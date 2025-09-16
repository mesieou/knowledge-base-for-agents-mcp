import os
import logging
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.DEBUG)

load_dotenv("../.env")

# Get port from Railway's environment variable (with fallback for local dev)
port = int(os.getenv("PORT", "8080"))


# Create an MCP server
mcp = FastMCP(
    name="Calculator",
    host="0.0.0.0",
    port=port,
    stateless_http=False,  # Enable session management for MCP protocol
)

app = mcp.streamable_http_app()
app.router.redirect_slashes = False

# Add a simple calculator tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

# Run the server
if __name__ == "__main__":
    transport = "streamable-http"
    mcp.run(transport=transport)
