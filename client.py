import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    # Connect to a streamable HTTP server
    async with streamablehttp_client("https://knowledge-base-for-agents-mcp-production.up.railway.app/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[tool.name for tool in tools.tools]}")

            # Test the greet tool
            result = await session.call_tool("greet", {"name": "Python MCP"})
            print(f"Greet result: {result.content}")

            # Test the fetch_weather tool
            weather_result = await session.call_tool("fetch_weather", {"city": "New York"})
            print(f"Weather result: {weather_result.content}")


if __name__ == "__main__":
    asyncio.run(main())
