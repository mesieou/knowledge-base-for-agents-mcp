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
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8050)
