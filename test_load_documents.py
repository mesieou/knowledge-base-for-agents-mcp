#!/usr/bin/env python3
"""
Test script for the load_documents tool using docling + Supabase/PostgreSQL
"""
import os
import sys
from dotenv import load_dotenv

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.loadDocuments import load_documents

def test_load_documents():
    """Test the load_documents function with Supabase/PostgreSQL"""

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    database_url = os.getenv("DATABASE_URL")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not database_url:
        print("❌ Missing DATABASE_URL environment variable")
        print("\nPlease set:")
        print("DATABASE_URL=postgresql://user:pass@db.supabase.co:5432/postgres")
        return False

    if not openai_key:
        print("❌ Missing OPENAI_API_KEY environment variable")
        print("\nPlease set:")
        print("OPENAI_API_KEY=your_openai_key_here")
        return False

    print("🧪 Testing load_documents with Supabase/PostgreSQL...")
    print(f"Database: {database_url[:50]}...")

    try:
        # Test with a sample document
        test_sources = ["https://arxiv.org/pdf/2408.09869"]

        print(f"\n📄 Processing: {test_sources[0]}")
        result = load_documents(
            sources=test_sources,
            table_name="test_supabase",
            max_tokens=4000
        )

        print("\n✅ Success! Results:")
        print(f"  Table: {result['table_name']}")
        print(f"  Chunks: {result['row_count']}")
        print(f"  Files: {result['stored_files']}")
        print(f"  Success: {result['successful_sources']}/{result['total_sources']}")

        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_load_documents()
    sys.exit(0 if success else 1)
