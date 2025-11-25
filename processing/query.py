"""
Query knowledge base using vector similarity search
"""
import json
from typing import List, Dict, Any, Optional
import psycopg
from psycopg.rows import dict_row
from openai import OpenAI


def query_knowledge(
    question: str,
    database_url: str,
    table_name: str,
    openai_api_key: str,
    business_id: str,
    match_threshold: float = 0.7,
    match_count: int = 3
) -> Dict[str, Any]:
    """
    Query knowledge_base table using vector similarity search

    Returns only the source documents - the agent will synthesize the answer.

    Args:
        question: The question to ask
        database_url: PostgreSQL connection string
        table_name: Table name (always knowledge_base)
        openai_api_key: OpenAI API key for generating question embedding
        business_id: Business UUID to filter results
        match_threshold: Minimum similarity threshold (0-1)
        match_count: Maximum number of results to return

    Returns:
        Dict containing sources array with content, similarity scores, and metadata
    """
    print(f"🔍 Querying: '{question}'")
    print(f"📋 Table: knowledge_base")
    print(f"🏢 Business ID: {business_id}")
    print(f"🎯 Threshold: {match_threshold}, Count: {match_count}")

    # Initialize OpenAI client
    openai_client = OpenAI(api_key=openai_api_key)

    try:
        # Generate embedding for the question
        print("🤖 Generating question embedding...")
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=question
        )
        question_embedding = embedding_response.data[0].embedding
        print("✅ Question embedding generated")

        # Query database for similar documents
        print("🔎 Searching for similar documents...")
        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                # Use pgvector's cosine similarity search on knowledge_base table
                # Filter by business_id and is_active for business-specific active results
                query_sql = """
                SELECT
                    id,
                    category,
                    title,
                    content as text,
                    metadata,
                    created_at,
                    updated_at,
                    1 - (embedding <=> %s::vector) as similarity
                FROM knowledge_base
                WHERE business_id = %s::uuid
                  AND is_active = true
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """

                cursor.execute(
                    query_sql,
                    (
                        question_embedding,
                        business_id,
                        question_embedding,
                        match_threshold,
                        question_embedding,
                        match_count
                    )
                )

                results = cursor.fetchall()
                print(f"📊 Found {len(results)} matching documents")

        # Format sources
        sources = []

        for row in results:
            source = {
                "id": str(row["id"]),
                "category": row["category"],
                "title": row["title"],
                "text": row["text"],  # aliased from content
                "similarity": float(row["similarity"]),
                "metadata": row["metadata"] if row["metadata"] else {},
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None
            }
            sources.append(source)

        if not sources:
            print("⚠️ No matching documents found")
            return {
                "sources": [],
                "context_count": 0
            }

        print(f"✅ Returning {len(sources)} sources (agent will synthesize answer)")

        return {
            "sources": sources,
            "context_count": len(sources)
        }

    except Exception as e:
        print(f"❌ Query error: {e}")
        raise


# For testing
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    openai_key = os.getenv("OPENAI_API_KEY")

    if database_url and openai_key:
        result = query_knowledge(
            question="What are your business hours?",
            database_url=database_url,
            table_name="documents",  # Replace with your table name
            openai_api_key=openai_key,
            business_id="test_business",  # Replace with actual business ID
            match_threshold=0.7,
            match_count=3
        )

        print("\n📝 Result:")
        print(f"Answer: {result['answer']}")
        print(f"\nSources ({len(result['sources'])}):")
        for i, source in enumerate(result['sources'], 1):
            print(f"\n{i}. Similarity: {source['similarity']:.3f}")
            print(f"   Text: {source['text'][:100]}...")
