"""アプリケーション設定管理モジュール。

pydantic-settings を使用して環境変数と .env ファイルから設定を読み込む。
必須フィールド（openai_api_key）が未設定の場合、起動時にバリデーションエラーが発生する。

設定の優先順位:
    1. 環境変数（最優先）
    2. .env ファイル
    3. デフォルト値

使用例:
    config = AppConfig()  # 環境変数/.envから自動読み込み
    print(config.openai_model)  # "gpt-4o"
"""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """FAQ チャットボットのアプリケーション設定。

    環境変数名は各フィールド名を大文字にしたもの（例: openai_api_key → OPENAI_API_KEY）。
    docker-compose.yml の env_file で .env を指定しているため、
    .env ファイルに記述した値が自動的に読み込まれる。
    """

    # -------------------------------------------------------------------------
    # LLM設定
    # -------------------------------------------------------------------------
    llm_provider: str = Field(
        default="openai",
        description="LLMプロバイダー。'openai' または 'vertexai'。"
        "factory.py でプロバイダーに応じたクライアントが生成される。",
    )
    openai_api_key: str = Field(
        ...,  # 必須 — 未設定時にバリデーションエラー
        description="OpenAI APIキー（またはGroq等の互換APIキー）。",
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI互換APIのベースURL。Groq等を使う場合に変更する。",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="チャット補完に使用するモデル名。"
        "Groqの場合は llama-3.3-70b-versatile 等を指定。",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding生成に使用するモデル名。"
        "text-embedding-3-large に変更すると精度が向上するがコストが増加する。",
    )

    # -------------------------------------------------------------------------
    # データパス（Docker環境ではコンテナ内のパス）
    # -------------------------------------------------------------------------
    faq_data_dir: str = Field(
        default="./data/faq",
        description="FAQのExcelファイル（.xlsx）を配置するディレクトリ。"
        "docker-compose.yml でホストの data/faq/ がマウントされる。",
    )
    image_data_dir: str = Field(
        default="./data/images",
        description="画像ファイル（PNG/JPEG）を配置するディレクトリ。"
        "docker-compose.yml でホストの data/images/ がマウントされる。",
    )
    chroma_persist_dir: str = Field(
        default="./data/chroma",
        description="ChromaDBのデータ永続化ディレクトリ。"
        "docker-compose.yml でホストの data/chroma/ がマウントされる。",
    )

    # -------------------------------------------------------------------------
    # MongoDB設定
    # -------------------------------------------------------------------------
    mongodb_uri: str = Field(
        default="mongodb://localhost:27017",
        description="MongoDB接続URI。Docker環境では 'mongodb://mongodb:27017'。",
    )
    mongodb_db_name: str = Field(
        default="faq_chatbot",
        description="MongoDBのデータベース名。チャット履歴のセッションが保存される。",
    )

    # -------------------------------------------------------------------------
    # RAG設定
    # -------------------------------------------------------------------------
    top_k: int = Field(
        default=3,
        description="ベクトル類似度検索で返す上位件数。"
        "増やすとコンテキストが豊富になるがノイズも増加する。",
    )
    history_limit: int = Field(
        default=5,
        description="プロンプトに含めるチャット履歴の最大件数。"
        "増やすと文脈理解が向上するがトークン消費が増加する。",
    )

    model_config = {"env_file": ".env", "extra": "ignore"}
