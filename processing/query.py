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
    Query knowledge base using vector similarity search

    Returns only the source documents - the agent will synthesize the answer.

    Args:
        question: The question to ask
        database_url: PostgreSQL connection string
        table_name: Table containing the embeddings
        openai_api_key: OpenAI API key for generating question embedding
        business_id: Business ID to filter results
        match_threshold: Minimum similarity threshold (0-1)
        match_count: Maximum number of results to return

    Returns:
        Dict containing sources array with text, similarity scores, and metadata
    """
    print(f"🔍 Querying: '{question}'")
    print(f"📋 Table: {table_name}")
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
                # Use pgvector's cosine similarity search
                # Note: We filter by business_id to ensure business-specific results
                query_sql = f"""
                SELECT
                    text,
                    metadata,
                    1 - (vector <=> %s::vector) as similarity
                FROM {table_name}
                WHERE business_id = %s
                  AND 1 - (vector <=> %s::vector) >= %s
                ORDER BY vector <=> %s::vector
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
                "text": row["text"],
                "similarity": float(row["similarity"]),
                "metadata": row["metadata"] if row["metadata"] else {}
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
