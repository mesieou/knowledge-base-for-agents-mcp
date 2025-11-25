import logging
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from tools.loadDocuments import load_documents
from tools.queryKnowledge import query_knowledge_base

# ------------------------
# Logging
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ------------------------
# FastMCP server
# ------------------------
mcp = FastMCP("KnowledgeBaseMCP")

@mcp.tool
def load_documents_tool(
    sources: List[str],
    database_url: str,
    business_id: str,
    category: str = "website",
    max_tokens: int = 8191,
    crawl_internal: bool = True
) -> Dict[str, Any]:
    """Load and process documents into knowledge_base table.

    Args:
        sources: List of URLs or file paths to process
        database_url: PostgreSQL connection string
        business_id: Business UUID from Skedy businesses table
        category: Knowledge category (website, faq, policy, pricing, procedure, technical)
        max_tokens: Maximum tokens per chunk
        crawl_internal: Whether to crawl internal links
    """
    try:
        logger.info("🚀 Tool called - starting knowledge_base pipeline")

        # Log received parameters
        logger.info(f"📊 Using provided database_url: {database_url[:50]}...")
        logger.info(f"🏢 Business ID: {business_id}")
        logger.info(f"📂 Category: {category}")

        result = load_documents(
            business_id=business_id,
            sources=sources,
            table_name="knowledge_base",
            max_tokens=max_tokens,
            crawl_internal=crawl_internal,
            database_url=database_url,
            category=category
        )
        logger.info(f"✅ Tool completed - returning result: {result}")
        return result
    except Exception as e:
        logger.error(f"❌ Tool failed: {e}", exc_info=True)
        return {"error": str(e), "row_count": 0, "stored_files": []}

@mcp.tool
def query_knowledge_tool(
    question: str,
    database_url: str,
    business_id: str,
    match_threshold: float = 0.7,
    match_count: int = 3
) -> Dict[str, Any]:
    """Query knowledge_base table using vector similarity search.

    Args:
        question: The question to search for
        database_url: PostgreSQL connection string
        business_id: Business UUID from Skedy businesses table
        match_threshold: Minimum similarity score (0-1)
        match_count: Maximum number of results to return
    """
    try:
        logger.info(f"🔍 Query tool called - question: '{question}'")
        logger.info(f"📊 Table: knowledge_base, Business: {business_id}")

        result = query_knowledge_base(
            question=question,
            table_name="knowledge_base",
            database_url=database_url,
            business_id=business_id,
            match_threshold=match_threshold,
            match_count=match_count
        )

        logger.info(f"✅ Query completed - {result.get('context_count', 0)} sources found")
        return result
    except Exception as e:
        logger.error(f"❌ Query tool failed: {e}", exc_info=True)
        return {
            "sources": [],
            "context_count": 0,
            "error": str(e)
        }

# ------------------------
# ASGI app
# ------------------------
app = mcp.http_app(path="/mcp")


# Add CORS middleware for browser access
app = CORSMiddleware(
    app,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "DELETE"],
    expose_headers=["Mcp-Session-Id"]
)

# ------------------------
# Run server
# ------------------------
if __name__ == "__main__":
    logger.info("🚀 Starting MCP Server on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
