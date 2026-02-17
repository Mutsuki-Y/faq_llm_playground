"""ChromaDB ベースのベクトルストアモジュール。

ChromaDB をラップし、FAQ チャンクと画像ドキュメントの保存・検索を提供する。
ファイルベースで動作するため、別途サーバープロセスを起動する必要がない。

Embedding生成はsentence-transformersの多言語モデル（paraphrase-multilingual-MiniLM-L12-v2）を
使用するため、外部APIは不要。日本語テキストの類似度検索に対応。

データの永続化先は config.chroma_persist_dir で指定され、
docker-compose.yml でホストの data/chroma/ にマウントされる。

検索アルゴリズム:
    - HNSW（Hierarchical Navigable Small World）インデックスを使用
    - コサイン類似度で類似度を計算
    - ChromaDB の距離 = 1 - コサイン類似度 なので、score = 1 - distance に変換
"""

import chromadb
from chromadb.utils import embedding_functions
from config import AppConfig
from models import Chunk, ContentType, ImageDocument, SearchResult


class VectorStore:
    """ChromaDBをラップし、Chunk/ImageDocumentの保存とコサイン類似度検索を提供する。

    Embedding生成は多言語対応のsentence-transformersモデルを使用。
    """

    COLLECTION_NAME = "faq_documents"
    EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, config: AppConfig) -> None:
        self._client = chromadb.PersistentClient(path=config.chroma_persist_dir)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.EMBEDDING_MODEL,
        )
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._ef,
        )

    async def add_chunks(self, chunks: list[Chunk]) -> None:
        """Chunkをストアに追加する。Embeddingはローカルで自動生成される。"""
        if not chunks:
            return
        self._collection.add(
            ids=[c.chunk_id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "source_file": c.metadata.source_file,
                    "sheet_name": c.metadata.sheet_name,
                    "row_number": c.metadata.row_number,
                    "parent_category": c.metadata.parent_category,
                    "child_category": c.metadata.child_category,
                    "title": c.metadata.title,
                    "content_type": c.metadata.content_type.value,
                }
                for c in chunks
            ],
        )

    async def add_image_documents(self, docs: list[ImageDocument]) -> None:
        """ImageDocumentをストアに追加する。Embeddingはローカルで自動生成される。"""
        if not docs:
            return
        self._collection.add(
            ids=[d.doc_id for d in docs],
            documents=[d.description for d in docs],
            metadatas=[
                {
                    "image_path": d.metadata.image_path,
                    "source_file": d.metadata.source_file,
                    "description": d.description,
                    "content_type": d.metadata.content_type.value,
                }
                for d in docs
            ],
        )

    async def search(self, query_text: str, top_k: int = 3) -> list[SearchResult]:
        """テキストクエリでコサイン類似度検索する。

        Embeddingはローカルで自動生成される。
        ChromaDBのコサイン距離は distance = 1 - similarity なので、
        score = 1 - distance で類似度スコアに変換する。
        """
        count = self._collection.count()
        if count == 0:
            return []

        effective_k = min(top_k, count)
        results = self._collection.query(
            query_texts=[query_text],
            n_results=effective_k,
            include=["documents", "metadatas", "distances"],
        )

        search_results: list[SearchResult] = []
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            score = 1.0 - dist
            content_type = ContentType(meta.get("content_type", "text"))
            search_results.append(
                SearchResult(
                    content=doc or "",
                    score=score,
                    metadata=meta,
                    content_type=content_type,
                )
            )

        return search_results

    def is_empty(self) -> bool:
        """ストアにデータが存在するか確認する。"""
        return self._collection.count() == 0
