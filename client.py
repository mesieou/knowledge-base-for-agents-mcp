import asyncio
import time
from typing import Any, Dict

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def timed_tool_call(session: ClientSession, tool_name: str, arguments: Dict[str, Any] = None) -> tuple:
    """Call a tool and measure the execution time."""
    start_time = time.perf_counter()
    result = await session.call_tool(tool_name, arguments or {})
    end_time = time.perf_counter()
    duration = end_time - start_time
    return result, duration


async def main():
    # Connect to a streamable HTTP server
    async with streamablehttp_client("http://localhost:8000/mcp") as (
        read_stream,
        write_stream,
        _,
    ):
        # Create a session using the client streams
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            print("🔗 Initializing connection...")
            init_start = time.perf_counter()
            await session.initialize()
            init_time = time.perf_counter() - init_start
            print(f"✅ Connected in {init_time:.3f}s")

            # List available tools
            list_start = time.perf_counter()
            tools = await session.list_tools()
            list_time = time.perf_counter() - list_start
            print(f"🔧 Available tools ({list_time:.3f}s): {[tool.name for tool in tools.tools]}")

            # Test the greet tool with timing
            print("\n🚀 Testing tools with timing:")
            result, duration = await timed_tool_call(session, "greet", {"name": "Python MCP"})
            print(f"⏱️  greet tool: {duration:.3f}s")
            print(f"📝 Result: {result.content}")

            # Test the fetch_weather tool with timing
            weather_result, weather_duration = await timed_tool_call(session, "fetch_weather", {"city": "New York"})
            print(f"⏱️  fetch_weather tool: {weather_duration:.3f}s")
            print(f"📝 Result: {weather_result.content}")

            # Summary
            total_time = init_time + list_time + duration + weather_duration
            print(f"\n📊 Performance Summary:")
            print(f"   Connection: {init_time:.3f}s")
            print(f"   List tools: {list_time:.3f}s")
            print(f"   Greet tool: {duration:.3f}s")
            print(f"   Weather tool: {weather_duration:.3f}s")
            print(f"   Total time: {total_time:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
