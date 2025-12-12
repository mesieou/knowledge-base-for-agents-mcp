"""
Document processing pipeline using docling library
"""
from .extraction import extract_documents, extract_from_sitemap
from .chunking import chunk_documents
from .embedding import (
    create_embeddings_table,
    embed_and_store_chunks,
    create_or_update_source_transactional,
    embed_and_store_chunks_transactional,
    infer_source_type
)
from .query import query_knowledge

__all__ = [
    "extract_documents",
    "extract_from_sitemap",
    "chunk_documents",
    "create_embeddings_table",
    "embed_and_store_chunks",
    "create_or_update_source_transactional",
    "embed_and_store_chunks_transactional",
    "infer_source_type",
    "query_knowledge"
]
