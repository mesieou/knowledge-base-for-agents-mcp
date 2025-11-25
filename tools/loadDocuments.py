"""
Thin MCP tool wrapper - orchestrates extraction, chunking, and embedding
"""
import os
import logging
import sys
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from processing import extract_documents, chunk_documents, create_embeddings_table, embed_and_store_chunks

load_dotenv()

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Force stdout for Railway
    ]
)
logger = logging.getLogger(__name__)


def load_documents(
    business_id: str,
    sources: Optional[List[str]] = None,
    table_name: str = "knowledge_base",
    max_tokens: int = 8191,
    crawl_internal: bool = True,
    database_url: Optional[str] = None,
    category: str = "website"
) -> Dict[str, Any]:
    """
    Thin wrapper that orchestrates the document processing pipeline into knowledge_base table
    """
    # Validate required business_id
    if not business_id:
        raise ValueError("business_id is required and cannot be None or empty")

    # Validate business_id is a valid UUID
    import uuid
    try:
        uuid.UUID(business_id)
    except ValueError:
        raise ValueError(f"business_id must be a valid UUID format, got: {business_id}")

    # Use provided database_url or fall back to environment variable
    if not database_url:
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL must be provided as parameter or environment variable")

    # OpenAI API key is still required from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Get sources from environment if not provided
    env_sources = os.getenv("SOURCES")

    # Parse sources
    if sources is None:
        if not env_sources:
            raise ValueError("SOURCES environment variable or sources parameter is required")
        sources = [s.strip() for s in env_sources.split(",") if s.strip()]

    if not sources:
        raise ValueError("At least one source must be provided")

    # Log business context
    logger.info(f"🏢 Processing for business ID: {business_id}")
    logger.info(f"📂 Category: {category}")

    # Step 1: Extract documents
    logger.info(f"🔍 Step 1/4: Extracting {len(sources)} documents (crawl_internal={crawl_internal})...")
    documents = extract_documents(sources, crawl_internal=crawl_internal)
    logger.info(f"✅ Extracted {len(documents)} documents")

    # Step 2: Chunk documents
    logger.info(f"✂️ Step 2/4: Chunking documents (max_tokens: {max_tokens})...")
    chunks = chunk_documents(documents, max_tokens)
    logger.info(f"✅ Created {len(chunks)} chunks")

    # Step 3: Create table (always knowledge_base)
    logger.info("🗄️ Step 3/4: Creating knowledge_base table...")
    actual_table_name = create_embeddings_table(database_url, "knowledge_base")
    logger.info(f"✅ Table created: {actual_table_name}")

    # Step 4: Generate embeddings and store
    logger.info(f"🤖 Step 4/4: Generating embeddings for {len(chunks)} chunks...")
    row_count = embed_and_store_chunks(chunks, database_url, actual_table_name, openai_api_key, business_id, category)
    logger.info(f"✅ Pipeline complete: {row_count} chunks stored")

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
