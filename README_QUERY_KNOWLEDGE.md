# Query Knowledge Base Tool

This document explains how to use the `query_knowledge_tool` to retrieve information from your knowledge base using vector similarity search.

## Overview

The `query_knowledge_tool` allows you to:
- Ask natural language questions about your business data
- Get AI-generated answers based on your knowledge base
- Retrieve source documents with similarity scores
- Filter results by business ID for multi-tenant scenarios

## Architecture

```
Question → Embedding → Vector Search → Context Retrieval → GPT Answer
```

1. **Question Embedding**: Converts your question to a vector using OpenAI's `text-embedding-3-small`
2. **Vector Search**: Uses pgvector's cosine similarity to find relevant documents
3. **Context Retrieval**: Retrieves top N most similar documents above threshold
4. **GPT Answer**: Uses `gpt-4o-mini` to generate a contextual answer

## Tool Parameters

```typescript
{
  question: string,           // The question to answer
  table_name: string,         // Table containing embeddings (e.g., "documents")
  database_url: string,       // PostgreSQL connection string
  business_id: string,        // Business ID to scope the search
  match_threshold?: number,   // Minimum similarity (0-1, default: 0.7)
  match_count?: number        // Max results to return (default: 3)
}
```

## Return Format

```typescript
{
  answer: string,              // AI-generated answer
  sources: Array<{             // Source documents used
    text: string,
    similarity: number,
    metadata: object
  }>,
  context_count: number,       // Number of sources found
  business_id: string,
  table_name: string,
  error?: string               // Error message if failed
}
```

## Usage Examples

### Example 1: Basic Query via TypeScript Client

```typescript
import { KnowledgeBaseManager } from './knowledge-base-manager';

const manager = KnowledgeBaseManager.fromEnv();

const result = await manager.queryKnowledge({
  question: "What are your business hours?",
  databaseUrl: process.env.DATABASE_URL!,
  businessId: "my-business-123",
  tableName: "documents",
  matchThreshold: 0.7,  // Optional
  matchCount: 3         // Optional
});

console.log('Answer:', result.answer);
console.log('Sources:', result.sources);
```

### Example 2: Direct MCP Tool Call

```typescript
// Using MCP client directly
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

const transport = new StreamableHTTPClientTransport(
  new URL('http://localhost:8000/mcp')
);

const client = new Client({
  name: 'query-client',
  version: '1.0.0'
}, {
  capabilities: {}
});

await client.connect(transport);

const result = await client.callTool({
  name: 'query_knowledge_tool',
  arguments: {
    question: "What are your business hours?",
    table_name: "documents",
    database_url: process.env.DATABASE_URL,
    business_id: "my-business-123",
    match_threshold: 0.7,
    match_count: 3
  }
});

console.log(result.content);
```

### Example 3: Python Test Script

```python
# See test_query_knowledge.py for a complete example
python test_query_knowledge.py
```

## Configuration

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@host:5432/db
OPENAI_API_KEY=sk-...

# Optional (for MCP server)
MCP_SERVER_URL=http://localhost:8000/mcp
```

### Database Schema

The tool expects a table with the following structure:

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id TEXT,
    text TEXT NOT NULL,
    vector vector(1536),
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Required indexes
CREATE INDEX documents_vector_idx
  ON documents USING ivfflat (vector vector_cosine_ops);

CREATE INDEX documents_business_idx
  ON documents (business_id);
```

## Performance Tuning

### Match Threshold

- **0.5-0.6**: Very broad search, may include less relevant results
- **0.7** (default): Balanced relevance
- **0.8-0.9**: High precision, may miss some relevant content

### Match Count

- **1-3**: Fast, focused answers
- **5-10**: More comprehensive context
- **10+**: Slower, use for complex queries requiring broad context

## Error Handling

The tool handles errors gracefully:

```typescript
if (result.error) {
  console.error('Query failed:', result.error);
}

if (result.sources.length === 0) {
  console.log('No relevant information found');
}
```

Common errors:
- Missing `OPENAI_API_KEY`
- Invalid `database_url`
- Table doesn't exist
- No documents for the given `business_id`

## Integration with Skedy AI

The tool is already integrated with the Skedy AI `KnowledgeBaseManager`:

```typescript
// In your Next.js API route or server action
import { KnowledgeBaseManager } from '@/features/knowledge-base/lib/knowledge-base-manager';

export async function answerQuestion(question: string, businessId: string) {
  const manager = KnowledgeBaseManager.fromEnv();

  const result = await manager.queryKnowledge({
    question,
    databaseUrl: process.env.DATABASE_URL!,
    businessId,
    tableName: 'documents',
    matchThreshold: 0.7,
    matchCount: 3
  });

  return result;
}
```

## Testing

1. **Load some documents first**:
```bash
python test_load_documents.py
```

2. **Query the knowledge base**:
```bash
python test_query_knowledge.py
```

3. **Test via HTTP**:
```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "query_knowledge_tool",
      "arguments": {
        "question": "What are your business hours?",
        "table_name": "documents",
        "database_url": "postgresql://...",
        "business_id": "test_business",
        "match_threshold": 0.7,
        "match_count": 3
      }
    },
    "id": 1
  }'
```

## Best Practices

1. **Use descriptive business IDs**: Helps with multi-tenant filtering
2. **Adjust thresholds based on content**: Technical docs may need lower thresholds
3. **Monitor similarity scores**: Helps tune match_threshold for your use case
4. **Cache frequent queries**: Consider caching common questions
5. **Update knowledge base regularly**: Re-load documents when business info changes

## Troubleshooting

### "No matching documents found"

- Check if documents were loaded with correct `business_id`
- Lower the `match_threshold` (try 0.5)
- Verify the question is related to loaded content

### "Connection error"

- Ensure MCP server is running: `python server.py`
- Check `MCP_SERVER_URL` is correct
- Verify network connectivity

### "Slow queries"

- Reduce `match_count` to fewer documents
- Ensure pgvector indexes are created
- Consider using connection pooling for high load

## Next Steps

- Integrate with chatbot interface
- Add conversation history for context
- Implement query analytics
- Add semantic caching layer
