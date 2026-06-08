"""
ChromaDB 向量数据库初始化和操作
"""
import asyncio
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from loguru import logger


class VectorStore:
    """ChromaDB 向量数据库管理类"""

    def __init__(self) -> None:
        self._client: Optional[chromadb.PersistentClient] = None
        self._embeddings: Optional[OpenAIEmbeddings] = None
        self._initialized: bool = False

    async def initialize(self) -> None:
        """初始化 ChromaDB 和 Embedding 模型"""
        if self._initialized:
            return

        from config import settings

        try:
            # 初始化 ChromaDB
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PATH,
                settings=ChromaSettings(anonymized_telemetry=False),
            )

            # 初始化 Embedding 模型
            self._embeddings = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
            )

            # 确保 Collection 存在
            self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_STANDARDS,
                metadata={"hnsw:space": "cosine"},
            )
            self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_SYMBOLS,
                metadata={"hnsw:space": "cosine"},
            )
            self._client.get_or_create_collection(
                name="user_knowledge",
                metadata={"hnsw:space": "cosine"},
            )

            self._initialized = True
            logger.info(f"VectorStore initialized at {settings.CHROMA_PATH}")
        except Exception as e:
            logger.error(f"VectorStore initialization failed: {e}")
            raise

    def _ensure_initialized(self) -> None:
        """确保已初始化"""
        if not self._initialized:
            raise RuntimeError("VectorStore not initialized. Call initialize() first.")

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        将文本列表转换为向量

        Args:
            texts: 待向量化的文本列表

        Returns:
            向量列表
        """
        self._ensure_initialized()
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None, self._embeddings.embed_documents, texts  # type: ignore
        )
        return embeddings

    async def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> None:
        """
        向 Collection 添加文档

        Args:
            collection_name: Collection 名称
            documents: 文档文本列表
            metadatas: 元数据列表
            ids: 文档 ID 列表
        """
        self._ensure_initialized()

        embeddings = await self.embed_texts(documents)
        collection = self._client.get_or_create_collection(collection_name)  # type: ignore

        # ChromaDB upsert 支持重复 ID
        collection.upsert(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        logger.debug(f"Added {len(documents)} documents to collection '{collection_name}'")

    async def similarity_search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        语义相似性搜索

        Args:
            collection_name: Collection 名称
            query: 查询文本
            top_k: 返回最相似的 top_k 条
            where: 元数据过滤条件

        Returns:
            包含 document/metadata/distance 的字典列表
        """
        self._ensure_initialized()

        query_embedding = await self.embed_texts([query])
        collection = self._client.get_collection(collection_name)  # type: ignore

        kwargs: dict = {
            "query_embeddings": query_embedding,
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
            output.append(
                {
                    "document": doc,
                    "metadata": meta,
                    "distance": dist,
                    "score": 1.0 - dist,  # cosine similarity
                }
            )

        return output

    def delete_collection(self, collection_name: str) -> None:
        """清空并删除 Collection"""
        self._ensure_initialized()
        try:
            self._client.delete_collection(collection_name)  # type: ignore
            logger.info(f"Collection '{collection_name}' deleted")
        except Exception as e:
            logger.warning(f"Failed to delete collection '{collection_name}': {e}")

    def get_chunks_by_doc(self, doc_id: int) -> list[dict]:
        """获取指定文档在 ChromaDB 中的所有分块"""
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
