"""
Thin MCP tool wrapper - orchestrates extraction, chunking, and embedding
"""
import os
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from processing import extract_documents, chunk_documents, create_embeddings_table, embed_and_store_chunks

load_dotenv()


def load_documents(
    sources: Optional[List[str]] = None,
    table_name: Optional[str] = None,
    max_tokens: int = 8191
) -> Dict[str, Any]:
    """
    Thin wrapper that orchestrates the document processing pipeline
    """
    # Read environment variables
    database_url = os.getenv("DATABASE_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    env_sources = os.getenv("SOURCES")

    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Parse sources
    if sources is None:
        if not env_sources:
            raise ValueError("SOURCES environment variable or sources parameter is required")
        sources = [s.strip() for s in env_sources.split(",") if s.strip()]

    if not sources:
        raise ValueError("At least one source must be provided")

    # Step 1: Extract documents
    print("🔍 Extracting documents...")
    documents = extract_documents(sources)

    # Step 2: Chunk documents
    print("✂️ Chunking documents...")
    chunks = chunk_documents(documents, max_tokens)

    # Step 3: Create table
    print("🗄️ Creating database table...")
    actual_table_name = create_embeddings_table(database_url, table_name)

    # Step 4: Generate embeddings and store
    print("🤖 Generating embeddings and storing...")
    row_count = embed_and_store_chunks(chunks, database_url, actual_table_name, openai_api_key)

    return {
        "table_name": actual_table_name,
        "row_count": row_count,
        "stored_files": sources[:len(documents)],  # Only successful extractions
        "total_sources": len(sources),
        "successful_sources": len(documents),
        "failed_sources": len(sources) - len(documents)
    }


# For testing
if __name__ == "__main__":
    import sys

    try:
        result = load_documents()
        print("✅ Pipeline Result:", result)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
