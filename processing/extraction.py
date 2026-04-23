"""
Document extraction using docling with optimal HTML configuration
"""
import logging
import re
import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Set
from docling.document_converter import DocumentConverter
from utils.sitemap import get_sitemap_urls

logger = logging.getLogger(__name__)

# Configuration constants
MAX_DOCUMENT_WORDS = 10000  # Skip documents larger than this
MIN_DELAY_SECONDS = 1.0     # Minimum delay between requests (rate limiting)
REQUEST_TIMEOUT = 15        # Timeout for HTTP requests
MAX_RETRIES = 2             # Max retries for failed requests

# URL patterns to skip during crawling (non-content pages)
SKIP_URL_PATTERNS = [
    '/book-an-appointment',
    '/book-',
    '/booking',
    '/quick-quote',
    '/quick_quote',
    '/get-quote',
    '/privacy-policy',
    '/privacy',
    '/terms',
    '/cookie',
    '/login',
    '/signup',
    '/register',
    '/account',
    '/my-account',
    '/lost-password',
    '/search',
    '/cart',
    '/checkout',
    '?',  # Skip URLs with query parameters
    '#',  # Skip anchor links
]

# URL patterns that indicate content pages (whitelist approach)
CONTENT_URL_PATTERNS = [
    '/about',
    '/services',
    '/service',
    '/pricing',
    '/price',
    '/fees',
    '/contact',
    '/team',
    '/staff',
    '/blog',
    '/article',
    '/post',
    '/faq',
    '/help',
    '/guide',
    '/our-',
    '/what-',
    '/how-',
]

PRIORITY_PATH_PATTERNS = [
    ('', 0),
    ('/', 0),
    ('/services', 1),
    ('/service', 1),
    ('/pricing', 3),
    ('/prices', 3),
    ('/fees', 3),
    ('/about', 4),
    ('/contact', 5),
]

SERVICE_SLUG_PATTERN = re.compile(
    r"(service|repair|install|maintenance|inspection|assessment|consult|therapy|"
    r"treatment|coaching|training|class|course|program|package|hire|rental|"
    r"move|moving|mover|removal|relocation|delivery|cleaning|support|management)",
    re.IGNORECASE,
)


def attach_source_url(document, source_url: str) -> None:
    """Attach the original crawled URL so chunk persistence can trace each chunk."""
    try:
        object.__setattr__(document, "_source_url", source_url)
    except Exception:
        try:
            setattr(document, "_source_url", source_url)
        except Exception:
            logger.debug(f"Could not attach source URL to document: {source_url}")


def should_crawl_url(url: str, base_domain: str) -> bool:
    """
    Determine if a URL should be crawled based on content relevance.

    Args:
        url: The URL to check
        base_domain: The base domain for comparison

    Returns:
        True if URL should be crawled
    """
    url_lower = url.lower()

    # Skip non-content patterns
    if any(pattern in url_lower for pattern in SKIP_URL_PATTERNS):
        logger.debug(f"⏭️  Skipping (non-content): {url}")
        return False

    # If it's the homepage, always crawl
    parsed = urlparse(url)
    if parsed.path in ['', '/']:
        return True

    # Check if it matches content patterns
    has_content_pattern = any(pattern in url_lower for pattern in CONTENT_URL_PATTERNS)

    if not has_content_pattern:
        # If no explicit content pattern, only accept short paths (likely main pages)
        path_depth = len([p for p in parsed.path.split('/') if p])
        if path_depth > 2:
            logger.debug(f"⏭️  Skipping (too deep, no content pattern): {url}")
            return False

    return True


def prioritize_urls(urls: Set[str], base_url: str, max_urls: int) -> List[str]:
    """Return URLs in an order useful for onboarding extraction."""
    parsed_base = urlparse(base_url)
    canonical_base = f"{parsed_base.scheme}://{parsed_base.netloc}{parsed_base.path}".rstrip('/')

    def score(url: str) -> tuple:
        parsed = urlparse(url)
        path = (parsed.path or '/').rstrip('/').lower()
        if url.rstrip('/') == canonical_base or path in ('', '/'):
            return (0, 0, url)
        for pattern, priority in PRIORITY_PATH_PATTERNS:
            if pattern and pattern in path:
                return (priority, len(path), url)
        if SERVICE_SLUG_PATTERN.search(path):
            return (2, len(path), url)
        depth = len([part for part in path.split('/') if part])
        return (10 + depth, len(path), url)

    return sorted(urls, key=score)[:max_urls]


def preprocess_html_minimal(html_content: str) -> str:
    """
    Minimal HTML preprocessing - only remove noise elements.
    Let docling handle the rest of the structure parsing.

    Args:
        html_content: Raw HTML content

    Returns:
        Cleaned HTML content
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Only remove navigation elements (nav tag specifically)
    for tag in soup.find_all(['nav']):
        tag.decompose()

    # Remove script, style, noscript (docling does this too, but be explicit)
    for tag in soup.find_all(['script', 'style', 'noscript']):
        tag.decompose()

    # Remove common non-content classes
    noise_classes = ['cookie', 'popup', 'modal', 'advertisement', 'ad-banner']
    for noise_class in noise_classes:
        for element in soup.find_all(class_=lambda c: c and noise_class in str(c).lower()):
            element.decompose()

    # Remove elements with display:none or visibility:hidden
    for element in soup.find_all(style=lambda s: s and ('display:none' in s or 'visibility:hidden' in s)):
        element.decompose()

    return str(soup)


def find_internal_links(base_url: str, max_depth: int = 2, max_urls: int = 50) -> Set[str]:
    """Find all internal links on a website with smart filtering and rate limiting"""
    logger.info(f"🔍 Discovering internal links for: {base_url} (max_depth={max_depth}, max_urls={max_urls})")

    parsed_base = urlparse(base_url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

    visited = set()
    to_visit = {base_url}
    all_urls = set()

    last_request_time = 0  # Track last request for rate limiting

    depth = 0
    while to_visit and depth < max_depth and len(all_urls) < max_urls:
        current_level = to_visit.copy()
        to_visit.clear()

        logger.info(f"📊 Level {depth + 1}: Scanning {len(current_level)} URLs")

        for url in current_level:
            if url in visited:
                continue

            # Rate limiting: ensure minimum delay between requests
            elapsed = time.time() - last_request_time
            if elapsed < MIN_DELAY_SECONDS:
                sleep_time = MIN_DELAY_SECONDS - elapsed
                logger.debug(f"⏱️  Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

            visited.add(url)
            all_urls.add(url)

            # Try with retries
            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f"🌐 Scanning: {url}")
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    response = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
                    last_request_time = time.time()

                    response.raise_for_status()

                    soup = BeautifulSoup(response.content, 'html.parser')
                    links = soup.find_all('a', href=True)

                    found_links = []
                    for link in links:
                        href = link['href']
                        full_url = urljoin(url, href)

                        # Normalize URL (remove trailing slash, fragments, query params)
                        normalized_url = full_url.rstrip('/').split('#')[0].split('?')[0]

                        # Also normalize the comparison URL for duplicate detection
                        parsed = urlparse(normalized_url)
                        # Remove www. prefix for comparison to catch www/non-www duplicates
                        domain_normalized = parsed.netloc.replace('www.', '')
                        canonical_url = f"{parsed.scheme}://{domain_normalized}{parsed.path}".rstrip('/')

                        # Only include internal links from same domain
                        if domain_normalized == urlparse(base_domain).netloc.replace('www.', ''):
                            # Check if we should crawl this URL
                            if canonical_url not in visited and len(all_urls) < max_urls:
                                if should_crawl_url(normalized_url, base_domain):
                                    to_visit.add(normalized_url)
                                    found_links.append(normalized_url)

                    if found_links:
                        logger.info(f"   📎 Found {len(found_links)} relevant links")
                        for link in found_links[:3]:  # Show first 3
                            logger.info(f"      → {link}")
                        if len(found_links) > 3:
                            logger.info(f"      ... and {len(found_links) - 3} more")
                    else:
                        logger.info(f"   📎 No new relevant links found")

                    break  # Success, exit retry loop

                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        logger.warning(f"⚠️  Bot protection detected (403): {url}")
                        break  # Don't retry on 403
                    elif attempt < MAX_RETRIES - 1:
                        logger.warning(f"⚠️  HTTP error {e.response.status_code}, retrying... ({attempt + 1}/{MAX_RETRIES})")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    else:
                        logger.warning(f"❌ Failed after {MAX_RETRIES} attempts: {url}")

                except requests.exceptions.Timeout:
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"⚠️  Timeout, retrying... ({attempt + 1}/{MAX_RETRIES})")
                        time.sleep(2 ** attempt)
                    else:
                        logger.warning(f"❌ Timeout after {MAX_RETRIES} attempts: {url}")

                except Exception as e:
                    logger.warning(f"❌ Error scanning {url}: {e}")
                    break

        depth += 1

    # Check if we hit the URL limit
    if len(all_urls) >= max_urls:
        logger.warning(f"🚨 Reached maximum URL limit ({max_urls}). Stopping discovery.")

    logger.info(f"🎯 Discovery complete: Found {len(all_urls)} content URLs across {depth} levels")

    # Log the final unique URLs
    logger.info(f"📋 Final URLs to extract:")
    for i, url in enumerate(sorted(all_urls), 1):
        logger.info(f"   {i}. {url}")

    return all_urls


def extract_documents(
    sources: List[str],
    crawl_internal: bool = True,
    max_document_words: int = MAX_DOCUMENT_WORDS,
    max_pages: int = 50
) -> List:
    """
    Extract documents from various sources using docling with optimal configuration.

    Args:
        sources: List of URLs or file paths
        crawl_internal: Whether to crawl internal links for websites
        max_document_words: Maximum words per document (skip larger docs)

    Returns:
        List of DoclingDocument objects
    """
    # Create converter - HTML preprocessing handles optimization
    # Note: HTMLBackendOptions configuration moved to preprocessing step
    converter = DocumentConverter()

    documents = []

    # Expand sources to include internal links if requested
    all_sources = set(sources)

    if crawl_internal:
        for source in sources:
            if source.startswith('http'):
                logger.info(f"🕷️  Crawling website: {source}")
                internal_urls = find_internal_links(source, max_urls=max_pages)
                all_sources.update(internal_urls)
                logger.info(f"📈 Expanded from 1 to {len(internal_urls)} URLs")

    ordered_sources = prioritize_urls(all_sources, sources[0], max_pages)
    logger.info(f"📄 Starting extraction of {len(ordered_sources)} total sources")

    last_request_time = 0  # Track for rate limiting

    for i, source in enumerate(ordered_sources, 1):
        try:
            logger.info(f"📖 [{i}/{len(ordered_sources)}] Extracting: {source}")

            # For HTML sources, preprocess to remove noise
            if source.startswith('http'):
                # Rate limiting
                elapsed = time.time() - last_request_time
                if elapsed < MIN_DELAY_SECONDS:
                    time.sleep(MIN_DELAY_SECONDS - elapsed)

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                response = requests.get(source, timeout=REQUEST_TIMEOUT, headers=headers)
                last_request_time = time.time()
                response.raise_for_status()

                # Minimal preprocessing
                cleaned_html = preprocess_html_minimal(
                    response.content.decode('utf-8', errors='ignore')
                )

                # Check document size BEFORE processing
                text_length = len(BeautifulSoup(cleaned_html, 'html.parser').get_text().split())
                if text_length > max_document_words:
                    logger.warning(
                        f"⚠️  Skipping large document: {source} "
                        f"({text_length:,} words > {max_document_words:,} limit)"
                    )
                    continue

                # Save to temp file for docling to process
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(cleaned_html)
                    temp_path = temp_file.name

                try:
                    result = converter.convert(temp_path)
                finally:
                    # Clean up temp file
                    import os
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            else:
                # For PDFs and local files, use normal conversion
                result = converter.convert(source)

            if result.document:
                # Double-check document size after conversion
                doc_text = result.document.export_to_markdown()
                doc_word_count = len(doc_text.split())

                if doc_word_count > max_document_words:
                    logger.warning(
                        f"⚠️  Skipping large converted document: {source} "
                        f"({doc_word_count:,} words > {max_document_words:,} limit)"
                    )
                    continue

                attach_source_url(result.document, source)
                documents.append(result.document)
                # Log some basic info about what was extracted
                logger.info(
                    f"✅ Extracted {len(doc_text)} chars "
                    f"({doc_word_count} words): {doc_text[:100]}..."
                )
            else:
                logger.warning(f"⚠️  No content from: {source}")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error(f"❌ Bot protection (403 Forbidden): {source}")
            else:
                logger.error(f"❌ HTTP error {e.response.status_code}: {source}")
        except requests.exceptions.Timeout:
            logger.error(f"❌ Request timeout: {source}")
        except Exception as e:
            logger.error(f"❌ Error extracting {source}: {e}")
            continue

    logger.info(f"🎉 Extraction complete: {len(documents)} documents from {len(ordered_sources)} sources")
    return documents


def extract_from_sitemap(base_url: str) -> List:
    """Extract documents from all URLs in a sitemap"""
    sitemap_urls = get_sitemap_urls(base_url)
    # Filter sitemap URLs using same criteria
    filtered_urls = [url for url in sitemap_urls if should_crawl_url(url, base_url)]
    logger.info(f"📋 Filtered sitemap: {len(filtered_urls)}/{len(sitemap_urls)} URLs")
    return extract_documents(filtered_urls, crawl_internal=False)


# For testing
if __name__ == "__main__":
    # Test basic extraction
    docs = extract_documents(["https://arxiv.org/pdf/2408.09869"], crawl_internal=False)
    print(f"Extracted {len(docs)} documents")
