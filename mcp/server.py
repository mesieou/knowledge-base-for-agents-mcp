import os
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv("../.env")

# Get port from Railway's environment variable (with fallback for local dev)
port = int(os.getenv("PORT", "8080"))

# Create MCP server
mcp = FastMCP("Calculator")

# Add a simple calculator tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

# Mount MCP server using Starlette
app = Starlette(
    routes=[
        Mount("/", app=mcp.streamable_http_app()),
    ]
)

# Run the server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
