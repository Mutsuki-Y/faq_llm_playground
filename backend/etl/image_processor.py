"""Image processing module for the ETL pipeline."""

import uuid
from pathlib import Path

from llm.base import LLMClientBase
from models import ContentType, ImageDocument, ImageMetadata

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg"}


class ImageProcessor:
    """画像ファイルを処理してImageDocumentを生成するクラス。"""

    def __init__(self, llm_client: LLMClientBase) -> None:
        self._llm_client = llm_client

    async def process_image(self, image_path: Path) -> ImageDocument:
        """画像からマルチモーダルAPIで説明テキストを生成し、ImageDocumentを返す。

        Args:
            image_path: 画像ファイルのパス

        Returns:
            生成されたImageDocument

        Raises:
            FileNotFoundError: 画像ファイルが存在しない場合
            ValueError: サポートされていない画像形式の場合
        """
        if not image_path.exists():
            raise FileNotFoundError(f"画像ファイルが見つかりません: {image_path}")

        if image_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"サポートされていない画像形式です: {image_path.suffix}. "
                f"対応形式: {SUPPORTED_EXTENSIONS}"
            )

        description = await self._llm_client.describe_image(image_path)

        return ImageDocument(
            doc_id=str(uuid.uuid4()),
            description=description,
            metadata=ImageMetadata(
                image_path=str(image_path),
                source_file=image_path.name,
                content_type=ContentType.IMAGE,
            ),
        )

    def list_images(self, directory: Path) -> list[Path]:
        """ディレクトリ内の対象画像ファイルを一覧する。

        Args:
            directory: 画像ディレクトリのパス

        Returns:
            対象画像ファイルのパスリスト
        """
        if not directory.exists():
            return []

        return [
            p for p in sorted(directory.iterdir())
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
