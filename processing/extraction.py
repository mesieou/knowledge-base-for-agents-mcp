"""
Document extraction using docling
"""
from typing import List, Optional
from docling.document_converter import DocumentConverter
from utils.sitemap import get_sitemap_urls


def extract_documents(sources: List[str]) -> List:
    """Extract documents from various sources using docling"""
    converter = DocumentConverter()
    documents = []

    for source in sources:
        try:
            print(f"Extracting: {source}")
            result = converter.convert(source)
            if result.document:
                documents.append(result.document)
                print(f"✅ Extracted: {source}")
            else:
                print(f"⚠️ No content from: {source}")
        except Exception as e:
            print(f"❌ Error extracting {source}: {e}")
            continue

    return documents


def extract_from_sitemap(base_url: str) -> List:
    """Extract documents from all URLs in a sitemap"""
    sitemap_urls = get_sitemap_urls(base_url)
    return extract_documents(sitemap_urls)


# For testing
if __name__ == "__main__":
    # Test basic extraction
    docs = extract_documents(["https://arxiv.org/pdf/2408.09869"])
    print(f"Extracted {len(docs)} documents")
