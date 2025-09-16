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
    # Set environment variables for Railway
    os.environ["HOST"] = "0.0.0.0"
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting MCP server on {os.environ['HOST']}:{port}")
    mcp.run(transport="streamable-http")
