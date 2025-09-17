import asyncio
import time
from typing import Any, Dict

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def timed_tool_call(session: ClientSession, tool_name: str, arguments: Dict[str, Any] = None) -> tuple:
    """Call a tool and measure the execution time with timeout and error handling."""
    start_time = time.perf_counter()

    try:
        # Show what we're processing
        if arguments and "sources" in arguments:
            sources = arguments["sources"]
            if len(sources) == 1:
                print(f"📄 Processing: {sources[0]}")
            else:
                print(f"📄 Processing {len(sources)} sources...")

        print(f"⏳ Executing {tool_name}...")

        # Add periodic progress updates
        async def call_with_updates():
            task = asyncio.create_task(session.call_tool(tool_name, arguments or {}))
            start = time.perf_counter()

            while not task.done():
                await asyncio.sleep(15)  # Check every 15 seconds
                elapsed = time.perf_counter() - start
                print(f"⏳ Processing... {elapsed:.0f}s elapsed")

            return await task

        result = await asyncio.wait_for(call_with_updates(), timeout=300)
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"✅ Completed in {duration:.1f}s")
        return result, duration

    except asyncio.TimeoutError:
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"⏰ Timed out after {duration:.1f}s")
        raise

    except Exception as e:
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"❌ Failed after {duration:.1f}s: {e}")
        raise


async def main():
    # Connect to a streamable HTTP server
    async with streamablehttp_client("http://45.151.154.42:8000/mcp") as (
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
                "sources": ["https://tigapropertyservices.com.au/"],
                "table_name": "test_railway_deployment",
                "max_tokens": 1000
            })
            print(f"⏱️  load_documents_tool: {duration:.3f}s")
            print(f"📝 Result: {result.content}")

            # Summary
            total_time = init_time + list_time + duration
            print(f"\n📊 Performance Summary:")
            print(f"   🔗 Connection: {init_time:.3f}s")
            print(f"   🔧 List tools: {list_time:.3f}s")
            print(f"   📄 Load documents: {duration:.3f}s")
            print(f"   ⏱️  Total time: {total_time:.3f}s")


if __name__ == "__main__":
    asyncio.run(main())
