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
        logger.info("🚀 Tool called - starting pipeline")
        result = load_documents(sources=sources, table_name=table_name, max_tokens=max_tokens)
        logger.info(f"✅ Tool completed - returning result: {result}")
        return result
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
