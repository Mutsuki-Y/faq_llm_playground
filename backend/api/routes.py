"""FastAPI ルーター定義。

FAQ チャットボットの REST API エンドポイントを定義する。
各エンドポイントは Swagger UI（/docs）で自動ドキュメント化される。

エンドポイント一覧:
    POST /api/chat    - ユーザーの質問に対してRAGパターンで回答を生成
    POST /api/ingest  - FAQデータ・画像の取り込み（ETLパイプライン実行）
    POST /api/upload  - ファイルアップロード＋自動取り込み
    GET  /api/health  - システムヘルスチェック
    POST /api/session - 新しいチャットセッションの作成
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from models import ChatRequest, ChatResponse, IngestResult
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["FAQ Chatbot API"])


# =============================================================================
# レスポンスモデル（Swagger UI用に詳細なスキーマを定義）
# =============================================================================

class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス。"""
    status: str = Field(..., description="システムステータス", json_schema_extra={"example": "ok"})
    message: str = Field(..., description="ステータスメッセージ", json_schema_extra={"example": "FAQ Chatbot is running"})


class SessionResponse(BaseModel):
    """セッション作成レスポンス。"""
    session_id: str = Field(
        ...,
        description="新しく発行されたセッションID（UUID v4）",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )


class SessionListItem(BaseModel):
    """セッション一覧の1項目。"""
    session_id: str = Field(..., description="セッションID")
    created_at: str = Field(..., description="作成日時（ISO 8601）")
    message_count: int = Field(..., description="メッセージ数")
    last_message: str = Field(..., description="最後のメッセージ（プレビュー）")


class SessionListResponse(BaseModel):
    """セッション一覧レスポンス。"""
    sessions: list[SessionListItem] = Field(..., description="セッション一覧（新しい順）")


class SessionHistoryResponse(BaseModel):
    """セッション履歴レスポンス。"""
    session_id: str = Field(..., description="セッションID")
    messages: list = Field(..., description="全メッセージ履歴")


class DeleteSessionResponse(BaseModel):
    """セッション削除レスポンス。"""
    success: bool = Field(..., description="削除成功フラグ")
    message: str = Field(..., description="結果メッセージ")


# =============================================================================
# サービス依存性注入
# =============================================================================

# main.py の lifespan で初期化されたサービスインスタンスを保持する。
# FastAPI の Depends() ではなくモジュールレベル変数を使用するのは、
# サービスの初期化が非同期 lifespan 内で行われるため。
_chat_service = None
_etl_pipeline = None
_session_manager = None
_config = None


def set_dependencies(chat_service, etl_pipeline, session_manager, config=None):
    """サービス依存性を設定する（main.py の lifespan から呼び出される）。

    Args:
        chat_service: ChatService インスタンス（RAGパイプライン）
        etl_pipeline: ETLPipeline インスタンス（データ取り込み）
        session_manager: SessionManager インスタンス（セッション管理）
        config: AppConfig インスタンス（設定）
    """
    global _chat_service, _etl_pipeline, _session_manager, _config
    _chat_service = chat_service
    _etl_pipeline = etl_pipeline
    _session_manager = session_manager
    _config = config


# =============================================================================
# エンドポイント
# =============================================================================

@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="質問に対してRAGで回答を生成",
    description="""
ユーザーの質問テキストとセッションIDを受け取り、RAGパイプラインで回答を生成する。

**処理フロー:**
1. 質問テキストをEmbeddingに変換
2. ベクトルストアでコサイン類似度検索（上位k件）
3. 同一セッションの直近N件のチャット履歴を取得
4. システムプロンプト + コンテキスト + 履歴 + 質問でプロンプトを構築
5. LLMで回答を生成
6. 質問と回答をセッション履歴に保存

**エラー時の挙動:**
- ベクトルストアが空の場合: 「ナレッジベースが未構築です」メッセージを返却
- LLM API失敗時: 「回答の生成に失敗しました」メッセージを返却
- バリデーション失敗時: HTTP 422 + 詳細エラー
    """,
    responses={
        200: {"description": "回答の生成に成功"},
        422: {"description": "リクエストバリデーションエラー（question または session_id の欠落・不正）"},
    },
)
async def chat(request: ChatRequest) -> ChatResponse:
    return await _chat_service.answer(request.question, request.session_id)


@router.post(
    "/ingest",
    response_model=IngestResult,
    summary="FAQデータ・画像の取り込み",
    description="""
ETLパイプラインを実行し、FAQデータと画像をベクトルストアに取り込む。

**処理内容:**
1. `FAQ_DATA_DIR`（デフォルト: `./data/faq/`）内の全 .xlsx ファイルを読み込み
2. ステータスが「公開」の行のみをフィルタリング
3. タイトル+本文を結合してチャンク化し、Embeddingを生成してChromaDBに保存
4. `IMAGE_DATA_DIR`（デフォルト: `./data/images/`）内のPNG/JPEG画像を処理
5. マルチモーダルLLMで画像の説明テキストを生成し、Embeddingを生成して保存

**リトライ:** Embedding API失敗時は1回リトライし、それでも失敗した場合はエラーを記録して次へ進む。

**注意:** 大量のデータがある場合、処理に時間がかかることがある。
    """,
    responses={
        200: {"description": "取り込み処理完了（error_count > 0 の場合は一部失敗あり）"},
    },
)
async def ingest() -> IngestResult:
    return await _etl_pipeline.ingest_all()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="ヘルスチェック",
    description="システムの稼働状態を確認する。コンテナのヘルスチェックやロードバランサーの監視に使用。",
    responses={
        200: {"description": "システム正常稼働中"},
    },
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", message="FAQ Chatbot is running")


@router.post(
    "/session",
    response_model=SessionResponse,
    summary="新しいチャットセッションを作成",
    description="""
新しいチャットセッションを作成し、一意のセッションIDを返す。

フロントエンドはページ読み込み時にこのエンドポイントを呼び出し、
以降の `/api/chat` リクエストに取得したセッションIDを付与する。

セッションIDはUUID v4形式で、MongoDBにセッションドキュメントとして保存される。
チャット履歴はセッション単位で管理される。
    """,
    responses={
        200: {"description": "セッション作成成功"},
    },
)
async def create_session() -> SessionResponse:
    session_id = await _session_manager.create_session()
    return SessionResponse(session_id=session_id)


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="全セッション一覧を取得",
    description="""
全セッションの一覧を新しい順で取得する。

各セッションには以下の情報が含まれる:
- session_id: セッションID
- created_at: 作成日時
- message_count: メッセージ数
- last_message: 最後のメッセージのプレビュー（最大50文字）
    """,
    responses={
        200: {"description": "セッション一覧取得成功"},
    },
)
async def get_sessions() -> SessionListResponse:
    sessions = await _session_manager.get_all_sessions()
    return SessionListResponse(sessions=sessions)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionHistoryResponse,
    summary="セッションの全履歴を取得",
    description="""
指定されたセッションIDの全メッセージ履歴を取得する。

過去のセッションを再開する際に使用する。
    """,
    responses={
        200: {"description": "履歴取得成功"},
        404: {"description": "セッションが見つからない"},
    },
)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    messages = await _session_manager.get_full_history(session_id)
    from fastapi import HTTPException
    if not messages:
        # セッションが存在しない、または空の場合
        doc = await _session_manager._sessions.find_one({"session_id": session_id})
        if doc is None:
            raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    return SessionHistoryResponse(
        session_id=session_id,
        messages=[m.model_dump() for m in messages],
    )


@router.delete(
    "/sessions/{session_id}",
    response_model=DeleteSessionResponse,
    summary="セッションを削除",
    description="""
指定されたセッションIDのセッションを削除する。

削除されたセッションは復元できない。
    """,
    responses={
        200: {"description": "削除成功"},
        404: {"description": "セッションが見つからない"},
    },
)
async def delete_session(session_id: str) -> DeleteSessionResponse:
    success = await _session_manager.delete_session(session_id)
    from fastapi import HTTPException
    if not success:
        raise HTTPException(status_code=404, detail="セッションが見つかりません")
    
    return DeleteSessionResponse(
        success=True,
        message="セッションを削除しました",
    )


class UploadResponse(BaseModel):
    """ファイルアップロードレスポンス。"""
    filename: str = Field(..., description="アップロードされたファイル名")
    file_type: str = Field(..., description="ファイル種別（excel / image）")
    ingest_result: IngestResult = Field(..., description="取り込み結果")


ALLOWED_EXCEL_EXTENSIONS = {".xlsx"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="ファイルアップロード＋自動取り込み",
    description="""
Excelファイルまたは画像ファイルをアップロードし、自動でETLパイプラインを実行する。

**対応ファイル形式:**
- Excel: .xlsx
- 画像: .png, .jpg, .jpeg

**処理フロー:**
1. ファイルを対応するデータディレクトリに保存
2. ファイル種別に応じてETLパイプラインを実行
3. 取り込み結果を返却
    """,
    responses={
        200: {"description": "アップロード＋取り込み成功"},
        400: {"description": "サポートされていないファイル形式"},
    },
)
async def upload_file(file: UploadFile = File(...)) -> UploadResponse:
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()

    if ext in ALLOWED_EXCEL_EXTENSIONS:
        file_type = "excel"
        dest_dir = Path(_config.faq_data_dir)
    elif ext in ALLOWED_IMAGE_EXTENSIONS:
        file_type = "image"
        dest_dir = Path(_config.image_data_dir)
    else:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"サポートされていないファイル形式です: {ext}。対応形式: .xlsx, .png, .jpg, .jpeg",
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if file_type == "excel":
        result = await _etl_pipeline.ingest_excel(dest_path)
    else:
        result = await _etl_pipeline.ingest_images(dest_dir)

    return UploadResponse(
        filename=filename,
        file_type=file_type,
        ingest_result=result,
    )
