import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

let client: Client|undefined = undefined
const baseUrl = new URL("http://knowledge-base-for-agents-mcp-production.up.railway.app/mcp");

try {
  client = new Client({
    name: 'streamable-http-client',
    version: '1.0.0'
  });
  const transport = new StreamableHTTPClientTransport(
    new URL(baseUrl)
  );
  await client.connect(transport);
  console.log("Connected using Streamable HTTP transport");
} catch (error) {
  // If that fails with a 4xx error, try the older SSE transport
  console.log("Streamable HTTP connection failed, falling back to SSE transport");
  client = new Client({
    name: 'sse-client',
    version: '1.0.0'
  });
  const sseTransport = new SSEClientTransport(baseUrl);
  await client.connect(sseTransport);
  console.log("Connected using SSE transport");
}

// Test the MCP server functionality
if (client) {
  try {
    // List available tools
    const tools = await client.listTools();
    console.log("Available tools:", JSON.stringify(tools, null, 2));

    // Test the fetch-weather tool if it exists
    if (tools.tools && tools.tools.length > 0) {
      const weatherTool = tools.tools.find(tool => tool.name === "fetch-weather");
      if (weatherTool) {
        console.log("Testing fetch-weather tool...");
        const weatherResult = await client.callTool({
          name: "fetch-weather",
          arguments: { city: "New York" }
        });
        console.log("Weather tool result:", JSON.stringify(weatherResult, null, 2));
      }
    }

    // Close the connection gracefully
    await client.close();
    console.log("Connection closed successfully");

  } catch (error) {
    console.error("Error testing MCP functionality:", error);
  }
}
