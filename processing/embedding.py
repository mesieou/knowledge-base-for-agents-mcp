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
    """Create PostgreSQL table with pgvector support"""
    if not table_name:
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        table_name = f"documents_{timestamp}_{unique_id}"

    # Sanitize table name
    table_name = table_name.replace('-', '_').replace(' ', '_')

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cursor:
            # Enable pgvector extension
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                conn.commit()
                print("✅ pgvector extension enabled")
            except psycopg.Error as e:
                print(f"⚠️ Could not enable pgvector: {e}")

    # Create table with pgvector support
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        text TEXT NOT NULL,
        vector vector(1536),
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS {table_name}_vector_idx
    ON {table_name} USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);

    CREATE INDEX IF NOT EXISTS {table_name}_metadata_idx
    ON {table_name} USING GIN (metadata);
    """

    cursor.execute(create_sql)
    conn.commit()

    print(f"✅ Created table: {table_name}")
    return table_name


def embed_and_store_chunks(chunks: List, database_url: str, table_name: str, openai_api_key: str) -> int:
    """Generate embeddings and store chunks in PostgreSQL"""
    openai_client = OpenAI(api_key=openai_api_key)

    chunk_data = []
    for chunk in chunks:
        try:
            # Generate embedding
            embedding_response = openai_client.embeddings.create(
                model="text-embedding-3-large",
                input=chunk.text
            )
            embedding = embedding_response.data[0].embedding

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
                "title": chunk.meta.headings[0] if chunk.meta and chunk.meta.headings else None,
            }

            chunk_data.append((chunk.text, embedding, json.dumps(metadata)))

        except Exception as e:
            print(f"❌ Error processing chunk: {e}")
            continue

    # Insert chunks
    if chunk_data:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cursor:
                insert_sql = f"""
                INSERT INTO {table_name} (text, vector, metadata)
                VALUES (%s, %s, %s)
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
