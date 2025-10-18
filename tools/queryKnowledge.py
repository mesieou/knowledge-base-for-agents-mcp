"""
MCP tool wrapper for querying knowledge base
"""
import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from processing.query import query_knowledge

load_dotenv()

logger = logging.getLogger(__name__)


def query_knowledge_base(
    question: str,
    table_name: str,
    database_url: str,
    business_id: str,
    match_threshold: float = 0.7,
    match_count: int = 3
) -> Dict[str, Any]:
    """
    Query knowledge base using vector similarity search

    Returns relevant source documents for the agent to use in synthesizing an answer.
    The agent will naturally incorporate this information into the conversation.

    Args:
        question: The question to search for
        table_name: Table containing the knowledge base
        database_url: PostgreSQL connection string
        business_id: Business ID to scope the search
        match_threshold: Minimum similarity score (0-1, default 0.7)
        match_count: Maximum number of source documents to retrieve (default 3)

    Returns:
        Dict with sources array (text, similarity, metadata) and context_count
    """
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        logger.info(f"🔍 Query tool called for business: {business_id}")
        logger.info(f"📋 Question: {question}")
        logger.info(f"📊 Table: {table_name}")

        # Call the query processor
        result = query_knowledge(
            question=question,
            database_url=database_url,
            table_name=table_name,
            openai_api_key=openai_api_key,
            business_id=business_id,
            match_threshold=match_threshold,
            match_count=match_count
        )

        logger.info(f"✅ Query completed - found {result['context_count']} sources")

        return {
            "sources": result["sources"],
            "context_count": result["context_count"],
            "business_id": business_id,
            "table_name": table_name
        }

    except Exception as e:
        logger.error(f"❌ Query failed: {e}", exc_info=True)
        return {
            "sources": [],
            "context_count": 0,
            "error": str(e)
        }


# For testing
if __name__ == "__main__":
    import sys

    try:
        result = query_knowledge_base(
            question="What are your business hours?",
            table_name="documents",
            database_url=os.getenv("DATABASE_URL", ""),
            business_id="test_business",
            match_threshold=0.7,
            match_count=3
        )
        print("✅ Query Result:", result)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
