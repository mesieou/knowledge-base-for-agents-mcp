import os
import contextlib
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
from dotenv import load_dotenv
import uvicorn

load_dotenv("../.env")

# Get port from Railway's environment variable (with fallback for local dev)
port = int(os.getenv("PORT", "8080"))

# Create MCP server with stateless HTTP (as per GitHub issue solution)
mcp = FastMCP(
    "Calculator",
    stateless_http=True,
)

@asynccontextmanager
async def lifespan(_: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(mcp.session_manager.run())
        yield

app = FastAPI(lifespan=lifespan)

# Mount the MCP endpoints
app.mount("/", mcp.streamable_http_app())

# Add a simple calculator tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

# Run the server using uvicorn (as per GitHub issue solution)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=port)
