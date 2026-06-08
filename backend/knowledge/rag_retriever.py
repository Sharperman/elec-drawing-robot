"""
RAG 检索器：从向量数据库检索相关规范片段供 Agent 使用
"""
from typing import Optional

from loguru import logger

from knowledge.vector_store import vector_store


class RAGRetriever:
    """规范知识库 RAG 检索器"""

    def __init__(self) -> None:
        from config import settings
        self._standards_collection = settings.CHROMA_COLLECTION_STANDARDS
        self._symbols_collection = settings.CHROMA_COLLECTION_SYMBOLS

    async def retrieve_standards(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[str]:
        """
        检索与查询最相关的规范片段

        Args:
            query: 用户查询文本
            top_k: 返回片段数量

        Returns:
            相关规范文本片段列表
        """
        try:
            results = await vector_store.similarity_search(
                collection_name=self._standards_collection,
                query=query,
                top_k=top_k,
            )
            fragments = []
            for item in results:
                if item["score"] > 0.5:  # 仅返回相似度 > 0.5 的片段
                    fragments.append(item["document"])
            return fragments
        except Exception as e:
            logger.warning(f"RAG retrieval failed for standards: {e}")
            return []

    async def retrieve_symbols(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> list[dict]:
        """
        检索与查询最相关的图元符号

        Args:
            query: 用户查询文本
            top_k: 返回符号数量
            category: 分类过滤

        Returns:
            相关符号信息字典列表
        """
        try:
            where = {"category": category} if category else None
            results = await vector_store.similarity_search(
                collection_name=self._symbols_collection,
                query=query,
                top_k=top_k,
                where=where,
            )
            symbols = []
            for item in results:
                if item["score"] > 0.4:
                    symbols.append(
                        {
                            "document": item["document"],
                            "metadata": item["metadata"],
                            "score": item["score"],
                        }
                    )
            return symbols
        except Exception as e:
            logger.warning(f"RAG retrieval failed for symbols: {e}")
            return []

    async def build_context(self, query: str, include_knowledge: bool = True) -> str:
        """
        构建完整的规范上下文字符串，注入 Agent Prompt

        Args:
            query: 用户查询
            include_knowledge: 是否检索用户知识库（默认 True）

        Returns:
            格式化的上下文字符串
        """
        standards_fragments = await self.retrieve_standards(query, top_k=3)
        symbol_results = await self.retrieve_symbols(query, top_k=3)

        context_parts: list[str] = []

        if standards_fragments:
            context_parts.append("【相关绘图规范】")
            for i, frag in enumerate(standards_fragments, 1):
                context_parts.append(f"{i}. {frag}")

        if symbol_results:
            context_parts.append("\n【相关图元符号】")
            for item in symbol_results:
                meta = item.get("metadata", {})
                context_parts.append(
                    f"- symbol_id: {meta.get('symbol_id', 'N/A')} | "
                    f"名称: {meta.get('name', 'N/A')} | "
                    f"描述: {item['document'][:100]}"
                )

        # 用户知识库检索
        if include_knowledge:
            knowledge_items = await self.retrieve_knowledge(query, top_k=3)
            if knowledge_items:
                context_parts.append("\n【用户知识库（设计手册/规程/策划文件）】")
                for item in knowledge_items:
                    meta = item.get("metadata", {})
                    source = meta.get("filename", "未知文档")
                    context_parts.append(
                        f"📄 {source} (score={item['score']:.2f}):\n"
                        f"{item['document'][:300]}"
                    )

        return "\n".join(context_parts) if context_parts else "暂无相关规范信息"

    async def retrieve_knowledge(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """
        从用户知识库检索相关文档片段

        Args:
            query: 查询文本
            top_k: 返回片段数

        Returns:
            [{document, metadata, score}, ...]
        """
        try:
            results = await vector_store.similarity_search(
                collection_name="user_knowledge",
                query=query,
                top_k=top_k,
            )
            return [
                {"document": r["document"], "metadata": r.get("metadata", {}), "score": r["score"]}
                for r in results if r["score"] > 0.4
            ]
        except Exception as e:
            logger.warning(f"Knowledge retrieval failed: {e}")
            return []

    async def index_standard(self, standard_id: int, content: str) -> None:
        """
        将规范文本索引到向量数据库

        Args:
            standard_id: 规范 ID
            content: 规范文本内容
        """
        # 按段落分割文本
        paragraphs = [p.strip() for p in content.split("\n") if len(p.strip()) > 20]
        if not paragraphs:
            return

        ids = [f"standard_{standard_id}_{i}" for i in range(len(paragraphs))]
        metadatas = [{"standard_id": standard_id, "chunk_index": i} for i in range(len(paragraphs))]

        await vector_store.add_documents(
            collection_name=self._standards_collection,
            documents=paragraphs,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Indexed {len(paragraphs)} paragraphs for standard {standard_id}")

    async def index_symbol(self, symbol_id: str, name: str, description: str, category: str) -> None:
        """
        将图元符号描述索引到向量数据库

        Args:
            symbol_id: 符号 ID
            name: 符号名称
            description: 符号描述
            category: 分类
        """
        text = f"{name}：{description}"
        await vector_store.add_documents(
            collection_name=self._symbols_collection,
            documents=[text],
            metadatas=[{"symbol_id": symbol_id, "name": name, "category": category}],
            ids=[f"symbol_{symbol_id}"],
        )


# 全局单例
rag_retriever = RAGRetriever()
