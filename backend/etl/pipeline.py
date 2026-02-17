"""ETL pipeline for ingesting FAQ Excel data and images."""

import logging
from pathlib import Path

from config import AppConfig
from etl.excel_reader import ExcelReader
from etl.image_processor import ImageProcessor
from llm.base import LLMClientBase
from models import IngestResult

logger = logging.getLogger(__name__)


class ETLPipeline:
    """FAQデータと画像を取り込み、ベクトルストアに保存するパイプライン。

    Embedding生成はVectorStore（ChromaDB）がローカルで行うため、
    LLMクライアントは画像説明生成のみに使用する。
    """

    def __init__(self, config: AppConfig, llm_client: LLMClientBase, vector_store) -> None:
        self._config = config
        self._llm_client = llm_client
        self._vector_store = vector_store
        self._excel_reader = ExcelReader()
        self._image_processor = ImageProcessor(llm_client)

    async def ingest_all(self) -> IngestResult:
        """Excelファイルと画像を一括取り込みする。"""
        total_processed = 0
        total_errors = 0
        details_parts: list[str] = []

        # Excel取り込み
        faq_dir = Path(self._config.faq_data_dir)
        xlsx_files = list(faq_dir.glob("*.xlsx")) if faq_dir.exists() else []

        if not xlsx_files:
            msg = f"対象Excelファイルが見つかりません: {faq_dir}"
            logger.warning(msg)
            details_parts.append(msg)
        else:
            for xlsx_path in xlsx_files:
                result = await self.ingest_excel(xlsx_path)
                total_processed += result.total_processed
                total_errors += result.error_count
                details_parts.append(result.details)

        # 画像取り込み
        image_dir = Path(self._config.image_data_dir)
        img_result = await self.ingest_images(image_dir)
        total_processed += img_result.total_processed
        total_errors += img_result.error_count
        details_parts.append(img_result.details)

        summary = f"処理完了: {total_processed}件処理, {total_errors}件エラー"
        logger.info(summary)

        return IngestResult(
            total_processed=total_processed,
            error_count=total_errors,
            details="; ".join(details_parts),
        )

    async def ingest_excel(self, file_path: Path) -> IngestResult:
        """単一Excelファイルの取り込み。Embeddingはローカルで自動生成される。"""
        processed = 0

        try:
            entries = self._excel_reader.read_faq_excel(file_path)
            published = self._excel_reader.filter_published(entries)
            chunks = [self._excel_reader.faq_entry_to_chunk(e) for e in published]

            if not chunks:
                msg = f"{file_path.name}: 公開エントリなし"
                logger.info(msg)
                return IngestResult(total_processed=0, error_count=0, details=msg)

            await self._vector_store.add_chunks(chunks)
            processed = len(chunks)
            msg = f"{file_path.name}: {processed}件のチャンクを取り込み"
            logger.info(msg)

        except FileNotFoundError as e:
            msg = str(e)
            logger.error(msg)
            return IngestResult(total_processed=0, error_count=1, details=msg)
        except Exception as e:
            msg = f"{file_path.name}: 取り込みエラー: {e}"
            logger.error(msg)
            return IngestResult(total_processed=0, error_count=1, details=msg)

        return IngestResult(total_processed=processed, error_count=0, details=msg)

    async def ingest_images(self, directory: Path) -> IngestResult:
        """画像ディレクトリの取り込み。"""
        processed = 0
        errors = 0
        image_paths = self._image_processor.list_images(directory)

        if not image_paths:
            msg = f"対象画像ファイルが見つかりません: {directory}"
            logger.info(msg)
            return IngestResult(total_processed=0, error_count=0, details=msg)

        for image_path in image_paths:
            try:
                doc = await self._image_processor.process_image(image_path)
                await self._vector_store.add_image_documents([doc])
                processed += 1
                logger.info(f"画像を取り込み: {image_path.name}")

            except Exception as e:
                errors += 1
                logger.error(f"画像処理エラー ({image_path.name}): {e}")

        msg = f"画像: {processed}件取り込み, {errors}件エラー"
        logger.info(msg)
        return IngestResult(total_processed=processed, error_count=errors, details=msg)
