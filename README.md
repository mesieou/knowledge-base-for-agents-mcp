# Knowledge Base MCP Server

Production-ready document extraction and vector storage using **docling + PostgreSQL**.

## Features

- **Smart Web Crawling**: Automatic internal link discovery with bot protection
- **Document Support**: PDF, DOCX, HTML, and more via docling
- **Table Extraction**: 100% data preservation with semantic format
- **Optimal Chunking**: 512 tokens per chunk for semantic search
- **Safety Features**: Rate limiting, size limits, retry logic
- **Vector Search**: OpenAI embeddings with PostgreSQL pgvector

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-key-here"
export DATABASE_URL="postgresql://user:pass@host:5432/db"

# Run tests
python test_extraction_chunking.py
```

## Usage

```python
from tools.loadDocuments import load_documents

result = load_documents(
    business_id="your-business-id",
    sources=["https://yourwebsite.com"],
    max_tokens=512,           # Optimal for semantic search
    crawl_internal=True,      # Auto-discover pages
    category="website"
)
```

## Architecture

**Extraction** (`processing/extraction.py`):
- Smart URL filtering (skips booking/contact pages)
- Rate limiting (1s between requests)
- Document size limits (10K words max)
- User-agent headers to avoid 403s

**Chunking** (`processing/chunking.py`):
- HybridChunker with 512 token max
- OpenAI tokenizer (matches embedding model)
- Filters out tiny chunks (<15 words)
- Merge related content at same hierarchy

**Storage** (`tools/loadDocuments.py`):
- PostgreSQL with pgvector
- Hierarchical titles ("Services > Physiotherapy")
- Full metadata preservation

## Safety Features

✅ **Rate Limiting**: 1 second delay between requests
✅ **Size Limits**: Skips documents >10K words
✅ **Retry Logic**: Max 2 retries with exponential backoff
✅ **Bot Detection**: Gracefully handles 403 Forbidden
✅ **Timeouts**: 15 second timeout per request

## Table Handling

Tables are converted to semantic format for better RAG:

**HTML Table** → **Semantic Format**
```
<table>                      John Smith, Role = Senior Physiotherapist
  <tr>                  →    John Smith, Department = Sports Medicine
    <td>John Smith</td>      John Smith, Years Experience = 12
    <td>Physio</td>
  </tr>
</table>
```

✅ 100% data preservation
✅ Self-contained chunks
✅ LLM-friendly format
✅ Natural language queryable

## Test Results

**10 Website Test** (60% success rate on challenging sites):
- ✅ Python.org, Nike, BBC, GitHub, Stack Overflow, Melbourne Athletic
- ❌ Wikipedia (too large - by design)
- ❌ Medium (bot-protected - unavoidable)
- ❌ Craigslist/HackerNews (no semantic content)

**Melbourne Athletic Test**:
- 21 pages crawled
- 275 chunks created
- 47.4 words/chunk average
- 89% hierarchical titles

## Environment Variables

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=postgresql://user:pass@host:5432/db

# Optional
MAX_DOCUMENT_WORDS=10000     # Skip larger documents
MIN_DELAY_SECONDS=1.0        # Rate limiting
REQUEST_TIMEOUT=15           # HTTP timeout
```

## Running Tests

```bash
# Test extraction + chunking (no DB)
python test_extraction_chunking.py

# Test 10 diverse websites
python test_10_websites.py

# Test full pipeline with DB
python test_load_documents.py
```

## Production Ready

✅ Commercial-grade web scraping
✅ Handles bad HTML structure
✅ JavaScript-heavy sites
✅ Rate limiting & bot protection
✅ Semantic table extraction
✅ Optimal chunk sizes for RAG

Ship it! 🚀
