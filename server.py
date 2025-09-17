from typing import Dict, List, Optional, Any
from mcp.server.fastmcp import FastMCP
from tools.loadDocuments import load_documents

# Create MCP server
mcp = FastMCP(
    name="KnowledgeBaseMCP",
    host="0.0.0.0",  # Docker-ready
    port=8000,
)

@mcp.tool()
def load_documents_tool(
    sources: Optional[List[str]] = None,
    table_name: Optional[str] = None,
    max_tokens: int = 8191
) -> Dict[str, Any]:
    return load_documents(sources=sources, table_name=table_name, max_tokens=max_tokens)

if __name__ == "__main__":
    # Now FastMCP should bind to 0.0.0.0:8000 properly!
    print("🚀 Starting FastMCP with host=0.0.0.0:8000")
    mcp.run(transport="streamable-http")
