
"""
 Document chunking using docling HybridChunker with optimal settings for semantic search
"""
from typing import List
from docling.chunking import HybridChunker
from utils.tokenizer import OpenAITokenizerWrapper
import logging

logger = logging.getLogger(__name__)


def chunk_documents(
    documents: List,
    max_tokens: int = 512,  # Optimal for semantic search and RAG
    merge_peers: bool = True,  # Merge related content at same hierarchy level
    min_chunk_words: int = 15  # Filter out chunks that are too small
) -> List:
    """
    Chunk documents using HybridChunker with optimal settings for semantic search.

    Args:
        documents: List of DoclingDocument objects
        max_tokens: Maximum tokens per chunk (default: 512 for semantic search)
                   - 512: Optimal for semantic search, good context windows
                   - 1024: For longer context needs
                   - 256: For very granular search
        merge_peers: Whether to merge peer elements (same hierarchy level)
        min_chunk_words: Minimum words per chunk (filters out tiny chunks)

    Returns:
        List of DoclingChunk objects (filtered for quality)
    """
    # Use OpenAI tokenizer to match embedding model (text-embedding-3-small)
    tokenizer = OpenAITokenizerWrapper(model_name="cl100k_base")

    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=max_tokens,
        merge_peers=merge_peers,  # Merge related content
    )

    all_chunks = []
    filtered_count = 0

    for doc_idx, document in enumerate(documents, 1):
        try:
            chunk_iter = chunker.chunk(dl_doc=document)
            chunks = list(chunk_iter)

            # Filter out chunks that are too small (likely navigation/buttons)
            filtered_chunks = [c for c in chunks if len(c.text.split()) >= min_chunk_words]
            filtered_count += len(chunks) - len(filtered_chunks)

            all_chunks.extend(filtered_chunks)
            logger.info(
                f"✅ Document {doc_idx}/{len(documents)}: "
                f"Chunked into {len(filtered_chunks)} chunks "
                f"(filtered {len(chunks) - len(filtered_chunks)} tiny chunks, "
                f"avg {sum(len(c.text.split()) for c in filtered_chunks) // len(filtered_chunks) if filtered_chunks else 0} words/chunk)"
            )
        except Exception as e:
            logger.error(f"❌ Error chunking document {doc_idx}: {e}")
            continue

    logger.info(
        f"📊 Total chunks: {len(all_chunks)} "
        f"(filtered out {filtered_count} tiny chunks, "
        f"avg {sum(len(c.text.split()) for c in all_chunks) // len(all_chunks) if all_chunks else 0} words/chunk)"
    )

    return all_chunks


# For testing
if __name__ == "__main__":
    from docling.document_converter import DocumentConverter

    # Test chunking
    converter = DocumentConverter()
    result = converter.convert("https://arxiv.org/pdf/2408.09869")

    if result.document:
        chunks = chunk_documents([result.document])
        print(f"Generated {len(chunks)} chunks")
