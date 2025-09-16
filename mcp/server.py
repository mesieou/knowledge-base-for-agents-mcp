import os
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv("../.env")

# Get port from Railway's environment variable (with fallback for local dev)
port = int(os.getenv("PORT", "8050"))

# Create an MCP server
mcp = FastMCP(
    name="Calculator",
    host="0.0.0.0",  # only used for SSE transport (localhost)
    port=port,  # Uses Railway's PORT or defaults to 8050
    stateless_http=True,
)

# Add MCP endpoint route
@mcp.get("/mcp")
@mcp.post("/mcp")

async def mcp_endpoint():
    """MCP protocol endpoint"""
    return {"status": "MCP endpoint available"}


# Add a simple calculator tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b


# Run the server
if __name__ == "__main__":
    import sys

    # Default to streamable-http for production, but allow override
    transport = "streamable-http"

    print(f"Running server with {transport} transport")
    mcp.run(transport=transport)
