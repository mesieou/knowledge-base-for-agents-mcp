"""
Simple FastMCP server example
"""

from mcp.server.fastmcp import FastMCP
import os

# Create MCP server
mcp = FastMCP("KnowledgeBaseMCP")

@mcp.tool()
def greet(name: str = "World") -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

@mcp.tool()
def fetch_weather(city: str) -> str:
    """Get weather data for a city (mock implementation)."""
    return f"Weather in {city}: Sunny, 25°C"

# Run server with streamable_http transport
if __name__ == "__main__":
    # Railway expects port 8050, set via environment variable
    os.environ.setdefault("PORT", "8050")
    mcp.run(transport="streamable-http")
