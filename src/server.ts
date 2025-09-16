import express from "express";
import { randomUUID } from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

const app = express();
app.use(express.json());

// Health check endpoint for Railway
app.get("/health", (req, res) => {
  res.status(200).json({ status: "healthy", timestamp: new Date().toISOString() });
});

// Map to store transports by session ID
const transports: { [sessionId: string]: StreamableHTTPServerTransport } = {};

// Handle POST requests for client-to-server communication
app.post("/mcp", async (req, res) => {
  // Check for existing session ID
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  let transport: StreamableHTTPServerTransport;

  if (sessionId && transports[sessionId]) {
    // Reuse existing transport
    transport = transports[sessionId];
  } else if (!sessionId && isInitializeRequest(req.body)) {
    // New initialization request
    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (sessionId) => {
        // Store the transport by session ID
        transports[sessionId] = transport;
      },
      // DNS rebinding protection is disabled by default for backwards compatibility. If you are running this server
      // locally, make sure to set:
      // enableDnsRebindingProtection: true,
      // allowedHosts: ['127.0.0.1'],
    });

    // Clean up transport when closed
    transport.onclose = () => {
      if (transport.sessionId) {
        delete transports[transport.sessionId];
      }
    };

    // Create and configure the MCP server
    const server = new McpServer({
      name: "railway-mcp",
      version: "1.0.0",
    });

    // Register tools
    server.registerTool(
      "fetch-weather",
      {
        title: "Weather Fetcher",
        description: "Get weather data for a city",
        inputSchema: { city: z.string() }
      },
      async ({ city }) => {
        try {
          const response = await fetch(`https://api.weather.com/${city}`);
          const data = await response.text();
          return {
            content: [{ type: "text", text: data }]
          };
        } catch (error) {
          return {
            content: [{ type: "text", text: `Weather API error: ${error.message}` }]
          };
        }
      }
    );

    // Connect to the MCP server with error handling
    try {
      await server.connect(transport);
      console.error(`✅ MCP server connected for session`);
    } catch (error) {
      console.error(`❌ MCP server connection failed:`, error);
      throw error;
    }
  } else {
    // Invalid request
    res.status(400).json({
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Bad Request: No valid session ID provided",
      },
      id: null,
    });
    return;
  }

  // Handle the request
  await transport.handleRequest(req, res, req.body);
});

// Reusable handler for GET and DELETE requests
const handleSessionRequest = async (
  req: express.Request,
  res: express.Response
) => {
  const sessionId = req.headers["mcp-session-id"] as string | undefined;
  if (!sessionId || !transports[sessionId]) {
    res.status(400).send("Invalid or missing session ID");
    return;
  }

  const transport = transports[sessionId];
  await transport.handleRequest(req, res);
};

// Handle GET requests for server-to-client notifications via SSE
app.get("/mcp", handleSessionRequest);

// Handle DELETE requests for session termination
app.delete("/mcp", handleSessionRequest);

// Debug Railway environment
console.error("Environment variables:");
console.error("PORT:", process.env.PORT);
console.error("NODE_ENV:", process.env.NODE_ENV);
console.error("All Railway vars:", Object.keys(process.env).filter(k => k.includes('RAILWAY')));

const port = parseInt(process.env.PORT || "8080");
console.error(`Attempting to bind to port: ${port}`);

app.listen(port, "0.0.0.0", () => {
  console.error(`✅ MCP server successfully running on http://0.0.0.0:${port}`);
}).on('error', (err) => {
  console.error(`❌ Server failed to start:`, err);
});
