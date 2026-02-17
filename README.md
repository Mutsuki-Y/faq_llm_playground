# FAQ チャットボット

ExcelファイルのFAQデータと画像をベクトル化し、RAG（Retrieval-Augmented Generation）パターンでユーザーの質問に回答するチャットボットシステム。

## 目次

- [システム構成](#システム構成)
- [技術スタック](#技術スタック)
- [クイックスタート](#クイックスタート)
- [FAQデータの準備](#faqデータの準備)
- [セッション管理機能](#セッション管理機能)
- [Embedding と プロンプトの仕組み](#embedding-と-プロンプトの仕組み)
- [API リファレンス](#api-リファレンス)
- [プロジェクト構成](#プロジェクト構成)
- [各モジュールの詳細](#各モジュールの詳細)
- [環境変数リファレンス](#環境変数リファレンス)
- [カスタマイズガイド](#カスタマイズガイド)
- [テスト](#テスト)
- [DeepEval 精度評価](#deepeval-精度評価)
- [トラブルシューティング](#トラブルシューティング)

---

## システム構成

```
┌──────────────────────────────────────────────────────────┐
│                    Docker Compose                         │
│                                                           │
│  ┌──────────────┐   ┌───────────────┐   ┌─────────────┐  │
│  │  Frontend     │   │  Backend      │   │  MongoDB    │  │
│  │  Vue.js 3     │──▶│  FastAPI      │──▶│  mongo:7    │  │
│  │  Vite         │   │  Python 3.12  │   │  :27017     │  │
│  │  :5173        │   │  :8000        │   └─────────────┘  │
│  └──────────────┘   └───────┬───────┘                     │
│                              │                             │
│                     ┌────────┴────────┐                    │
│                     │   ChromaDB      │                    │
│                     │  (ファイルDB)    │                    │
│                     │  コサイン類似度  │                    │
│                     │  多言語Embed    │                    │
│                     └─────────────────┘                    │
└──────────────────────────────────────────────────────────┘
           ↕                    ↕
      ブラウザ            Groq API
    (localhost:5173)    (Llama 3.3 チャット補完のみ)
```

### サービス構成

| サービス | 技術 | ポート | 役割 | データ永続化 |
|---------|------|--------|------|-------------|
| frontend | Vue.js 3 + Vite | 5173 | チャットUI | なし（SPA） |
| backend | Python 3.12 + FastAPI | 8000 | REST API、RAGパイプライン、ETL | ChromaDB（ファイル） |
| mongodb | MongoDB 7 | 27017 | チャット履歴の永続化 | Docker Volume |

### データフロー

```
[ユーザー] → [Vue.js フロントエンド] → [FastAPI バックエンド]
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
            [ローカルEmbedding]       [ChromaDB 検索]          [MongoDB 履歴取得]
            (多言語モデル)            (ローカルEmbed+検索)      │
                    │                         │                         │
                    ▼                         ▼                         ▼
            [質問ベクトル化(ローカル)]  [類似ドキュメント取得]    [直近N件の会話]
                    │                         │                         │
                    └─────────────────────────┼─────────────────────────┘
                                              ▼
                                    [プロンプト構築]
                                    (システムプロンプト + コンテキスト + 履歴 + 質問)
                                              │
                                              ▼
                                    [Groq API (Llama 3.3)]
                                              │
                                              ▼
                                    [回答 + ソース情報を返却]
```

---

## 技術スタック

| カテゴリ | 技術 | バージョン | 用途 |
|---------|------|-----------|------|
| バックエンドFW | FastAPI | ≥0.115 | REST API、自動Swaggerドキュメント |
| ASGIサーバー | uvicorn | ≥0.32 | 非同期HTTPサーバー |
| ベクトルストア | ChromaDB | ≥0.5 | ファイルベースのベクトルDB、コサイン類似度検索 |
| Excel解析 | openpyxl | ≥3.1 | .xlsx形式のFAQデータ読み込み |
| LLMクライアント | openai (Groq互換) | ≥1.50 | Groq API経由でLlama 3.3チャット補完、画像説明 |
| Embedding | sentence-transformers | ≥3.0 | ローカル多言語Embedding生成（paraphrase-multilingual-MiniLM-L12-v2）。API不要、日本語対応 |
| MongoDB非同期 | motor | ≥3.6 | チャット履歴の非同期CRUD |
| 設定管理 | pydantic-settings | ≥2.5 | 環境変数/.envからの型安全な設定読み込み |
| フロントエンド | Vue.js 3 | ≥3.5 | Composition API ベースのチャットUI |
| ビルドツール | Vite | ≥6.0 | 高速HMR、開発サーバー |
| テスト | pytest + hypothesis | ≥8.3 / ≥6.112 | ユニットテスト + プロパティベーステスト |
| 精度評価 | DeepEval | ≥1.4 | RAGの回答品質評価（Faithfulness等） |
| コンテナ | Docker Compose | - | ローカル開発環境の統一 |

---

## クイックスタート

### 前提条件

- Docker Desktop がインストール済み
- Groq APIキーを取得済み（https://console.groq.com で無料アカウント作成）

### 1. リポジトリのクローンと環境変数の設定

```bash
git clone <repository-url>
cd <repository-dir>

# 環境変数ファイルを作成
cp .env.example .env

# .env を編集して OPENAI_API_KEY（Groqキー）を設定
# OPENAI_API_KEY=gsk-xxxxxxxxxxxxx
# OPENAI_BASE_URL=https://api.groq.com/openai/v1
# OPENAI_MODEL=llama-3.3-70b-versatile
```

### 2. 全サービスの起動

```bash
docker compose up --build
```

起動後にアクセスできるURL:

| URL | 内容 |
|-----|------|
| http://localhost:5173 | チャットUI（フロントエンド） |
| http://localhost:8000/docs | Swagger UI（APIドキュメント） |
| http://localhost:8000/redoc | ReDoc（APIドキュメント） |
| http://localhost:8000/api/health | ヘルスチェック |

### 3. FAQデータの取り込み

#### 方法1: UI からアップロード（推奨）

1. http://localhost:5173 を開く
2. ヘッダーの「📁 データ登録」ボタンをクリック
3. Excel (.xlsx) または画像 (.png, .jpg) ファイルを選択
4. 「アップロード＆登録」をクリック → 自動でベクトルストアに取り込まれる

#### 方法2: ファイル配置 + API

```bash
# Excelファイルを配置
cp your_faq.xlsx data/faq/

# 画像ファイルを配置（任意）
cp your_image.png data/images/

# ETLパイプラインを実行
curl -X POST http://localhost:8000/api/ingest
```

#### 方法3: API で直接アップロード

```bash
# Excelファイルをアップロード＆取り込み
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your_faq.xlsx"

# 画像ファイルをアップロード＆取り込み
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your_image.png"
```

### 4. チャット開始

ブラウザで http://localhost:5173 を開いて質問を入力。

または API を直接呼び出す:

```bash
# セッション作成
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/session | jq -r '.session_id')

# 質問を送信
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"VPNに接続できません\", \"session_id\": \"$SESSION_ID\"}"
```

### 5. サービスの停止

```bash
docker compose down          # コンテナ停止（データは保持）
docker compose down -v       # コンテナ停止 + MongoDBデータ削除
```

---

## FAQデータの準備

### Excelファイルの形式
[サンプルファイルはここからダウンロード可能](https://helpme.center/ja/faq-sample/dept-it/) 
ここでダウンロードしたものは1枚目のシートを削除しておいてください。

Excelファイル（.xlsx）は以下のカラム構成を想定しています（1行目はヘッダー）:

| カラム位置 | カラム名 | 説明 | 例 |
|-----------|---------|------|-----|
| A列 | No. | 通し番号（整数） | 1 |
| B列 | ステータス | 公開状態。**「公開」の行のみ**取り込み対象 | 公開 |
| C列 | 親カテゴリ | 大分類 | ネットワーク |
| D列 | 子カテゴリ | 小分類 | VPN |
| E列 | タイトル | FAQ質問タイトル | VPNに接続できない |
| F列 | 本文 | FAQ回答本文 | VPNクライアントを再起動... |

- 複数シートに対応（全シートを読み込み）
- ステータスが「公開」以外の行（「下書き」「非公開」等）はスキップされる
- タイトルと本文が結合（`タイトル\n本文`）されてチャンクとなり、Embeddingが生成される

### 画像ファイル

- 対応形式: PNG (.png), JPEG (.jpg, .jpeg)
- `data/images/` ディレクトリに配置
- マルチモーダルLLM（GPT-4o）が画像の説明テキストを自動生成
- 説明テキストがEmbedding化されてベクトルストアに保存される
- 検索結果に画像が含まれる場合、フロントエンドでサムネイルが表示される

---

## セッション管理機能

ChatGPTのようなセッション管理機能を搭載しています。

### 主な機能

1. **セッション一覧表示**
   - 左側のサイドバーに全セッションを新しい順で表示
   - 各セッションには最後のメッセージプレビュー、メッセージ数、経過時間を表示
   - サイドバーは折りたたみ可能（☰ボタン）

2. **新しいチャット作成**
   - 「➕ 新しいチャット」ボタンで新規セッション作成
   - 最初のメッセージ送信時に自動的にセッションが作成される

3. **セッション切り替え**
   - セッション一覧のアイテムをクリックで過去のセッションに切り替え
   - 履歴が自動的に復元され、続きから会話可能
   - アクティブなセッションは青色でハイライト

4. **セッション削除**
   - 各セッションにホバーすると🗑️ボタンが表示
   - 確認ダイアログ後に削除
   - 削除されたセッションは復元不可

5. **セッション永続化**
   - 現在のセッションIDはlocalStorageに保存
   - ページをリロードしても前回のセッションが復元される
   - リロードのたびに新規セッションが作成されることはない

### 使い方

1. **初回アクセス時**
   - セッション一覧が表示される（空の状態）
   - 質問を入力して送信すると、自動的に新規セッションが作成される

2. **セッション切り替え**
   - 左側のサイドバーから過去のセッションを選択
   - 履歴が復元され、続きから会話可能

3. **新しいチャット開始**
   - 「➕ 新しいチャット」ボタンをクリック
   - 空の状態で新規セッションが作成される

4. **リロード時の挙動**
   - 最後に使用していたセッションが自動的に復元される
   - セッションが削除されている場合は空の状態に戻る

### 時刻表示

セッション一覧の経過時間は相対表示されます：

- 1分未満: 「今」
- 1時間未満: 「5分前」「30分前」
- 24時間未満: 「2時間前」「12時間前」
- 7日未満: 「3日前」「5日前」
- 7日以上: 「1月15日」（日付表示）

### 参照元情報

回答の下部に「参照元」が表示されます：

- **ファイル名**: 参照したExcelファイル名
- **スコア**: コサイン類似度（0.0〜1.0、1.0に近いほど関連性が高い）
- **件数**: RAGパイプラインが参照したFAQデータの件数（デフォルト: 3件）

例:
```
参照元 (3件)
Sample_faq_dept_it_JP.xlsx (スコア: 0.78)
Sample_faq_dept_it_JP.xlsx (スコア: 0.61)
Sample_faq_dept_it_JP.xlsx (スコア: 0.37)
```

スコアが低い場合（0.5未満）は、FAQデータの改善や検索パラメータ（TOP_K）の調整を検討してください。

---

## Embedding と プロンプトの仕組み

このシステムの精度を左右する2つの重要な要素について説明します。

### Embedding（ベクトル化）

Embeddingは、テキストを数値ベクトルに変換する処理です。このシステムでは、FAQデータと質問の両方をベクトル化し、コサイン類似度で関連性を計算します。

#### 実装ファイル

**`backend/store/vector_store.py`** ⭐ 最重要

```python
class VectorStore:
    COLLECTION_NAME = "faq_documents"
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # ← ここを変更
    
    def __init__(self, config: AppConfig) -> None:
        self._client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.EMBEDDING_MODEL,
        )
        # コサイン類似度で検索
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._ef,
        )
```

#### 特徴

- **ローカル実行**: sentence-transformersを使用し、外部APIは不要
- **多言語対応**: `paraphrase-multilingual-MiniLM-L12-v2` は日本語に対応
- **自動生成**: FAQデータ追加時と質問検索時に自動的にEmbeddingを生成
- **コサイン類似度**: 0.0〜1.0のスコアで類似度を計算（1.0に近いほど類似）

#### モデル変更方法

`EMBEDDING_MODEL` 定数を変更すると、別のモデルに切り替え可能：

```python
# より高精度（遅い）
EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# 最高精度（最も遅い）
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
```

**注意**: モデル変更後は既存データのクリアと再取り込みが必要：
```bash
rm -rf data/chroma/*
curl -X POST http://localhost:8000/api/ingest
```

#### チャンク生成戦略

**`backend/etl/excel_reader.py`**

FAQデータをどのようにテキスト化するかで検索精度が変わります：

```python
def faq_entry_to_chunk(self, entry: FAQEntry) -> Chunk:
    # 現在: タイトル + 本文
    text = f"{entry.title}\n{entry.body}"
    
    # カスタマイズ例1: カテゴリ情報を追加（検索精度向上）
    # text = f"カテゴリ: {entry.parent_category} > {entry.child_category}\n{entry.title}\n{entry.body}"
    
    # カスタマイズ例2: タイトルを強調（タイトルマッチ優先）
    # text = f"{entry.title}\n{entry.title}\n{entry.body}"
    
    return Chunk(
        chunk_id=str(uuid.uuid4()),
        text=text,
        metadata=ChunkMetadata(...)
    )
```

---

### プロンプト構築

プロンプトは、LLMに送信する指示文です。システムプロンプト、FAQコンテキスト、チャット履歴、質問を組み合わせて構築します。

#### 実装ファイル

**`backend/services/chat_service.py`** ⭐ 最重要

#### システムプロンプト

LLMの振る舞いを定義する最も重要な要素：

```python
SYSTEM_PROMPT = (
    "あなたはFAQチャットボットです。"
    "提供されたFAQコンテキストに基づいてのみ回答してください。"
    "コンテキストに含まれない情報については「該当する情報が見つかりませんでした」と回答してください。"
    "回答は簡潔かつ正確に、日本語で行ってください。"
)
```

**カスタマイズ例**:

```python
# より柔軟な回答
SYSTEM_PROMPT = (
    "あなたはFAQチャットボットです。"
    "提供されたFAQコンテキストに基づいて回答してください。"
    "コンテキストに少しでも関連する情報がある場合は、その情報を使って回答してください。"
    "コンテキストに全く関連する情報がない場合のみ「該当する情報が見つかりませんでした」と回答してください。"
    "回答は丁寧かつ詳細に、日本語で行ってください。"
)

# より厳密な回答
SYSTEM_PROMPT = (
    "あなたはFAQチャットボットです。"
    "提供されたFAQコンテキストに完全に基づいてのみ回答してください。"
    "コンテキストに明示的に記載されていない情報については、一切推測せず「該当する情報が見つかりませんでした」と回答してください。"
    "回答は簡潔に、日本語で行ってください。"
)
```

#### プロンプト構築ロジック

`_build_prompt()` メソッドで以下の順序でプロンプトを構築：

```python
def _build_prompt(
    self,
    question: str,
    context: list[SearchResult],
    history: list[ChatMessage],
) -> list[dict]:
    messages: list[dict] = []
    
    # 1. システムプロンプト
    messages.append({"role": "system", "content": SYSTEM_PROMPT})
    
    # 2. FAQコンテキスト（検索結果）
    if context:
        context_parts = []
        for i, result in enumerate(context, 1):
            context_parts.append(f"[{i}] {result.content}")
        context_text = "\n\n".join(context_parts)
        messages.append({
            "role": "system",
            "content": f"以下はFAQコンテキストです:\n\n{context_text}",
        })
    
    # 3. チャット履歴（直近N件）
    for msg in history:
        messages.append({"role": "user", "content": msg.question})
        messages.append({"role": "assistant", "content": msg.answer})
    
    # 4. ユーザーの質問
    messages.append({"role": "user", "content": question})
    
    return messages
```

#### プロンプト構築の流れ

```
1. システムプロンプト
   ↓
2. FAQコンテキスト（検索結果 TOP_K=3件）
   [1] VPN接続のトラブルシューティング: まず...
   [2] ネットワーク設定の確認方法: ...
   [3] VPNクライアントの再起動手順: ...
   ↓
3. チャット履歴（直近 HISTORY_LIMIT=5件）
   User: 前回の質問
   Assistant: 前回の回答
   ↓
4. 現在の質問
   User: VPNに接続できません
   ↓
LLMに送信 → 回答生成
```

#### 設定パラメータ

`.env` で調整可能：

```bash
# 検索結果の件数（多い=コンテキスト豊富だがノイズ増加）
TOP_K=3

# チャット履歴の参照件数（多い=文脈理解向上だがトークン消費増加）
HISTORY_LIMIT=5
```

#### テスト

**`backend/tests/test_property_prompt.py`**

プロンプト構築の正しさを検証：

```python
def test_prompt_construction_completeness(session_manager, ...):
    """プロンプトにsystem + context + history + questionが全て含まれることを検証"""
    # システムプロンプトが含まれているか
    # コンテキストが全て含まれているか
    # 履歴が全て含まれているか
    # 質問が含まれているか
```

---

### 精度改善のポイント

| 変更したい内容 | ファイル | 変更箇所 | 影響度 |
|--------------|---------|---------|--------|
| 回答のトーン・制約 | `backend/services/chat_service.py` | `SYSTEM_PROMPT` 定数 | ⭐⭐⭐ 最大 |
| Embeddingモデル | `backend/store/vector_store.py` | `EMBEDDING_MODEL` 定数 | ⭐⭐⭐ 大 |
| チャンク生成戦略 | `backend/etl/excel_reader.py` | `faq_entry_to_chunk()` メソッド | ⭐⭐ 中 |
| 検索件数 | `.env` | `TOP_K` | ⭐⭐ 中 |
| 履歴参照件数 | `.env` | `HISTORY_LIMIT` | ⭐ 小 |
| LLMモデル | `.env` | `OPENAI_MODEL` | ⭐⭐ 中 |

**推奨順序**:
1. まず `SYSTEM_PROMPT` を調整（最も効果的で変更が簡単）
2. 次に `TOP_K` を調整（3→5に増やすとコンテキストが豊富に）
3. 必要に応じて `EMBEDDING_MODEL` を変更（データ再取り込みが必要）

---

## API リファレンス

詳細なAPIドキュメントは Swagger UI（http://localhost:8000/docs）で確認できます。

### POST /api/session

新しいチャットセッションを作成する。フロントエンドはページ読み込み時にこのエンドポイントを呼び出す。

```bash
curl -X POST http://localhost:8000/api/session
```

レスポンス:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### POST /api/chat

質問を送信してRAGパターンで回答を取得する。

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "VPNに接続できません", "session_id": "550e8400-..."}'
```

リクエスト:
| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| question | string | ○ | 質問テキスト（空文字不可） |
| session_id | string | ○ | セッションID（POST /api/session で取得） |

レスポンス:
```json
{
  "answer": "VPNクライアントを再起動し、ネットワーク設定を確認してください。",
  "sources": [
    {
      "content": "VPN接続のトラブルシューティング: まずVPNクライアントを再起動...",
      "source_file": "FAQ_IT.xlsx",
      "content_type": "text",
      "score": 0.92,
      "image_path": null
    }
  ],
  "session_id": "550e8400-..."
}
```

エラーレスポンス（バリデーション失敗時 HTTP 422）:
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "question"],
      "msg": "Field required"
    }
  ]
}
```

### POST /api/ingest

ETLパイプラインを実行してFAQデータと画像をベクトルストアに取り込む。

```bash
curl -X POST http://localhost:8000/api/ingest
```

レスポンス:
```json
{
  "total_processed": 42,
  "error_count": 0,
  "details": "FAQ_IT.xlsx: 42件のチャンクを取り込み; 画像: 3件取り込み, 0件エラー"
}
```

### POST /api/upload

ファイルをアップロードし、自動でETLパイプラインを実行する。対応形式: .xlsx, .png, .jpg, .jpeg

```bash
curl -X POST http://localhost:8000/api/upload -F "file=@FAQ_IT.xlsx"
```

レスポンス:
```json
{
  "filename": "FAQ_IT.xlsx",
  "file_type": "excel",
  "ingest_result": {
    "total_processed": 42,
    "error_count": 0,
    "details": "FAQ_IT.xlsx: 42件のチャンクを取り込み"
  }
}
```

非対応ファイル形式の場合は HTTP 400:
```json
{
  "detail": "サポートされていないファイル形式です: .csv。対応形式: .xlsx, .png, .jpg, .jpeg"
}
```

### GET /api/health

システムの稼働状態を確認する。

```bash
curl http://localhost:8000/api/health
```

レスポンス:
```json
{
  "status": "ok",
  "message": "FAQ Chatbot is running"
}
```

### GET /api/sessions

全セッションの一覧を取得する（新しい順）。

```bash
curl http://localhost:8000/api/sessions
```

レスポンス:
```json
{
  "sessions": [
    {
      "session_id": "550e8400-e29b-41d4-a716-446655440000",
      "created_at": "2025-01-01T00:00:00+00:00",
      "message_count": 5,
      "last_message": "VPNに接続できない場合はどうすればよいですか？"
    }
  ]
}
```

### GET /api/sessions/{session_id}

指定されたセッションIDの全履歴を取得する。

```bash
curl http://localhost:8000/api/sessions/550e8400-e29b-41d4-a716-446655440000
```

レスポンス:
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "question": "VPNに接続できません",
      "answer": "VPNクライアントを再起動してください...",
      "sources": [...],
      "timestamp": "2025-01-01T00:00:00+00:00"
    }
  ]
}
```

エラーレスポンス（セッションが存在しない場合 HTTP 404）:
```json
{
  "detail": "セッションが見つかりません"
}
```

### DELETE /api/sessions/{session_id}

指定されたセッションIDのセッションを削除する。

```bash
curl -X DELETE http://localhost:8000/api/sessions/550e8400-e29b-41d4-a716-446655440000
```

レスポンス:
```json
{
  "success": true,
  "message": "セッションを削除しました"
}
```

エラーレスポンス（セッションが存在しない場合 HTTP 404）:
```json
{
  "detail": "セッションが見つかりません"
}
```

---

## プロジェクト構成

```
.
├── backend/                          # バックエンド（Python / FastAPI）
│   ├── api/
│   │   └── routes.py                 # REST APIエンドポイント定義
│   ├── etl/
│   │   ├── excel_reader.py           # Excel読み込み・チャンク生成
│   │   ├── image_processor.py        # 画像→説明テキスト変換
│   │   └── pipeline.py              # ETLパイプライン統合
│   ├── evaluation/
│   │   ├── evaluator.py             # DeepEval精度評価エンジン
│   │   └── cli.py                   # 評価用CLIコマンド
│   ├── llm/
│   │   ├── base.py                  # LLMクライアント抽象基底クラス
│   │   ├── factory.py               # プロバイダー切り替えファクトリ
│   │   ├── openai_client.py         # OpenAI API実装
│   │   └── vertexai_client.py       # Vertex AIスタブ（将来用）
│   ├── services/
│   │   ├── chat_service.py          # RAGチャットサービス（中核ロジック）
│   │   └── session_manager.py       # MongoDBセッション管理
│   ├── store/
│   │   └── vector_store.py          # ChromaDBベクトルストア
│   ├── tests/                       # プロパティベーステスト（hypothesis）
│   │   ├── test_property_api.py     # P7: 不正リクエスト422検証
│   │   ├── test_property_etl.py     # P1: FAQフィルタリング・チャンク生成
│   │   ├── test_property_image_metadata.py  # P8: 画像メタデータ完全性
│   │   ├── test_property_models.py  # P2,P9: シリアライゼーション往復
│   │   ├── test_property_prompt.py  # P4: プロンプト構築完全性
│   │   ├── test_property_session.py # P5,P6: セッション履歴往復・初期化
│   │   ├── test_property_vector_store.py  # P3: 検索結果順序・完全性
│   │   └── test_smoke.py           # 環境スモークテスト
│   ├── config.py                    # 設定管理（pydantic-settings）
│   ├── conftest.py                  # pytest設定（sys.path調整）
│   ├── models.py                    # Pydanticデータモデル（全モデル定義）
│   ├── main.py                      # FastAPIエントリポイント
│   ├── Dockerfile                   # バックエンドDockerイメージ
│   └── requirements.txt             # Python依存パッケージ
├── frontend/                        # フロントエンド（Vue.js 3）
│   ├── src/
│   │   ├── components/
│   │   │   └── ChatView.vue         # チャットUIコンポーネント
│   │   ├── App.vue                  # ルートコンポーネント
│   │   └── main.js                  # Vueアプリケーションエントリ
│   ├── index.html                   # HTMLテンプレート
│   ├── vite.config.js               # Vite設定（APIプロキシ含む）
│   ├── package.json                 # Node.js依存パッケージ
│   └── Dockerfile                   # フロントエンドDockerイメージ
├── data/                            # データディレクトリ（ホストにマウント）
│   ├── faq/                         # FAQのExcelファイル配置先
│   ├── images/                      # 画像ファイル配置先
│   └── chroma/                      # ChromaDB永続化データ
├── docker-compose.yml               # Docker Compose定義
├── .env.example                     # 環境変数テンプレート
└── .env                             # 環境変数（gitignore推奨）
```

---

## 各モジュールの詳細

### backend/main.py — アプリケーションエントリポイント

FastAPIアプリケーションの起動と、全サービスの初期化を行う。`lifespan` コンテキストマネージャーで起動時に以下を初期化:

1. `AppConfig` — 環境変数/.envから設定読み込み
2. `LLMClientBase` — ファクトリパターンでOpenAI/VertexAIクライアントを生成
3. `VectorStore` — ChromaDBの初期化（永続化ディレクトリ指定）
4. `SessionManager` — MongoDB接続の確立
5. `ChatService` — 上記すべてを組み合わせたRAGサービス
6. `ETLPipeline` — データ取り込みパイプライン

### backend/services/chat_service.py — RAGチャットサービス

システムの中核。`answer()` メソッドが以下のRAGパイプラインを実行:

```
質問テキスト
    ↓ vector_store.search(query_text, top_k=3)
関連ドキュメント（最大3件）※Embeddingはローカル自動生成
    ↓ session_manager.get_recent_history(n=5)
直近5件のチャット履歴
    ↓ _build_prompt()
LLMプロンプト（system + context + history + question）
    ↓ llm_client.chat_completion()
回答テキスト
    ↓ session_manager.add_message()
履歴に保存 → ChatResponse を返却
```

`SYSTEM_PROMPT` 定数を編集すると、回答のトーンや制約を変更できる。

### backend/llm/ — LLMクライアント

Strategy パターンで実装。`LLMClientBase` 抽象クラスを継承した具象クラスを `factory.py` で切り替える。

| ファイル | クラス | 状態 | 説明 |
|---------|--------|------|------|
| base.py | `LLMClientBase` | 抽象 | 4つの抽象メソッド定義 |
| openai_client.py | `OpenAIClient` | 実装済 | OpenAI互換API（Groq経由でLlama 3.3チャット補完、マルチモーダル画像説明） |
| vertexai_client.py | `VertexAIClient` | スタブ | 将来のGCP移行用（NotImplementedError） |
| factory.py | `create_llm_client()` | - | `config.llm_provider` に基づいてインスタンス生成 |

新しいプロバイダーを追加する場合:
1. `LLMClientBase` を継承した新クラスを作成
2. `factory.py` に分岐を追加

### backend/etl/ — ETLパイプライン

FAQデータと画像の取り込みを担当。

| ファイル | クラス | 説明 |
|---------|--------|------|
| excel_reader.py | `ExcelReader` | Excelファイル読み込み、「公開」フィルタ、チャンク生成 |
| image_processor.py | `ImageProcessor` | 画像→マルチモーダルLLMで説明テキスト生成→ImageDocument |
| pipeline.py | `ETLPipeline` | 上記を統合。Embedding生成はVectorStore（ローカル）に委譲 |

### backend/store/vector_store.py — ベクトルストア

ChromaDB をラップ。HNSWインデックス + コサイン類似度で検索。Embedding生成はsentence-transformersの多言語モデル（paraphrase-multilingual-MiniLM-L12-v2）を使用するため、外部APIは不要。日本語テキストに対応。

主要メソッド:
- `add_chunks()` — テキストチャンクを保存（Embeddingはローカル自動生成）
- `add_image_documents()` — 画像ドキュメントを保存（Embeddingはローカル自動生成）
- `search()` — テキストクエリで類似度検索（結果はスコア降順）
- `is_empty()` — データ存在チェック（空の場合は「ナレッジベース未構築」メッセージ）

**カスタマイズ:** `EMBEDDING_MODEL` 定数を変更すると、別の多言語モデルに切り替え可能。

### backend/services/session_manager.py — セッション管理

MongoDB（motor非同期ドライバー）でチャット履歴を管理。

MongoDBドキュメント構造:
```json
{
  "session_id": "uuid-v4",
  "messages": [
    {
      "question": "VPNに接続できません",
      "answer": "VPNクライアントを再起動してください...",
      "sources": [...],
      "timestamp": "2025-01-01T00:00:00+00:00"
    }
  ],
  "created_at": "2025-01-01T00:00:00+00:00"
}
```

### frontend/src/components/ChatView.vue — チャットUI

Vue.js 3 Composition API で実装。主な機能:

- **セッション管理**: 左側のサイドバーでセッション一覧を表示、切り替え、削除
- **セッション永続化**: localStorageで現在のセッションIDを保存し、リロード時に復元
- **新規チャット作成**: 「➕ 新しいチャット」ボタンまたは最初のメッセージ送信時に作成
- **メッセージ送信**: Enter / 送信ボタンで `POST /api/chat` を呼び出し
- **会話履歴表示**: チャット形式で時系列表示（ユーザー: 右、ボット: 左）
- **画像表示**: 画像ソースを含む回答ではサムネイルを表示
- **ローディング表示**: 回答生成中はローディングアニメーション表示
- **参照元表示**: 回答の下部に参照元情報（ファイル名、スコア）を表示

---

## 環境変数リファレンス

`.env.example` をコピーして `.env` を作成し、値を設定する。

| 変数名 | 必須 | デフォルト | 説明 |
|--------|------|-----------|------|
| `OPENAI_API_KEY` | ○ | - | Groq APIキー（またはOpenAI互換APIキー）。未設定だと起動時にエラー |
| `OPENAI_BASE_URL` | - | `https://api.openai.com/v1` | API BaseURL。Groqは `https://api.groq.com/openai/v1` |
| `LLM_PROVIDER` | - | `openai` | LLMプロバイダー（`openai` / `vertexai`） |
| `OPENAI_MODEL` | - | `gpt-4o` | チャット補完モデル。Groqは `llama-3.3-70b-versatile` 推奨 |
| `FAQ_DATA_DIR` | - | `./data/faq` | FAQのExcelファイルディレクトリ |
| `IMAGE_DATA_DIR` | - | `./data/images` | 画像ファイルディレクトリ |
| `CHROMA_PERSIST_DIR` | - | `./data/chroma` | ChromaDBデータ永続化先 |
| `MONGODB_URI` | - | `mongodb://mongodb:27017` | MongoDB接続URI |
| `MONGODB_DB_NAME` | - | `faq_chatbot` | MongoDBデータベース名 |
| `TOP_K` | - | `3` | 類似検索で返す上位件数 |
| `HISTORY_LIMIT` | - | `5` | プロンプトに含めるチャット履歴件数 |

---

## カスタマイズガイド

### 回答のトーン・制約を変更したい

`backend/services/chat_service.py` の `SYSTEM_PROMPT` 定数を編集:

```python
SYSTEM_PROMPT = (
    "あなたはFAQチャットボットです。"
    "提供されたFAQコンテキストに基づいてのみ回答してください。"
    # ↓ ここを変更
    "回答は簡潔かつ正確に、日本語で行ってください。"
)
```

### LLMモデルを変更したい

`.env` の `OPENAI_MODEL` を変更:

```bash
# コスト削減（精度はやや低下）
OPENAI_MODEL=gpt-4o-mini

# 最新モデル
OPENAI_MODEL=gpt-4o-2024-08-06
```

### 検索精度を調整したい

`.env` で以下を調整:

```bash
# 検索結果の件数（多い=コンテキスト豊富だがノイズ増加）
TOP_K=5

# チャット履歴の参照件数（多い=文脈理解向上だがトークン消費増加）
HISTORY_LIMIT=10
```

> **Note:** Embedding生成はsentence-transformersの多言語モデル（paraphrase-multilingual-MiniLM-L12-v2）を使用しています。日本語に対応しており、API不要です。

### 精度を向上させたい

RAGシステムの精度を改善するには、以下の箇所をカスタマイズします。

#### 1. システムプロンプトの調整（最も効果的）

`backend/services/chat_service.py` の `SYSTEM_PROMPT` 定数を編集:

```python
SYSTEM_PROMPT = (
    "あなたはFAQチャットボットです。"
    "提供されたFAQコンテキストに基づいて回答してください。"
    # ↓ ここを変更して回答の厳密さを調整
    "コンテキストに少しでも関連する情報がある場合は、その情報を使って回答してください。"
    "コンテキストに全く関連する情報がない場合のみ「該当する情報が見つかりませんでした」と回答してください。"
    "回答は簡潔かつ正確に、日本語で行ってください。"
)
```

**調整ポイント:**
- より厳密な回答が欲しい場合: 「コンテキストに基づいてのみ」を強調
- より柔軟な回答が欲しい場合: 「少しでも関連する情報があれば」を追加
- 回答のトーン変更: 「丁寧に」「簡潔に」「ステップバイステップで」等を追加

#### 2. Embeddingモデルの変更

`backend/store/vector_store.py` の `EMBEDDING_MODEL` を変更:

```python
class VectorStore:
    COLLECTION_NAME = "faq_documents"
    # ↓ ここを変更
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # 現在（日本語対応）
    # EMBEDDING_MODEL = "paraphrase-multilingual-mpnet-base-v2"  # より高精度（遅い）
    # EMBEDDING_MODEL = "intfloat/multilingual-e5-large"  # 最高精度（最も遅い）
```

**注意:** モデル変更後は既存データのクリアと再取り込みが必要:
```bash
rm -rf data/chroma/*
curl -X POST http://localhost:8000/api/ingest
```

#### 3. チャンク生成戦略の変更

`backend/etl/excel_reader.py` の `faq_entry_to_chunk()` メソッドを編集:

```python
def faq_entry_to_chunk(self, entry: FAQEntry) -> Chunk:
    # 現在: タイトル + 本文
    text = f"{entry.title}\n{entry.body}"
    
    # カスタマイズ例1: カテゴリ情報を追加（検索精度向上）
    # text = f"カテゴリ: {entry.parent_category} > {entry.child_category}\n{entry.title}\n{entry.body}"
    
    # カスタマイズ例2: タイトルを強調（タイトルマッチ優先）
    # text = f"{entry.title}\n{entry.title}\n{entry.body}"
    
    return Chunk(...)
```

#### 4. 検索パラメータの調整

`.env` で `TOP_K` を増やすと、より多くのコンテキストがLLMに渡されます:

```bash
# デフォルト: 3件
TOP_K=3

# より多くのコンテキストを参照（精度向上、ノイズ増加）
TOP_K=5

# 少ないコンテキストで絞り込み（ノイズ減少、情報不足リスク）
TOP_K=2
```

#### 5. LLMモデルの変更

`.env` でGroqの別モデルに切り替え:

```bash
# 現在: Llama 3.3 70B（バランス型）
OPENAI_MODEL=llama-3.3-70b-versatile

# より高速（精度やや低下）
OPENAI_MODEL=llama-3.1-8b-instant

# より高精度（やや遅い）
OPENAI_MODEL=llama-3.1-70b-versatile
```

Groq以外のプロバイダーに切り替える場合:

```bash
# OpenAI（有料、高精度）
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-proj-xxxxx
OPENAI_MODEL=gpt-4o

# Google Gemini（無料枠あり）
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_API_KEY=your-gemini-api-key
OPENAI_MODEL=gemini-1.5-flash
```

### Vertex AI に切り替えたい

1. `backend/llm/vertexai_client.py` のスタブメソッドを実装
2. `.env` で `LLM_PROVIDER=vertexai` に変更
3. GCP認証情報を環境変数に追加
4. `backend/config.py` に必要な設定フィールドを追加

### 新しいLLMプロバイダーを追加したい

1. `backend/llm/` に新しいクライアントクラスを作成（`LLMClientBase` を継承）
2. `backend/llm/factory.py` の `create_llm_client()` に分岐を追加
3. `backend/config.py` に必要な設定フィールドを追加

### 新しいデータソースを追加したい

1. `backend/etl/` に新しいリーダークラスを作成（例: `csv_reader.py`）
2. `backend/etl/pipeline.py` の `ingest_all()` に新しい取り込みロジックを追加
3. 必要に応じて `backend/models.py` に新しいデータモデルを追加

### Excelのカラム構成を変更したい

`backend/etl/excel_reader.py` の `ExcelReader` クラスのカラムインデックス定数を変更:

```python
class ExcelReader:
    COL_NO = 0              # A列: No.
    COL_STATUS = 1          # B列: ステータス
    COL_PARENT_CATEGORY = 2 # C列: 親カテゴリ
    COL_CHILD_CATEGORY = 3  # D列: 子カテゴリ
    COL_TITLE = 4           # E列: タイトル
    COL_BODY = 5            # F列: 本文
    PUBLISH_STATUS = "公開"  # 取り込み対象のステータス値
```

### フロントエンドのデザインを変更したい

`frontend/src/components/ChatView.vue` の `<style scoped>` セクションを編集:

| CSSクラス | 対象 |
|-----------|------|
| `.chat-header` | ヘッダー（背景色、テキスト） |
| `.message.user` | ユーザーメッセージの吹き出し |
| `.message.assistant` | ボットメッセージの吹き出し |
| `.chat-input` | 入力欄エリア |
| `.chat-input button` | 送信ボタン |
| `.source-thumbnail` | 画像サムネイルのサイズ |

### ベクトルストアをリセットしたい

```bash
# ChromaDBのデータを削除
rm -rf data/chroma/*

# 再取り込み
curl -X POST http://localhost:8000/api/ingest
```

### チャット履歴をリセットしたい

```bash
# MongoDBのデータを削除（Docker Volume ごと）
docker compose down -v
docker compose up --build
```

---

## テスト

### テスト実行

```bash
# 全テスト実行
docker compose run --rm backend pytest tests/ -v

# 特定のテストファイルのみ
docker compose run --rm backend pytest tests/test_property_models.py -v

# 特定のテスト関数のみ
docker compose run --rm backend pytest tests/test_property_prompt.py::test_prompt_construction_completeness -v
```

### テスト一覧

全テストは hypothesis ライブラリによるプロパティベーステスト（各100イテレーション）。

| テストファイル | プロパティ | 検証内容 | 対応要件 |
|---------------|-----------|---------|---------|
| test_property_models.py | P2 | Chunk/ImageDocumentのJSON往復 | 9.3 |
| test_property_models.py | P9 | EvalTestCaseのJSON往復 | 13.2 |
| test_property_etl.py | P1 | FAQフィルタリング・チャンク生成の正しさ | 1.2, 1.3, 1.5 |
| test_property_image_metadata.py | P8 | ImageDocumentメタデータの完全性 | 3.4 |
| test_property_vector_store.py | P3 | 検索結果の順序（スコア降順）と完全性 | 4.2, 4.3, 3.5 |
| test_property_prompt.py | P4 | プロンプト構築の完全性（system+context+history+question） | 5.1, 5.4, 6.2 |
| test_property_session.py | P5 | セッション履歴の永続化往復（MongoDB） | 6.1, 6.4 |
| test_property_session.py | P6 | 新規セッション初期化（一意ID + 空履歴） | 6.5 |
| test_property_api.py | P7 | 不正リクエストに対するHTTP 422レスポンス | 7.3 |
| test_smoke.py | - | 環境スモークテスト | - |

### テストの仕組み

プロパティベーステスト（PBT）は、ランダムに生成された入力データに対して「常に成り立つべき性質」を検証する。例:

- P2: 「任意のChunkをJSONにシリアライズしてデシリアライズすると、元と同一のオブジェクトが復元される」
- P3: 「任意のクエリに対して、検索結果はスコア降順で並び、最大k件を返す」
- P5: 「任意の質問・回答ペアをMongoDBに保存して読み込むと、同一のデータが復元される」

---

## DeepEval 精度評価

RAGパイプラインの回答品質を定量的に評価する。

### 評価指標

| 指標 | 説明 | スコア範囲 |
|------|------|-----------|
| Faithfulness | コンテキストに忠実な回答か（ハルシネーションがないか） | 0.0〜1.0 |
| Answer Relevancy | 質問に対して関連性のある回答か | 0.0〜1.0 |
| Contextual Relevancy | 検索されたコンテキストが質問に関連しているか | 0.0〜1.0 |

### 使い方

```bash
# 方法1: FAQデータからテストケースを自動生成（推奨）
# ※ 事前に data/faq/ にExcelファイルを配置しておくこと
docker compose run --rm backend python -m evaluation.cli auto \
  --output ./data/eval_auto.json

# コンテキストあたりの生成数を指定（デフォルト: 2）
docker compose run --rm backend python -m evaluation.cli auto \
  --output ./data/eval_auto.json \
  --max-per-context 3

# 自動生成したテストケースで評価を実行
docker compose run --rm backend python -m evaluation.cli evaluate \
  --test-cases ./data/eval_auto.json

# 方法2: テンプレートから手動でテストケースを作成
docker compose run --rm backend python -m evaluation.cli template \
  --output ./data/eval_cases.json
# data/eval_cases.json を編集後、評価を実行
docker compose run --rm backend python -m evaluation.cli evaluate \
  --test-cases ./data/eval_cases.json

# 結果をファイルに出力
docker compose run --rm backend python -m evaluation.cli evaluate \
  --test-cases ./data/eval_auto.json \
  --output ./data/eval_results.json
```

自動生成（`auto`）は DeepEval の Synthesizer を使用し、取り込み済みFAQデータの各チャンクをコンテキストとして、LLMが質問と期待回答のペアを生成します。手動でテストケースを書く手間が省けるため、まずはこちらを試すのがおすすめです。

### テストケースの形式

```json
[
  {
    "question": "VPNに接続できない場合はどうすればよいですか？",
    "expected_answer": "VPNクライアントを再起動し、ネットワーク設定を確認してください。",
    "context": [
      "VPN接続のトラブルシューティング: まずVPNクライアントを再起動してください。",
      "ネットワーク設定でプロキシが正しく設定されているか確認してください。"
    ]
  }
]
```

---

## トラブルシューティング

### 「ナレッジベースが未構築です」と表示される

FAQデータの取り込みが完了していない。`POST /api/ingest` を実行する。

### Embedding生成でエラーが発生する

Embedding生成はsentence-transformersの多言語モデルで行うため、通常はAPIエラーは発生しない。初回起動時にモデルのダウンロードが行われるため、ネットワーク接続が必要。

> **Note:** Groq APIはチャット補完（回答生成）のみに使用される。Embedding生成にはAPIは不要。

### MongoDBに接続できない

- `docker compose ps` で mongodb コンテナが起動しているか確認
- `.env` の `MONGODB_URI` が `mongodb://mongodb:27017` になっているか確認（Docker内部ネットワーク名）

### ChromaDBのデータが壊れた

```bash
rm -rf data/chroma/*
curl -X POST http://localhost:8000/api/ingest
```

### フロントエンドからAPIに接続できない

- `vite.config.js` のプロキシ設定で `/api` が `http://backend:8000` に転送されているか確認
- `docker compose ps` で backend コンテナが起動しているか確認
- ブラウザの開発者ツールでネットワークエラーを確認
