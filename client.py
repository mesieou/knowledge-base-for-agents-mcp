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


async def load_website_to_knowledge_base(
    website_url: str,
    database_url: str,
    business_id: str,
    category: str = "website",
    description: str = None,
    server_url: str = "http://45.151.154.42:8000/mcp",
    max_tokens: int = 8191
):
    """Load a website into the knowledge_base table with source tracking"""
    print(f"🚀 Loading website: {website_url}")
    print(f"📊 Database: {database_url[:50]}...")
    print(f"📋 Table: knowledge_base")
    print(f"🏢 Business ID: {business_id}")
    print(f"📂 Category: {category}")
    if description:
        print(f"📝 Description: {description}")
    print()

    # Connect to the streamable HTTP server
    async with streamablehttp_client(server_url) as (
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

            # Prepare tool arguments
            tool_args = {
                "sources": [website_url],
                "database_url": database_url,
                "business_id": business_id,
                "category": category,
                "max_tokens": max_tokens
            }

            # Add description if provided
            if description:
                tool_args["description"] = description

            # Call the load_documents_tool
            print("🚀 Loading documents...")
            result, duration = await timed_tool_call(session, "load_documents_tool", tool_args)
            print(f"⏱️  Completed in {duration:.3f}s")
            print(f"📝 Result: {result.content}")

            return result.content


async def main():
    """Example usage"""
    result = await load_website_to_knowledge_base(
        website_url="https://tigapropertyservices.com.au/",
        database_url="postgresql://postgres.prktfpcksfnfihsrrgnd:gPwpxnpgvBdQGCyU@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres",
        business_id="48576899-068b-4d61-b131-9ab4e599bdea",
        category="website",
        description="Tiga Property Services website content",
        server_url="http://localhost:8000/mcp"  # Use local server
    )
    print("Final result:", result)


if __name__ == "__main__":
    asyncio.run(main())
