"""FAQ チャットボットシステムの Pydantic データモデル定義。

このモジュールはシステム全体で使用されるデータ構造を定義する。
各モデルは FastAPI の自動ドキュメント生成（Swagger UI）にも使用される。

モデル一覧:
    - ContentType: コンテンツ種別の列挙型（text / image）
    - FAQEntry: Excelから読み込んだFAQの1行分のデータ
    - ChunkMetadata / Chunk: ベクトルストアに保存するテキストチャンクとメタデータ
    - ImageMetadata / ImageDocument: ベクトルストアに保存する画像ドキュメントとメタデータ
    - SearchResult: ベクトル類似度検索の結果1件
    - SourceInfo: 回答の参照元情報（フロントエンドに返却）
    - ChatMessage: チャット履歴の1メッセージ（質問+回答+ソース+タイムスタンプ）
    - LLMResponse: LLMからの応答（プロバイダー非依存の統一形式）
    - ChatRequest / ChatResponse: チャットAPIのリクエスト・レスポンス
    - IngestResult: ETL取り込み処理の結果サマリー
    - EvaluationResult: DeepEval精度評価の結果
    - EvalTestCase: DeepEval評価用のテストケース
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# =============================================================================
# 列挙型
# =============================================================================

class ContentType(str, Enum):
    """コンテンツの種別。

    ベクトルストアに保存されるドキュメントがテキスト由来か画像由来かを区別する。
    検索結果やソース情報でフロントエンドに返却され、表示方法の切り替えに使用される。
    """
    TEXT = "text"
    IMAGE = "image"


# =============================================================================
# FAQ データモデル
# =============================================================================

class FAQEntry(BaseModel):
    """Excelファイルから読み込んだFAQエントリ（1行分）。

    ExcelReaderが各行をこのモデルに変換する。
    ステータスが「公開」のエントリのみがチャンク化の対象となる。
    """
    no: int = Field(..., description="FAQ通し番号（Excelの No. カラム）")
    status: str = Field(..., description="公開ステータス（「公開」の行のみ取り込み対象）")
    parent_category: str = Field(..., description="親カテゴリ（大分類）")
    child_category: str = Field(..., description="子カテゴリ（小分類）")
    title: str = Field(..., description="FAQのタイトル（質問文）")
    body: str = Field(..., description="FAQの本文（回答文）")
    source_file: str = Field(..., description="読み込み元のExcelファイル名")
    sheet_name: str = Field(..., description="読み込み元のシート名")
    row_number: int = Field(..., description="Excel上の行番号（ヘッダー除く）")


# =============================================================================
# チャンク・ベクトルストア関連
# =============================================================================

class ChunkMetadata(BaseModel):
    """Chunkに付与するメタデータ。

    ベクトルストア（ChromaDB）にEmbeddingと共に保存され、
    検索結果のソース情報としてユーザーに返却される。
    """
    source_file: str = Field(..., description="元のExcelファイル名")
    sheet_name: str = Field(..., description="元のシート名")
    row_number: int = Field(..., description="Excel上の行番号")
    parent_category: str = Field(..., description="親カテゴリ")
    child_category: str = Field(..., description="子カテゴリ")
    title: str = Field(..., description="FAQタイトル（検索結果の表示用）")
    content_type: ContentType = Field(
        default=ContentType.TEXT,
        description="コンテンツ種別（テキストチャンクは常に 'text'）",
    )


class Chunk(BaseModel):
    """ベクトルストアに保存するテキストチャンク。

    FAQEntryのタイトルと本文を結合したテキストと、
    出典を追跡するためのメタデータで構成される。
    chunk_idはUUID v4で自動生成される。
    """
    chunk_id: str = Field(..., description="チャンクの一意識別子（UUID v4）")
    text: str = Field(..., description="チャンクテキスト（タイトル + 改行 + 本文）")
    metadata: ChunkMetadata = Field(..., description="チャンクのメタデータ")


class ImageMetadata(BaseModel):
    """画像ドキュメントのメタデータ。

    画像ファイルのパスとソースファイル名を保持する。
    検索結果で画像タイプの場合、image_pathを使ってフロントエンドで画像を表示する。
    """
    image_path: str = Field(..., description="画像ファイルのパス")
    source_file: str = Field(..., description="元の画像ファイル名")
    content_type: ContentType = Field(
        default=ContentType.IMAGE,
        description="コンテンツ種別（画像ドキュメントは常に 'image'）",
    )


class ImageDocument(BaseModel):
    """ベクトルストアに保存する画像ドキュメント。

    マルチモーダルLLMが生成した画像の説明テキストをEmbedding化して保存する。
    検索時は説明テキストのEmbeddingで類似度を計算し、
    結果にはimage_pathを含めてフロントエンドで画像表示を可能にする。
    """
    doc_id: str = Field(..., description="ドキュメントの一意識別子（UUID v4）")
    description: str = Field(..., description="LLMが生成した画像の説明テキスト")
    metadata: ImageMetadata = Field(..., description="画像のメタデータ")


# =============================================================================
# 検索・回答関連
# =============================================================================

class SearchResult(BaseModel):
    """ベクトル類似度検索の結果1件。

    ChromaDBのコサイン類似度検索から返される。
    scoreは0.0〜1.0の範囲で、1.0に近いほど類似度が高い。
    """
    content: str = Field(..., description="ドキュメントのテキスト内容")
    score: float = Field(..., description="コサイン類似度スコア（0.0〜1.0、高いほど類似）")
    metadata: dict = Field(..., description="ドキュメントのメタデータ（source_file等）")
    content_type: ContentType = Field(..., description="コンテンツ種別（text / image）")


class SourceInfo(BaseModel):
    """回答の参照元情報。

    チャットAPIのレスポンスに含まれ、フロントエンドで
    「参照元」として表示される。画像ソースの場合はimage_pathが設定される。
    """
    content: str = Field(..., description="参照元のテキスト内容")
    source_file: str = Field(..., description="参照元のファイル名")
    content_type: ContentType = Field(..., description="コンテンツ種別（text / image）")
    score: float = Field(..., description="類似度スコア")
    image_path: Optional[str] = Field(
        default=None,
        description="画像ファイルのパス（content_typeがimageの場合のみ設定）",
    )


class ChatMessage(BaseModel):
    """チャット履歴の1メッセージ。

    MongoDBのセッションドキュメント内のmessages配列に保存される。
    get_recent_historyで取得され、プロンプト構築時にコンテキストとして使用される。
    """
    question: str = Field(..., description="ユーザーの質問テキスト")
    answer: str = Field(..., description="チャットボットの回答テキスト")
    sources: list[SourceInfo] = Field(..., description="回答の参照元情報リスト")
    timestamp: str = Field(..., description="メッセージのタイムスタンプ（ISO 8601 UTC）")


class LLMResponse(BaseModel):
    """LLMからの応答（プロバイダー非依存の統一形式）。

    OpenAIでもVertex AIでも同じ形式で返却されるため、
    上位レイヤーはプロバイダーの違いを意識する必要がない。
    """
    content: str = Field(..., description="LLMが生成した回答テキスト")
    model: str = Field(..., description="使用されたモデル名（例: gpt-4o）")
    usage: dict = Field(..., description="トークン使用量（prompt_tokens, completion_tokens, total_tokens）")


# =============================================================================
# API リクエスト / レスポンス
# =============================================================================

class ChatRequest(BaseModel):
    """チャットAPIリクエスト（POST /api/chat）。

    フロントエンドから送信される。session_idは事前に
    POST /api/session で取得したものを使用する。

    Example:
        {"question": "VPNに接続できません", "session_id": "550e8400-..."}
    """
    question: str = Field(
        ...,
        min_length=1,
        description="ユーザーの質問テキスト（空文字不可）",
        json_schema_extra={"example": "VPNに接続できない場合はどうすればよいですか？"},
    )
    session_id: str = Field(
        ...,
        min_length=1,
        description="チャットセッションID（POST /api/session で取得）",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )


class ChatResponse(BaseModel):
    """チャットAPIレスポンス（POST /api/chat）。

    RAGパイプラインで生成された回答と、回答の根拠となった参照元情報を返す。

    Example:
        {
            "answer": "VPNクライアントを再起動してください...",
            "sources": [...],
            "session_id": "550e8400-..."
        }
    """
    answer: str = Field(..., description="チャットボットの回答テキスト")
    sources: list[SourceInfo] = Field(
        ...,
        description="回答の参照元情報リスト（類似度スコア降順）",
    )
    session_id: str = Field(..., description="チャットセッションID")


class IngestResult(BaseModel):
    """ETL取り込み処理の結果サマリー（POST /api/ingest）。

    Excelファイルと画像の取り込み処理の結果を返す。
    error_countが0でない場合、一部のドキュメントの処理に失敗している。

    Example:
        {
            "total_processed": 42,
            "error_count": 0,
            "details": "FAQ_IT.xlsx: 42件のチャンクを取り込み; 画像: 3件取り込み, 0件エラー"
        }
    """
    total_processed: int = Field(..., description="正常に処理されたドキュメント数")
    error_count: int = Field(..., description="処理に失敗したドキュメント数")
    details: str = Field(..., description="処理結果の詳細メッセージ")


# =============================================================================
# DeepEval 精度評価
# =============================================================================

class EvaluationResult(BaseModel):
    """DeepEval精度評価の結果。

    3つの指標（Faithfulness, Answer Relevancy, Contextual Relevancy）の
    平均スコアと、各テストケースごとの詳細スコアを含む。
    スコアは0.0〜1.0の範囲で、1.0に近いほど品質が高い。
    """
    faithfulness: float = Field(
        ...,
        description="忠実性スコア平均（コンテキストに忠実な回答か、0.0〜1.0）",
    )
    answer_relevancy: float = Field(
        ...,
        description="回答関連性スコア平均（質問に対して関連性のある回答か、0.0〜1.0）",
    )
    contextual_relevancy: float = Field(
        ...,
        description="コンテキスト関連性スコア平均（検索コンテキストが質問に関連しているか、0.0〜1.0）",
    )
    summary: dict = Field(
        ...,
        description="評価サマリー（total_cases, 各指標の個別スコア配列）",
    )


class EvalTestCase(BaseModel):
    """DeepEval評価用のテストケース。

    JSONファイルから読み込まれ、RAGパイプラインの精度評価に使用される。
    contextにはRAGが検索すべき正解のコンテキストを記述する。

    Example:
        {
            "question": "VPNに接続できない場合は？",
            "expected_answer": "VPNクライアントを再起動してください",
            "context": ["VPN接続のトラブルシューティング: ..."]
        }
    """
    question: str = Field(..., description="評価用の質問テキスト")
    expected_answer: str = Field(..., description="期待される回答テキスト")
    context: list[str] = Field(..., description="正解コンテキストのリスト")
