import asyncio
import time
from typing import Any, Dict

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def timed_tool_call(session: ClientSession, tool_name: str, arguments: Dict[str, Any] = None) -> tuple:
    """Call a tool and measure the execution time with timeout and error handling."""
    start_time = time.perf_counter()

    try:
        print(f"⏳ Calling {tool_name} (timeout: 5 minutes)...")
        print("📋 Check Railway logs for detailed progress...")

        # Add periodic progress updates
        async def call_with_updates():
            task = asyncio.create_task(session.call_tool(tool_name, arguments or {}))
            start = time.perf_counter()

            while not task.done():
                await asyncio.sleep(10)  # Check every 10 seconds
                elapsed = time.perf_counter() - start
                print(f"⏳ Still processing... {elapsed:.0f}s elapsed")

            return await task

        result = await asyncio.wait_for(call_with_updates(), timeout=300)
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"✅ {tool_name} completed in {duration:.1f}s")
        return result, duration

    except asyncio.TimeoutError:
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"⏰ {tool_name} timed out after {duration:.1f}s")
        raise

    except Exception as e:
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"❌ {tool_name} failed after {duration:.1f}s: {e}")
        raise


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
