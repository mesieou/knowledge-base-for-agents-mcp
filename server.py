import logging
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
import uvicorn

from tools.loadDocuments import load_documents

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
def ping() -> str:
    """Simple ping test to verify server is working"""
    logger.info("🏓 Ping received")
    return "pong"

@mcp.tool
def load_documents_tool(
    sources: Optional[List[str]] = None,
    table_name: Optional[str] = None,
    max_tokens: int = 8191
) -> Dict[str, Any]:
    """Load and process documents into vector DB."""
    try:
        logger.info("🚀 Tool called - starting MOCK pipeline for testing")

        # MOCK RESPONSE for testing - bypass heavy processing
        import time
        import uuid

        mock_table = f"documents_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        mock_result = {
            "table_name": mock_table,
            "row_count": 5,  # Mock data
            "stored_files": sources[:1] if sources else ["test.pdf"],
            "total_sources": len(sources) if sources else 1,
            "successful_sources": 1,
            "failed_sources": 0,
            "status": "MOCK_SUCCESS - Heavy processing disabled for Railway testing"
        }

        logger.info(f"✅ MOCK Tool completed - returning result: {mock_result}")
        return mock_result

    except Exception as e:
        logger.error(f"❌ Tool failed: {e}", exc_info=True)
        return {"error": str(e), "row_count": 0, "stored_files": []}

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
