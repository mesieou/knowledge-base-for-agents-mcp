# Knowledge Base MCP Server

A production-ready MCP server for document processing and vector storage using **docling + Supabase/PostgreSQL**.

## Features

- **Document Support**: PDF, DOCX, PPTX, XLSX, HTML, WAV, MP3, PNG, TIFF, JPEG, and more
- **Content Extraction**: Uses `docling.DocumentConverter` for robust document parsing
- **Smart Chunking**: Uses `docling.chunking.HybridChunker` with configurable token limits
- **Vector Embeddings**: Automatic embeddings using OpenAI's `text-embedding-3-large` via LanceDB
- **Simple Storage**: Uses LanceDB with built-in OpenAI embedding integration
- **Automatic Table Naming**: Generates unique table names with timestamps and UUIDs

## Environment Variables

Only **one required** environment variable:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional (defaults to data/lancedb)
DATABASE_URL=data/lancedb

# Optional (if not providing sources as parameters)
SOURCES=https://arxiv.org/pdf/2408.09869,/path/to/document.pdf,https://example.com/page.html
```

## Usage

The tool can be called in several ways:

### 1. Using Environment Variables
```python
# Set env vars and call with no parameters
result = load_documents_tool()
```

### 2. Providing Sources Directly
```python
sources = [
    "https://arxiv.org/pdf/2408.09869",
    "/path/to/local/document.pdf",
    "https://example.com/page.html"
]
result = load_documents_tool(sources=sources)
```

### 3. Custom Configuration
```python
result = load_documents_tool(
    sources=["document.pdf"],
    table_name="my_custom_table",
    max_tokens=4096
)
```

## Output

The tool returns a dictionary with:

```python
{
    "table_name": "documents_1695123456_abc12345",
    "row_count": 150,
    "stored_files": ["document1.pdf", "document2.html"],
    "total_sources": 3,
    "successful_sources": 2,
    "failed_sources": 1
}
```

## Database Schema

### LanceDB (Simple & Powerful)
- `text`: Chunk content (automatically embedded by LanceDB)
- `vector`: Embedding vector (auto-generated using OpenAI text-embedding-3-large)
- `metadata`: JSON with filename, page_numbers, title
  - `filename`: Original document filename
  - `page_numbers`: List of page numbers where chunk appears
  - `title`: Section heading/title if available

## Architecture

Simple and clean:

- **`docling/loadUnstructuredInfo.py`**: Main tool using docling + LanceDB
- **`utils/tokenizer.py`**: OpenAI tokenizer wrapper for chunking
- **`server.py`**: MCP server with tool registration

## Quick Start

1. **Setup environment:**
```bash
python setup.py  # Installs deps and creates .env.example
cp .env.example .env  # Copy and edit with your values
```

2. **Configure environment variables:**
```bash
DATABASE_URL=postgresql://user:pass@db.supabase.co:5432/postgres
OPENAI_API_KEY=your_openai_key_here
SOURCES=https://arxiv.org/pdf/2408.09869  # Optional
```

3. **Run the server:**
```bash
python server.py
```

4. **Test the tool:**
```bash
python test_load_documents.py
```

The `load_documents_tool` will be available in your MCP client.

## Why This Approach?

- **Simple**: Uses docling's built-in LanceDB integration (no complex database adapters)
- **Powerful**: Automatic embeddings, vector search, and metadata extraction
- **Reliable**: Built on proven docling + LanceDB stack
- **Fast**: LanceDB's optimized vector storage and retrieval
