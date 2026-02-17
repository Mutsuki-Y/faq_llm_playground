"""FastAPI アプリケーションのエントリポイント。

このモジュールはFAQ チャットボットのバックエンドサーバーを構成する。
`docker compose up` で起動すると、uvicorn がこのファイルの `app` を読み込む。

起動時の初期化フロー（lifespan）:
    1. AppConfig で環境変数/.envから設定を読み込み
    2. LLMクライアントを設定に基づいて生成（OpenAI or Vertex AI）
    3. ChromaDB ベクトルストアを初期化（ファイルベース永続化）
    4. MongoDB セッションマネージャーを初期化
    5. ChatService（RAGパイプライン）を構築
    6. ETLPipeline（データ取り込み）を構築
    7. 各サービスをAPIルーターに注入

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc
"""

from contextlib import asynccontextmanager

from api.routes import router, set_dependencies
from config import AppConfig
from etl.pipeline import ETLPipeline
from fastapi import FastAPI
from llm.factory import create_llm_client
from services.chat_service import ChatService
from services.session_manager import SessionManager
from store.vector_store import VectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理。

    起動時にすべてのサービスを初期化し、APIルーターに注入する。
    シャットダウン時は yield 以降で後処理を行う（現時点では不要）。
    """
    # --- 起動時の初期化 ---
    config = AppConfig()

    # LLMクライアント（OpenAI / Vertex AI）
    llm_client = create_llm_client(config)

    # ベクトルストア（ChromaDB、ファイルベース永続化）
    vector_store = VectorStore(config)

    # セッションマネージャー（MongoDB）
    session_manager = SessionManager(config)

    # RAGチャットサービス
    chat_service = ChatService(llm_client, vector_store, session_manager, config)

    # ETLパイプライン（Excel + 画像取り込み）
    etl_pipeline = ETLPipeline(config, llm_client, vector_store)

    # APIルーターにサービスを注入
    set_dependencies(chat_service, etl_pipeline, session_manager, config)

    yield  # アプリケーション稼働中


app = FastAPI(
    title="FAQ Chatbot API",
    description="""
## FAQ チャットボット REST API

ExcelファイルのFAQデータと画像をベクトル化し、
RAG（Retrieval-Augmented Generation）パターンでユーザーの質問に回答するAPIです。

### 主な機能

- **チャット**: 質問に対してFAQナレッジベースから関連情報を検索し、LLMで回答を生成
- **データ取り込み**: ExcelファイルのFAQデータと画像をベクトルストアに取り込み
- **セッション管理**: チャット履歴をセッション単位でMongoDBに保存
- **ヘルスチェック**: システムの稼働状態を確認

### 使い方

1. `POST /api/session` でセッションIDを取得
2. `POST /api/ingest` でFAQデータを取り込み（初回のみ）
3. `POST /api/chat` で質問を送信して回答を取得

### 技術スタック

- **LLM**: OpenAI GPT-4o（Vertex AI切り替え可能）
- **Embedding**: OpenAI text-embedding-3-small
- **ベクトルストア**: ChromaDB（ファイルベース、コサイン類似度）
- **チャット履歴**: MongoDB
- **フレームワーク**: FastAPI + uvicorn
    """,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.include_router(router)
