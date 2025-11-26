"""
Thin MCP tool wrapper - orchestrates extraction, chunking, and embedding
"""
import os
import logging
import sys
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

from processing import extract_documents, chunk_documents, create_embeddings_table, embed_and_store_chunks
from processing.embedding import infer_source_type, create_or_update_source, mark_source_loaded

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
    category: str = "website",
    description: str = None
) -> Dict[str, Any]:
    """
    Load documents with source tracking

    NEW: Creates entries in both knowledge_sources (tracking) and knowledge_base (data)
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

    # Create knowledge_base and knowledge_sources tables
    logger.info("🗄️ Creating database tables...")
    actual_table_name = create_embeddings_table(database_url, "knowledge_base")
    logger.info(f"✅ Tables created: {actual_table_name}")

    # Results tracking
    all_results = []
    total_entries_created = 0

    # Process each source
    for source_url in sources:
        logger.info(f"📄 Processing source: {source_url}")

        try:
            # Step 1: Create/update source tracking record
            logger.info("📝 Creating source tracking record...")
            source_type = infer_source_type(source_url)
            source_id = create_or_update_source(
                database_url=database_url,
                business_id=business_id,
                source_url=source_url,
                category=category,
                source_type=source_type,
                crawl_internal=crawl_internal,
                description=description
            )
            logger.info(f"✓ Source ID: {source_id}")

            # Step 2: Extract documents
            logger.info(f"🔍 Extracting documents from {source_type}...")
            documents = extract_documents([source_url], crawl_internal=crawl_internal)
            logger.info(f"✅ Extracted {len(documents)} documents")

            # Step 3: Chunk documents
            logger.info(f"✂️ Chunking documents (max_tokens: {max_tokens})...")
            chunks = chunk_documents(documents, max_tokens)
            logger.info(f"✅ Created {len(chunks)} chunks")

            # Step 4: Embed and store WITH source tracking
            logger.info(f"🤖 Generating embeddings for {len(chunks)} chunks...")
            row_count = embed_and_store_chunks(
                chunks=chunks,
                database_url=database_url,
                table_name=actual_table_name,
                openai_api_key=openai_api_key,
                business_id=business_id,
                category=category,
                source_id=source_id,      # NEW: Link entries to source
                source_url=source_url     # NEW: Store in metadata
            )
            logger.info(f"✅ Stored {row_count} chunks")

            # Step 5: Mark source as successfully loaded
            logger.info(f"🔧 DEBUG: About to mark source loaded with row_count={row_count}")
            mark_source_loaded(
                database_url=database_url,
                source_id=source_id,
                entry_count=row_count
            )

            total_entries_created += row_count
            all_results.append({
                "source_url": source_url,
                "source_id": source_id,
                "source_type": source_type,
                "status": "loaded",
                "entry_count": row_count
            })

        except Exception as e:
            logger.error(f"❌ Failed to load source {source_url}: {e}")

            # Mark source as failed
            if 'source_id' in locals():
                mark_source_loaded(
                    database_url=database_url,
                    source_id=source_id,
                    entry_count=0,
                    error_message=str(e)
                )

            all_results.append({
                "source_url": source_url,
                "status": "failed",
                "error": str(e)
            })

            # Continue with next source instead of failing completely
            continue

    # Return comprehensive results
    successful_sources = [r for r in all_results if r['status'] == 'loaded']
    failed_sources = [r for r in all_results if r['status'] == 'failed']

    logger.info(f"✅ Pipeline complete: {total_entries_created} total entries from {len(successful_sources)}/{len(sources)} sources")

    return {
        "table_name": actual_table_name,
        "total_entries": total_entries_created,
        "sources_processed": len(sources),
        "sources_successful": len(successful_sources),
        "sources_failed": len(failed_sources),
        "results": all_results
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
