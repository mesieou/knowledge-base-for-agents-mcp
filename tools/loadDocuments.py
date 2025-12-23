"""
Thin MCP tool wrapper - orchestrates extraction, chunking, and embedding
Uses TRANSACTIONAL approach - nothing is committed until everything succeeds
"""
import os
import logging
import sys
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row

from processing import extract_documents, chunk_documents, create_embeddings_table, embed_and_store_chunks
from processing.embedding import infer_source_type, create_or_update_source_transactional, embed_and_store_chunks_transactional

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
    table_name: str = "knowledge_entries",
    max_tokens: int = 8191,
    crawl_internal: bool = True,
    database_url: Optional[str] = None,
    category: str = "website",
    description: str = None
) -> Dict[str, Any]:
    """
    Load documents with source tracking - TRANSACTIONAL approach.

    CRITICAL: Nothing is committed to the database until ALL processing succeeds.
    If any step fails (extraction, chunking, embedding), NO database records are created.
    """
    import uuid as uuid_module
    from openai import OpenAI

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: VALIDATION (fail fast before any processing)
    # ═══════════════════════════════════════════════════════════════════════════

    # Validate required business_id
    if not business_id:
        raise ValueError("business_id is required and cannot be None or empty")

    # Validate business_id is a valid UUID
    try:
        uuid_module.UUID(business_id)
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

    # Validate OpenAI API key works before processing
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        # Quick validation call
        logger.info("🔑 Validating OpenAI API key...")
    except Exception as e:
        raise ValueError(f"Invalid OPENAI_API_KEY: {e}")

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
    logger.info(f"📋 Sources to process: {len(sources)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: EXTRACTION & CHUNKING (all processing BEFORE any DB writes)
    # ═══════════════════════════════════════════════════════════════════════════

    # Process all sources and collect results BEFORE touching the database
    processed_sources = []  # Will hold: {source_url, source_type, chunks, embeddings}

    for source_url in sources:
        logger.info(f"📄 Processing source: {source_url}")

        source_type = infer_source_type(source_url)

        # Step 1: Extract documents
        logger.info(f"🔍 Extracting documents from {source_type}...")
        documents = extract_documents([source_url], crawl_internal=crawl_internal)
        logger.info(f"✅ Extracted {len(documents)} documents")

        if not documents:
            raise ValueError(f"No documents extracted from source: {source_url}")

        # Step 2: Chunk documents
        logger.info(f"✂️ Chunking documents (max_tokens: {max_tokens})...")
        chunks = chunk_documents(documents, max_tokens)
        logger.info(f"✅ Created {len(chunks)} chunks")

        if not chunks:
            raise ValueError(f"No chunks created from source: {source_url}")

        # Step 3: Generate embeddings (most expensive step - do BEFORE DB transaction)
        logger.info(f"🤖 Generating embeddings for {len(chunks)} chunks...")
        chunk_data = _generate_embeddings(
            chunks=chunks,
            openai_client=openai_client,
            business_id=business_id,
            category=category,
            source_url=source_url
        )
        logger.info(f"✅ Generated {len(chunk_data)} embeddings")

        processed_sources.append({
            "source_url": source_url,
            "source_type": source_type,
            "chunk_data": chunk_data,
            "chunk_count": len(chunk_data)
        })

    logger.info(f"✅ All sources processed successfully. Starting database transaction...")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: DATABASE TRANSACTION (all-or-nothing commit)
    # ═══════════════════════════════════════════════════════════════════════════

    all_results = []
    total_entries_created = 0

    # Single transaction for ALL database operations
    with psycopg.connect(database_url, autocommit=False) as conn:
        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                # Create tables if needed (within transaction)
                logger.info("🗄️ Ensuring database tables exist...")
                _ensure_tables_exist(cursor)

                # Process each source within the same transaction
                for processed in processed_sources:
                    source_url = processed["source_url"]
                    source_type = processed["source_type"]
                    chunk_data = processed["chunk_data"]

                    # Create/update source tracking record (NOT committed yet)
                    logger.info(f"📝 Creating source record: {source_url}")
                    source_id = create_or_update_source_transactional(
                        cursor=cursor,
                        business_id=business_id,
                        source_url=source_url,
                        category=category,
                        source_type=source_type,
                        crawl_internal=crawl_internal,
                        description=description
                    )
                    logger.info(f"✓ Source ID: {source_id}")

                    # Store embeddings (NOT committed yet)
                    row_count = embed_and_store_chunks_transactional(
                        cursor=cursor,
                        chunk_data=chunk_data,
                        business_id=business_id,
                        category=category,
                        source_id=source_id,
                        source_url=source_url
                    )
                    logger.info(f"✓ Prepared {row_count} chunks for storage")

                    # Update source with entry count (NOT committed yet)
                    cursor.execute(
                        """
                        UPDATE knowledge_sources
                        SET status = 'loaded',
                            last_loaded_at = now(),
                            entry_count = %s,
                            error_message = NULL,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (row_count, source_id)
                    )

                    total_entries_created += row_count
                    all_results.append({
                        "source_url": source_url,
                        "source_id": source_id,
                        "source_type": source_type,
                        "status": "loaded",
                        "entry_count": row_count
                    })

                # ═══════════════════════════════════════════════════════════════
                # COMMIT: Only here, after ALL operations succeeded
                # ═══════════════════════════════════════════════════════════════
                conn.commit()
                logger.info("✅ Transaction committed successfully!")

        except Exception as e:
            # ROLLBACK: Nothing is saved if ANY step fails
            conn.rollback()
            logger.error(f"❌ Transaction rolled back due to error: {e}")
            raise RuntimeError(f"Pipeline failed, no data was saved: {e}") from e

    # Return comprehensive results
    successful_sources = [r for r in all_results if r['status'] == 'loaded']

    logger.info(f"✅ Pipeline complete: {total_entries_created} total entries from {len(successful_sources)}/{len(sources)} sources")

    return {
        "table_name": "knowledge_entries",
        "total_entries": total_entries_created,
        "sources_processed": len(sources),
        "sources_successful": len(successful_sources),
        "sources_failed": 0,
        "results": all_results
    }


def _generate_embeddings(chunks: List, openai_client, business_id: str, category: str, source_url: str) -> List[tuple]:
    """
    Generate embeddings for chunks in BATCHES - much faster than individual API calls.
    Returns list of dicts ready for database insertion.
    """
    import json
    import time

    chunk_data = []
    total_chunks = len(chunks)
    BATCH_SIZE = 100  # OpenAI supports up to 2048, but 100 is safe for token limits

    logger.info(f"📊 Processing {total_chunks} chunks in batches of {BATCH_SIZE}...")

    # Process in batches for faster API calls
    for batch_start in range(0, total_chunks, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_chunks)
        batch_chunks = chunks[batch_start:batch_end]

        # Batch API call - sends multiple texts in one request
        texts = [chunk.text for chunk in batch_chunks]
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )

        # Process batch results
        for idx, (chunk, emb_data) in enumerate(zip(batch_chunks, embedding_response.data)):
            global_idx = batch_start + idx + 1
            embedding = emb_data.embedding

            # Extract title with fallback logic
            title = "Untitled Document"
            if chunk.meta and chunk.meta.headings:
                title = chunk.meta.headings[0]
            elif chunk.meta and chunk.meta.origin and chunk.meta.origin.filename:
                title = chunk.meta.origin.filename

            # Truncate title to 255 characters max
            title = title[:255] if title else "Untitled Document"

            # Build metadata
            metadata = {
                "source_url": source_url,
                "filename": chunk.meta.origin.filename if chunk.meta and chunk.meta.origin else "unknown",
                "page_numbers": [
                    page_no
                    for page_no in sorted(
                        set(
                            prov.page_no
                            for item in chunk.meta.doc_items
                            for prov in item.prov
                            if hasattr(prov, 'page_no') and prov.page_no is not None
                        )
                    )
                ] if chunk.meta and chunk.meta.doc_items else None,
                "original_title": chunk.meta.headings[0] if chunk.meta and chunk.meta.headings else None,
                "chunk_index": global_idx,
                "total_chunks": total_chunks,
                "loaded_at": time.time()
            }

            chunk_data.append({
                "title": title,
                "content": chunk.text,
                "embedding": embedding,
                "metadata": json.dumps(metadata)
            })

        # Progress tracking per batch
        progress = (batch_end / total_chunks) * 100
        logger.info(f"📈 Embedding progress: {batch_end}/{total_chunks} ({progress:.1f}%)")

    return chunk_data


def _ensure_tables_exist(cursor):
    """Create tables if they don't exist (within transaction)."""

    # Enable pgvector extension
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except Exception as e:
        logger.warning(f"⚠️ Could not enable pgvector: {e}")

    # Create knowledge_sources table FIRST (due to FK constraint)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id UUID NOT NULL REFERENCES businesses(id),
            source_url TEXT NOT NULL,
            source_type VARCHAR NOT NULL CHECK (source_type IN ('website', 'pdf', 'document', 'text')),
            category VARCHAR NOT NULL CHECK (category IN ('website', 'faq', 'policy', 'pricing', 'procedure', 'technical')),
            description TEXT,
            crawl_internal BOOLEAN DEFAULT true,
            status VARCHAR NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'loading', 'loaded', 'failed', 'inactive')),
            last_loaded_at TIMESTAMPTZ,
            error_message TEXT,
            entry_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(business_id, source_url)
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_business
            ON knowledge_sources(business_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_status
            ON knowledge_sources(business_id, status);
        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_url
            ON knowledge_sources(source_url);
    """)

    # Create knowledge_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id UUID NOT NULL REFERENCES businesses(id),
            category VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536),
            metadata JSONB,
            source_id UUID REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS knowledge_entries_embedding_idx
            ON knowledge_entries USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

        CREATE INDEX IF NOT EXISTS knowledge_entries_metadata_idx
            ON knowledge_entries USING GIN (metadata);

        CREATE INDEX IF NOT EXISTS knowledge_entries_business_active_idx
            ON knowledge_entries (business_id, is_active);

        CREATE INDEX IF NOT EXISTS knowledge_entries_content_fts_idx
            ON knowledge_entries USING GIN (to_tsvector('english', content));

        CREATE INDEX IF NOT EXISTS idx_knowledge_entries_source
            ON knowledge_entries(source_id);

        CREATE INDEX IF NOT EXISTS idx_knowledge_entries_business_source
            ON knowledge_entries(business_id, source_id)
            WHERE is_active = true;
    """)

    logger.info("✅ Tables verified/created")


# For testing
if __name__ == "__main__":
    import sys

    try:
        result = load_documents()
        print("✅ Pipeline Result:", result)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
