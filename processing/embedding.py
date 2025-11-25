"""
Embedding and database storage using Supabase/PostgreSQL
"""
import os
import json
import time
import uuid
from typing import List, Dict, Any
import psycopg
from psycopg.rows import dict_row
from openai import OpenAI


def create_embeddings_table(database_url: str, table_name: str = None) -> str:
    """Create knowledge_base table with proper schema"""
    # Always use knowledge_base table - ignore any table_name parameter
    table_name = "knowledge_base"

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            # Enable pgvector extension
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
                print("✅ pgvector extension enabled")
            except psycopg.Error as e:
                print(f"⚠️ Could not enable pgvector: {e}")

            # Create knowledge_base table with proper schema
            create_sql = """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                business_id UUID NOT NULL REFERENCES businesses(id),
                category VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                content TEXT NOT NULL,
                embedding vector(1536),
                metadata JSONB,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );

            CREATE INDEX IF NOT EXISTS knowledge_base_embedding_idx
            ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

            CREATE INDEX IF NOT EXISTS knowledge_base_metadata_idx
            ON knowledge_base USING GIN (metadata);

            CREATE INDEX IF NOT EXISTS knowledge_base_business_active_idx
            ON knowledge_base (business_id, is_active);

            CREATE INDEX IF NOT EXISTS knowledge_base_content_fts_idx
            ON knowledge_base USING GIN (to_tsvector('english', content));
            """

            cursor.execute(create_sql)
            conn.commit()

    print(f"✅ Created table: knowledge_base")
    return "knowledge_base"


def embed_and_store_chunks(chunks: List, database_url: str, table_name: str, openai_api_key: str, business_id: str, category: str = "website") -> int:
    """Generate embeddings and store chunks in knowledge_base table"""
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

            # Extract metadata
            metadata = {
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
            }

            chunk_data.append((business_id, category, title, chunk.text, embedding, json.dumps(metadata)))

            # Progress tracking
            if i % 5 == 0 or i == total_chunks:
                progress = (i / total_chunks) * 100
                print(f"📈 Progress: {i}/{total_chunks} chunks ({progress:.1f}%)")

        except Exception as e:
            print(f"❌ Error processing chunk {i}/{total_chunks}: {e}")
            continue

    # Insert chunks
    if chunk_data:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cursor:
                insert_sql = """
                INSERT INTO knowledge_base (business_id, category, title, content, embedding, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.executemany(insert_sql, chunk_data)
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
