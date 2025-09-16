"""
Production-ready MCP server following Docker best practices
"""

import os
from mcp.server.fastmcp import FastMCP

# Create MCP server with proper Docker host binding
mcp = FastMCP(
    name="KnowledgeBaseMCP",
    host="0.0.0.0",  # Bind to all interfaces for Docker
    port=8000,       # Port for the server
)

@mcp.tool()
def greet(name: str = "World") -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

@mcp.tool()
def fetch_weather(city: str) -> str:
    """Get weather data for a city (mock implementation)."""
    return f"Weather in {city}: Sunny, 25°C"

if __name__ == "__main__":
    # Now FastMCP should bind to 0.0.0.0:8000 properly!
    print("🚀 Starting FastMCP with host=0.0.0.0:8000")
    mcp.run(transport="streamable-http")
