import asyncio
import nest_asyncio
import logging
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

nest_asyncio.apply()  # Needed to run interactive python

"""
Make sure:
1. The server is running before running this script.
2. The server is configured to use streamable-http transport.
3. The server is listening on port 8050.

To run the server:
uv run server.py
"""


async def main():
    try:
        logger.info("Starting MCP client connection...")

        # Connect to the server using Streamable HTTP
        logger.info("Connecting to: https://knowledge-base-for-agents-mcp-production.up.railway.app/mcp")

        async with streamablehttp_client("https://knowledge-base-for-agents-mcp-production.up.railway.app/mcp") as (
            read_stream,
            write_stream,
            get_session_id,
        ):
            logger.info("Successfully connected to server!")

            # Get and log the session ID
            session_id = get_session_id()
            logger.info(f"Session ID: {session_id}")

            async with ClientSession(read_stream, write_stream) as session:
                # Initialize the connection
                logger.info("Initializing MCP session...")
                await session.initialize()
                logger.info("Session initialized successfully!")

                # List available tools
                logger.info("Requesting tools list...")
                tools_result = await session.list_tools()
                logger.info(f"Received {len(tools_result.tools)} tools")

                print("Available tools:")
                for tool in tools_result.tools:
                    print(f"  - {tool.name}: {tool.description}")

                # Call our calculator tool
                logger.info("Calling add tool with a=2, b=3...")
                result = await session.call_tool("add", arguments={"a": 2, "b": 3})
                print(f"2 + 3 = {result.content[0].text}")
                logger.info("Tool call completed successfully!")

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        logger.error(f"Error type: {type(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
