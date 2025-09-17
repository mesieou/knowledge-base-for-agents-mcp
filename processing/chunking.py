
"""
Document chunking using docling HybridChunker
"""
from typing import List
from docling.chunking import HybridChunker
from utils.tokenizer import OpenAITokenizerWrapper


def chunk_documents(documents: List, max_tokens: int = 8191) -> List:
    """Chunk documents using HybridChunker"""
    tokenizer = OpenAITokenizerWrapper()
    chunker = HybridChunker(
        tokenizer=tokenizer,
        max_tokens=max_tokens,
        merge_peers=True,
    )

    all_chunks = []
    for document in documents:
        try:
            chunk_iter = chunker.chunk(dl_doc=document)
            chunks = list(chunk_iter)
            all_chunks.extend(chunks)
            print(f"✅ Chunked document into {len(chunks)} chunks")
        except Exception as e:
            print(f"❌ Error chunking document: {e}")
            continue

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
