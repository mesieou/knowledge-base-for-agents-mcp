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
    async with streamablehttp_client("https://knowledge-base-for-agents-mcp-production.up.railway.app/mcp") as (
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

            # Test the load_documents_tool with timing
            print("\n🚀 Testing load_documents_tool:")
            result, duration = await timed_tool_call(session, "load_documents_tool", {
                "sources": ["https://arxiv.org/pdf/2408.09869"],
                "table_name": "test_railway_deployment",
                "max_tokens": 1000
            })
            print(f"⏱️  load_documents_tool: {duration:.3f}s")
            print(f"📝 Result: {result.content}")

            # Summary
            total_time = init_time + list_time + duration
            print(f"\n📊 Performance Summary:")
            print(f"   Connection: {init_time:.3f}s")
            print(f"   List tools: {list_time:.3f}s")
            print(f"   Load documents: {duration:.3f}s")
            print(f"   Total time: {total_time:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
