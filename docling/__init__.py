"""
Document processing pipeline using docling
"""
from .extraction import extract_documents, extract_from_sitemap
from .chunking import chunk_documents
from .embedding import create_embeddings_table, embed_and_store_chunks

__all__ = [
    "extract_documents",
    "extract_from_sitemap",
    "chunk_documents",
    "create_embeddings_table",
    "embed_and_store_chunks"
]
