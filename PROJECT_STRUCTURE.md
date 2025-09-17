# Knowledge Base MCP - Project Structure

## 📁 Project Organization

```
knowledge-base-mcp/
├── 🚀 server.py                    # Main MCP server
├── 🧪 test_load_documents.py       # Integration tests
├── 📋 requirements.txt             # Python dependencies
├── 📖 README_LOAD_DOCUMENTS.md     # Documentation
├── 🐳 Dockerfile                   # Container setup
├── 🐳 docker-compose.yml           # Multi-container setup
├── 🚂 railway.toml                 # Railway deployment config
│
├── 🔧 tools/                       # MCP Tools
│   ├── __init__.py
│   └── loadDocuments.py            # Main orchestrator tool
│
├── 📄 docling/                     # Document processing pipeline
│   ├── __init__.py
│   ├── extraction.py               # Document extraction
│   ├── chunking.py                 # Text chunking
│   └── embedding.py                # Embeddings & storage
│
└── 🛠️ utils/                       # Shared utilities
    ├── __init__.py
    ├── tokenizer.py                # OpenAI tokenizer wrapper
    └── sitemap.py                  # Sitemap parsing
```

## 🔄 Data Flow

```
Sources → Extract → Chunk → Embed → Store
   ↓         ↓        ↓       ↓       ↓
[URLs]  [Documents] [Chunks] [Vectors] [Supabase]
```

## 📦 Module Responsibilities

### 🚀 **server.py**
- MCP server setup and configuration
- Tool registration and routing
- Docker/Railway deployment ready

### 🔧 **tools/loadDocuments.py**
- Thin orchestrator that coordinates the pipeline
- Environment variable handling
- Error management and reporting

### 📄 **docling/ package**
- **extraction.py**: Document conversion using docling
- **chunking.py**: Text chunking with HybridChunker
- **embedding.py**: OpenAI embeddings + PostgreSQL storage

### 🛠️ **utils/ package**
- **tokenizer.py**: OpenAI-compatible tokenizer for chunking
- **sitemap.py**: Website sitemap parsing utilities

## 🔌 Import Structure

```python
# Clean imports
from tools import load_documents
from docling import extract_documents, chunk_documents
from utils import OpenAITokenizerWrapper
```

## 🧪 Testing

```bash
# Test individual components
python docling/extraction.py
python docling/chunking.py
python docling/embedding.py

# Test full pipeline
python tools/loadDocuments.py

# Test MCP integration
python test_load_documents.py
```

## 🚀 Deployment

```bash
# Local development
python server.py

# Docker
docker-compose up

# Railway
railway up
```

This structure follows Python best practices with clear separation of concerns and modular design.
