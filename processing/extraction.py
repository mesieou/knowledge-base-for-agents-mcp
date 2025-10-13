"""
Document extraction using docling
"""
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Set
from docling.document_converter import DocumentConverter
from utils.sitemap import get_sitemap_urls

logger = logging.getLogger(__name__)


def find_internal_links(base_url: str, max_depth: int = 2, max_urls: int = 50) -> Set[str]:
    """Find all internal links on a website"""
    logger.info(f"🔍 Discovering internal links for: {base_url} (max_depth={max_depth}, max_urls={max_urls})")

    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

    visited = set()
    to_visit = {base_url}
    all_urls = set()

    depth = 0
    while to_visit and depth < max_depth and len(all_urls) < max_urls:
        current_level = to_visit.copy()
        to_visit.clear()

        logger.info(f"📊 Level {depth + 1}: Scanning {len(current_level)} URLs")

        for url in current_level:
            if url in visited:
                continue

            visited.add(url)
            all_urls.add(url)

            try:
                logger.info(f"🌐 Scanning: {url}")
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')
                links = soup.find_all('a', href=True)

                found_links = []
                for link in links:
                    href = link['href']
                    full_url = urljoin(url, href)

                    # Normalize URL (remove trailing slash, fragments)
                    normalized_url = full_url.rstrip('/').split('#')[0]

                    # Only include internal links
                    if urlparse(normalized_url).netloc == parsed_base.netloc:
                        # Skip anchors, files, and common non-content pages
                        if not any(skip in normalized_url.lower() for skip in ['#', '.pdf', '.jpg', '.png', '.css', '.js', 'mailto:', 'tel:']):
                            if normalized_url not in visited and len(all_urls) < max_urls:
                                to_visit.add(normalized_url)
                                found_links.append(normalized_url)

                if found_links:
                    logger.info(f"   📎 Found {len(found_links)} new internal links")
                    for link in found_links[:5]:  # Show first 5
                        logger.info(f"      → {link}")
                    if len(found_links) > 5:
                        logger.info(f"      ... and {len(found_links) - 5} more")
                else:
                    logger.info(f"   📎 No new internal links found")

            except Exception as e:
                logger.warning(f"❌ Error scanning {url}: {e}")
                continue

        depth += 1

    # Check if we hit the URL limit
    if len(all_urls) >= max_urls:
        logger.warning(f"🚨 Reached maximum URL limit ({max_urls}). Stopping discovery.")

    logger.info(f"🎯 Discovery complete: Found {len(all_urls)} total URLs across {depth} levels")

    # Log the final unique URLs
    logger.info(f"📋 Final unique URLs to extract:")
    for i, url in enumerate(sorted(all_urls), 1):
        logger.info(f"   {i}. {url}")

    return all_urls


def extract_documents(sources: List[str], crawl_internal: bool = True) -> List:
    """Extract documents from various sources using docling"""
    converter = DocumentConverter()
    documents = []

    # Expand sources to include internal links if requested
    all_sources = set(sources)

    if crawl_internal:
        for source in sources:
            if source.startswith('http'):
                logger.info(f"🕷️ Crawling website: {source}")
                internal_urls = find_internal_links(source)
                all_sources.update(internal_urls)
                logger.info(f"📈 Expanded from 1 to {len(internal_urls)} URLs")

    logger.info(f"📄 Starting extraction of {len(all_sources)} total URLs")

    for i, source in enumerate(all_sources, 1):
        try:
            logger.info(f"📖 [{i}/{len(all_sources)}] Extracting: {source}")
            result = converter.convert(source)
            if result.document:
                documents.append(result.document)
                # Log some basic info about what was extracted
                doc_text = result.document.export_to_markdown()[:200]
                logger.info(f"✅ Extracted {len(doc_text)} chars: {doc_text[:100]}...")
            else:
                logger.warning(f"⚠️ No content from: {source}")
        except Exception as e:
            logger.error(f"❌ Error extracting {source}: {e}")
            continue

    logger.info(f"🎉 Extraction complete: {len(documents)} documents from {len(all_sources)} URLs")
    return documents


def extract_from_sitemap(base_url: str) -> List:
    """Extract documents from all URLs in a sitemap"""
    sitemap_urls = get_sitemap_urls(base_url)
    print(sitemap_urls)
    return extract_documents(sitemap_urls)


# For testing
if __name__ == "__main__":
    # Test basic extraction
    docs = extract_documents(["https://arxiv.org/pdf/2408.09869"])
    print(f"Extracted {len(docs)} documents")
