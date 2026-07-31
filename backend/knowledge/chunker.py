"""
文本分块和向量化引擎
将处理后的文档文本切分为适合检索的 chunk，并写入 ChromaDB。
"""
import json
import re

from loguru import logger


class DocumentChunker:
    """
    智能文档分块器
    按段落/标题边界分块，保持语义完整性。
    """

    def __init__(self, chunk_size: int = 1200, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, metadata: dict | None = None) -> list[dict]:
        """
        将文本分块，返回 [{text, char_count, chunk_index, metadata}, ...]
        """
        if not text or not text.strip():
            return []

        meta = metadata or {}

        # 按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current_chunk = []
        current_len = 0
        chunk_idx = 0

        for para in paragraphs:
            para_len = len(para)

            # 如果当前段落自己就超过 chunk_size，按句号分割
            if para_len > self.chunk_size:
                if current_chunk:
                    chunks.append(self._make_chunk(current_chunk, chunk_idx, meta))
                    chunk_idx += 1
                    current_chunk = []
                    current_len = 0
                sub_chunks = self._split_long_paragraph(para)
                for sc in sub_chunks:
                    chunks.append(self._make_chunk([sc], chunk_idx, meta))
                    chunk_idx += 1
                continue

            # 添加到当前 chunk
            if current_len + para_len + 2 > self.chunk_size and current_chunk:
                chunks.append(self._make_chunk(current_chunk, chunk_idx, meta))
                chunk_idx += 1
                # 重叠：保留最后一段
                overlap_text = current_chunk[-1] if current_chunk else ""
                current_chunk = [overlap_text] if len(overlap_text) < self.chunk_overlap else []
                current_len = len(overlap_text) if current_chunk else 0

            current_chunk.append(para)
            current_len += para_len + 2

        # 最后一个 chunk
        if current_chunk:
            chunks.append(self._make_chunk(current_chunk, chunk_idx, meta))

        logger.info(f"分块完成: {len(chunks)} chunks from {len(text)} chars")
        return chunks

    def _make_chunk(self, paragraphs: list[str], index: int, meta: dict) -> dict:
        text = "\n\n".join(paragraphs)
        return {
            "text": text,
            "char_count": len(text),
            "chunk_index": index,
            "metadata": {**meta, "chunk_index": index},
        }

    def _split_long_paragraph(self, text: str) -> list[str]:
        """将超长段落按句号分割"""
        sentences = re.split(r'(?<=[。.!！?？])\s*', text)
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) > self.chunk_size and current:
                chunks.append(current.strip())
                current = s
            else:
                current += s
        if current.strip():
            chunks.append(current.strip())
        return chunks or [text]


class KnowledgeEmbedder:
    """
    知识库向量化引擎
    将分块后的文本写入 ChromaDB user_knowledge collection。
    """

    def __init__(self):
        self._chunker = DocumentChunker()

    def embed_document(
        self,
        doc_id: int,
        text: str,
        filename: str,
        file_type: str,
        doc_category: str = "",
        images: list = None,
        tables: list = None,
        has_latex: bool = False,
    ) -> int:
        """
        将文档分块并写入 ChromaDB。
        返回 chunk 数量
        """
        from knowledge.vector_store import vector_store
        vector_store._ensure_initialized()

        metadata = {
            "doc_id": str(doc_id),
            "filename": filename,
            "file_type": file_type,
            "doc_category": doc_category,
            "has_latex": str(has_latex),
        }

        # 如果有图片，生成 AI 标注并加入首个 chunk 的 metadata
        from knowledge.document_processor import generate_image_caption
        image_refs = []
        if images:
            for img in images[:20]:  # 最多处理20张图片
                caption = generate_image_caption(img.get("path", ""))
                img["caption"] = caption
                image_refs.append(img)
            # 在 metadata 中存储图片引用
            metadata["image_count"] = str(len(image_refs))
            metadata["images"] = json.dumps(image_refs, ensure_ascii=False)[:2000]

        # 如果有表格，也存储在 metadata 中
        if tables:
            metadata["table_count"] = str(len(tables))
            metadata["tables_preview"] = json.dumps(tables[:3], ensure_ascii=False)[:1500]

        chunks = self._chunker.chunk(text, metadata)
        if not chunks:
            return 0

        # 批量写入 ChromaDB
        try:
            collection = vector_store._client.get_or_create_collection(
                name="user_knowledge",
                metadata={"hnsw:space": "cosine"},
            )

            # Upsert chunks
            ids = []
            documents = []
            metadatas = []
            for c in chunks:
                chunk_id = f"doc{doc_id}_chunk{c['chunk_index']}"
                ids.append(chunk_id)
                documents.append(c['text'])
                metadatas.append(c['metadata'])

            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

            logger.info(f"已写入 {len(chunks)} 个 chunk 到 ChromaDB user_knowledge")
            return len(chunks)

        except Exception as e:
            logger.error(f"写入 ChromaDB 失败: {e}")
            raise

    def delete_document_chunks(self, doc_id: int) -> None:
        """从 ChromaDB 中删除指定文档的所有 chunk"""
        try:
            from knowledge.vector_store import vector_store
            vector_store._ensure_initialized()

            collection = vector_store._client.get_collection("user_knowledge")
            # 按 metadata 过滤删除
            collection.delete(where={"doc_id": str(doc_id)})
            logger.info(f"已删除 doc_id={doc_id} 的所有 chunk")
        except Exception as e:
            logger.error(f"删除 chunk 失败: {e}")

    def estimate_tokens(self, text: str) -> int:
        """粗略估算 token 数（中文字符≈1.5 tokens, 英文≈0.75）"""
        chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
        other = len(text) - chinese
        return int(chinese * 1.5 + other * 0.75)


# 全局单例
knowledge_embedder = KnowledgeEmbedder()
