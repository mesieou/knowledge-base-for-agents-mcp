"""
Embedding and database storage using Supabase/PostgreSQL
"""
import os
import json
import time
import uuid
import logging
from typing import List, Dict, Any
import psycopg
from psycopg.rows import dict_row
from openai import OpenAI

logger = logging.getLogger(__name__)


def create_embeddings_table(database_url: str, table_name: str = "knowledge_entries") -> str:
    """
    Create or verify knowledge_entries table with pgvector support
    ALSO creates knowledge_sources tracking table
    """
    table_name = "knowledge_entries"

    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cursor:
            # Enable pgvector extension
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
                print("✅ pgvector extension enabled")
            except psycopg.Error as e:
                print(f"⚠️ Could not enable pgvector: {e}")

            # Create knowledge_entries table with proper schema
            create_kb_sql = """
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

            COMMENT ON COLUMN knowledge_entries.source_id IS 'Foreign key to knowledge_sources table. Entries auto-delete when source is deleted (CASCADE).';
            """
            cursor.execute(create_kb_sql)

            # NEW: Create knowledge_sources tracking table
            create_sources_sql = """
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
            """

            cursor.execute(create_sources_sql)
            conn.commit()
            print("✅ Created knowledge_sources tracking table")

    print(f"✅ Created table: {table_name}")
    return table_name


def infer_source_type(source_url: str) -> str:
    """Detect source type from URL/path"""
    source_lower = source_url.lower()

    if source_lower.endswith('.pdf'):
        return 'pdf'
    elif source_lower.startswith('http://') or source_lower.startswith('https://'):
        return 'website'
    elif source_lower.endswith(('.doc', '.docx')):
        return 'document'
    else:
        return 'text'


def create_or_update_source(
    database_url: str,
    business_id: str,
    source_url: str,
    category: str,
    source_type: str = None,
    crawl_internal: bool = True,
    description: str = None
) -> str:
    """
    Create or update knowledge source record
    Returns source_id
    """
    if not source_type:
        source_type = infer_source_type(source_url)

    with psycopg.connect(database_url, row_factory=dict_row, autocommit=False) as conn:
        with conn.cursor() as cursor:
            # Try to find existing source
            cursor.execute(
                """
                SELECT id, status FROM knowledge_sources
                WHERE business_id = %s::uuid AND source_url = %s
                """,
                (business_id, source_url)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing source
                cursor.execute(
                    """
                    UPDATE knowledge_sources
                    SET status = 'loading',
                        category = %s,
                        source_type = %s,
                        crawl_internal = %s,
                        description = COALESCE(%s, description),
                        entry_count = 0,
                        error_message = NULL,
                        is_active = true,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING id
                    """,
                    (category, source_type, crawl_internal, description, existing['id'])
                )
                conn.commit()
                logger.info(f"📝 Updated existing source: {source_url}")
                return str(existing['id'])
            else:
                # Create new source
                cursor.execute(
                    """
                    INSERT INTO knowledge_sources (
                        business_id, source_url, source_type, category,
                        crawl_internal, description, status, entry_count,
                        error_message, is_active
                    )
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, 'loading', 0, NULL, true)
                    RETURNING id
                    """,
                    (business_id, source_url, source_type, category, crawl_internal, description)
                )
                result = cursor.fetchone()
                conn.commit()
                logger.info(f"➕ Created new source: {source_url}")
                return str(result['id'])


def mark_source_loaded(
    database_url: str,
    source_id: str,
    entry_count: int,
    error_message: str = None
):
    """Mark source as successfully loaded or failed"""
    status = 'failed' if error_message else 'loaded'

    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cursor:
            # First verify the record exists
            cursor.execute(
                "SELECT id, entry_count FROM knowledge_sources WHERE id = %s",
                (source_id,)
            )
            before_update = cursor.fetchone()
            logger.info(f"🔧 Before update: {before_update}")

            # Perform the update
            cursor.execute(
                """
                UPDATE knowledge_sources
                SET status = %s,
                    last_loaded_at = now(),
                    entry_count = %s,
                    error_message = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (status, entry_count, error_message, source_id)
            )

            rows_updated = cursor.rowcount
            logger.info(f"🔧 Rows updated: {rows_updated}")

            conn.commit()

            # Verify after update
            cursor.execute(
                "SELECT id, entry_count, status FROM knowledge_sources WHERE id = %s",
                (source_id,)
            )
            after_update = cursor.fetchone()
            logger.info(f"🔧 After update: {after_update}")

    if error_message:
        logger.error(f"❌ Source failed: {error_message}")
    else:
        logger.info(f"✅ Source loaded: {entry_count} entries")


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONAL VERSIONS - Use existing cursor, don't commit
# ═══════════════════════════════════════════════════════════════════════════════

def create_or_update_source_transactional(
    cursor,
    business_id: str,
    source_url: str,
    category: str,
    source_type: str = None,
    crawl_internal: bool = True,
    description: str = None
) -> str:
    """
    Create or update knowledge source record WITHIN an existing transaction.
    Does NOT commit - caller is responsible for transaction management.
    Returns source_id
    """
    if not source_type:
        source_type = infer_source_type(source_url)

    # Try to find existing source
    cursor.execute(
        """
        SELECT id, status FROM knowledge_sources
        WHERE business_id = %s::uuid AND source_url = %s
        """,
        (business_id, source_url)
    )
    existing = cursor.fetchone()

    if existing:
        # Update existing source
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET status = 'loading',
                category = %s,
                source_type = %s,
                crawl_internal = %s,
                description = COALESCE(%s, description),
                entry_count = 0,
                error_message = NULL,
                is_active = true,
                updated_at = now()
            WHERE id = %s
            RETURNING id
            """,
            (category, source_type, crawl_internal, description, existing['id'])
        )
        # NOTE: No commit here - transaction managed by caller
        logger.info(f"📝 Updated existing source: {source_url}")
        return str(existing['id'])
    else:
        # Create new source
        cursor.execute(
            """
            INSERT INTO knowledge_sources (
                business_id, source_url, source_type, category,
                crawl_internal, description, status, entry_count,
                error_message, is_active
            )
            VALUES (%s::uuid, %s, %s, %s, %s, %s, 'loading', 0, NULL, true)
            RETURNING id
            """,
            (business_id, source_url, source_type, category, crawl_internal, description)
        )
        result = cursor.fetchone()
        # NOTE: No commit here - transaction managed by caller
        logger.info(f"➕ Created new source: {source_url}")
        return str(result['id'])


def embed_and_store_chunks_transactional(
    cursor,
    chunk_data: List[Dict],
    business_id: str,
    category: str,
    source_id: str,
    source_url: str
) -> int:
    """
    Store pre-generated embeddings WITHIN an existing transaction.
    Does NOT commit - caller is responsible for transaction management.

    Args:
        cursor: Active database cursor
        chunk_data: List of dicts with 'title', 'content', 'embedding', 'metadata'
        business_id: UUID of the business
        category: Category for the knowledge base entries
        source_id: UUID of the source record
        source_url: URL of the source (for metadata)

    Returns:
        Number of chunks stored
    """
    if not chunk_data:
        return 0

    # Validate business_id
    try:
        uuid.UUID(business_id)
    except ValueError:
        raise ValueError(f"business_id must be a valid UUID format, got: {business_id}")

    insert_sql = """
        INSERT INTO knowledge_entries (business_id, category, title, content, embedding, metadata, source_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    for chunk in chunk_data:
        cursor.execute(insert_sql, (
            business_id,
            category,
            chunk['title'],
            chunk['content'],
            chunk['embedding'],
            chunk['metadata'],
            source_id
        ))

    # NOTE: No commit here - transaction managed by caller
    logger.info(f"📦 Prepared {len(chunk_data)} chunks for insertion")
    return len(chunk_data)


def embed_and_store_chunks(chunks: List, database_url: str, table_name: str, openai_api_key: str, business_id: str, category: str = "website", source_id: str = None, source_url: str = None) -> int:
    """
    Generate embeddings and store chunks in knowledge_entries table
    Now includes source tracking in metadata
    """
    import os

    # Validate required business_id
    if not business_id:
        raise ValueError("business_id is required and cannot be None or empty")

    # Validate business_id is a valid UUID
    try:
        uuid.UUID(business_id)
    except ValueError:
        raise ValueError(f"business_id must be a valid UUID format, got: {business_id}")

    openai_client = OpenAI(api_key=openai_api_key)

    print(f"🏢 Using business_id: {business_id}")
    print(f"📂 Category: {category}")
    if source_id:
        print(f"🔗 Source ID: {source_id}")
    if source_url:
        print(f"🌐 Source URL: {source_url}")

    chunk_data = []
    total_chunks = len(chunks)
    print(f"📊 Processing {total_chunks} chunks for embeddings...")

    for i, chunk in enumerate(chunks, 1):
        try:
            # Generate embedding (using small model for pgvector 2000 dimension limit)
            embedding_response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=chunk.text
            )
            embedding = embedding_response.data[0].embedding

            # Extract title with fallback logic
            title = "Untitled Document"
            if chunk.meta and chunk.meta.headings:
                title = chunk.meta.headings[0]
            elif chunk.meta and chunk.meta.origin and chunk.meta.origin.filename:
                title = chunk.meta.origin.filename

            # Truncate title to 255 characters max
            title = title[:255] if title else "Untitled Document"

            # Build metadata WITH source tracking
            metadata = {
                "source_url": source_url,  # NEW: Track source URL
                "source_id": source_id,    # NEW: Link to knowledge_sources table
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
                "chunk_index": i,                # NEW: Track chunk position
                "total_chunks": total_chunks,    # NEW: Total chunks from this source
                "loaded_at": time.time()         # NEW: When this was loaded
            }

            chunk_data.append((business_id, category, title, chunk.text, embedding, json.dumps(metadata), source_id))

            # Progress tracking
            if i % 5 == 0 or i == total_chunks:
                progress = (i / total_chunks) * 100
                print(f"📈 Progress: {i}/{total_chunks} chunks ({progress:.1f}%)")

        except Exception as e:
            print(f"❌ Error processing chunk {i}/{total_chunks}: {e}")
            continue

    # Insert chunks
    if chunk_data:
        # Use fresh connection to avoid prepared statement conflicts
        with psycopg.connect(database_url, autocommit=False) as conn:
            with conn.cursor() as cursor:
                insert_sql = """
                INSERT INTO knowledge_entries (business_id, category, title, content, embedding, metadata, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                # Use execute() in loop instead of executemany() to avoid prepared statements
                for chunk in chunk_data:
                    cursor.execute(insert_sql, chunk)
                conn.commit()
                print(f"✅ Stored {len(chunk_data)} chunks with embeddings")

    return len(chunk_data)


# For testing
if __name__ == "__main__":
    from .extraction import extract_documents
    from .chunking import chunk_documents
    from dotenv import load_dotenv

    load_dotenv()

    # Test the pipeline
    docs = extract_documents(["https://arxiv.org/pdf/2408.09869"])
    chunks = chunk_documents(docs)

    database_url = os.getenv("DATABASE_URL")
    openai_key = os.getenv("OPENAI_API_KEY")

    if database_url and openai_key:
        table_name = create_embeddings_table(database_url, "test_embeddings")
        count = embed_and_store_chunks(chunks, database_url, table_name, openai_key)
        print(f"Pipeline complete: {count} chunks stored")
