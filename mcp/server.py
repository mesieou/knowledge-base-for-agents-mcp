import logging
from mcp.server.fastmcp import FastMCP
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv("../.env")

port = int(os.getenv("PORT", "8050"))
logger.debug(f"PORT env var = {os.getenv('PORT')}")
logger.debug(f"Using port = {port}")

mcp = FastMCP(
    name="Calculator",
    host="0.0.0.0",
    port=port,
    stateless_http=True,
)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    logger.debug(f"Executing add({a}, {b})")
    return a + b

@mcp.app.get("/health")
async def health():
    logger.debug("Health check accessed")
    return {"status": "healthy"}

@mcp.app.post("/mcp")
@mcp.app.post("/mcp/")
async def mcp_endpoint(request):
    logger.debug(f"Received request to {request.url}: {request}")
    return await mcp.app.post(request)

if __name__ == "__main__":
    transport = "streamable-http"
    logger.info(f"Running server with {transport} transport on port {port}")
    try:
        mcp.run(transport=transport)
    except Exception as e:
        logger.error(f"Server failed: {e}")
        raise
