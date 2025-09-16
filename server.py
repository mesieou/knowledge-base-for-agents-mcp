from mcp.server.fastmcp import FastMCP# Stateful server (maintains session state)

mcp = FastMCP("KnowledgeBaseMCP")

# Other configuration options:
# Stateless server (no session persistence)
# mcp = FastMCP("StatelessServer", stateless_http=True)

# Stateless server (no session persistence, no sse stream with supported client)
# mcp = FastMCP("StatelessServer", stateless_http=True, json_response=True)


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
    mcp.run(transport="streamable-http")
