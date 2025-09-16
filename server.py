from mcp.server.fastmcp import FastMCP
import os
import uvicorn

# Stateful server (maintains session state)
mcp = FastMCP("KnowledgeBaseMCP")
# Add a simple tool to demonstrate the server
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
    # Use PORT from environment or default to 8000 (FastMCP default)
    port = int(os.getenv("PORT", 8050))
    print(f"Starting MCP server on port {port}")

    # Get the FastAPI app and run with uvicorn
    app = mcp.create_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
