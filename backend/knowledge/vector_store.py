"""
ChromaDB 向量数据库 — 全部使用 ChromaDB 本地默认模型 (all-MiniLM-L6-v2)
不依赖外部 Embedding API
"""

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger


class VectorStore:
    """ChromaDB 向量数据库管理类（纯本地 embedding）"""

    def __init__(self) -> None:
        self._client: chromadb.PersistentClient | None = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """初始化 ChromaDB（使用内置默认 embedding 模型）"""
        if self._initialized:
            return

        from config import settings

        try:
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PATH,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            # 预创建 Collection（不指定 embedding_function → 使用 ChromaDB 默认本地模型）
            for name in [
                settings.CHROMA_COLLECTION_STANDARDS,
                settings.CHROMA_COLLECTION_SYMBOLS,
                "user_knowledge",
            ]:
                self._client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"},
                )

            self._initialized = True
            logger.info(f"VectorStore initialized (local embedding) at {settings.CHROMA_PATH}")
        except Exception as e:
            logger.error(f"VectorStore initialization failed: {e}")
            raise

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("VectorStore not initialized. Call initialize() first.")

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """
        向 Collection 添加文档（由 ChromaDB 自动向量化）
        """
        self._ensure_initialized()
        collection = self._client.get_or_create_collection(collection_name)  # type: ignore
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        logger.debug(f"Added {len(documents)} documents to '{collection_name}'")

    async def similarity_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
    ) -> list[dict]:
        """
        语义相似性搜索（查询文本由 ChromaDB 自动向量化）
        """
        self._ensure_initialized()
        collection = self._client.get_collection(collection_name)  # type: ignore

        kwargs: dict = {
            "query_texts": [query],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = collection.query(**kwargs)

        output: list[dict] = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, distances):
            output.append({
                "document": doc,
                "metadata": meta,
                "distance": dist,
                "score": 1.0 - dist,
            })

        return output

    def delete_collection(self, collection_name: str) -> None:
        self._ensure_initialized()
        try:
            self._client.delete_collection(collection_name)  # type: ignore
            logger.info(f"Collection '{collection_name}' deleted")
        except Exception as e:
            logger.warning(f"Failed to delete collection '{collection_name}': {e}")

    def get_chunks_by_doc(self, doc_id: int) -> list[dict]:
        """获取指定文档的所有分块"""
        self._ensure_initialized()
        try:
            collection = self._client.get_collection("user_knowledge")
            result = collection.get(where={"doc_id": str(doc_id)})
            chunks = []
            ids = result.get("ids", [])
            docs = result.get("documents", [])
            metas = result.get("metadatas", [])
            for i in range(len(ids)):
                chunks.append({
                    "id": ids[i],
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                })
            return chunks
        except Exception as e:
            logger.warning(f"获取文档分块失败: {e}")
            return []


# 全局单例
vector_store = VectorStore()
