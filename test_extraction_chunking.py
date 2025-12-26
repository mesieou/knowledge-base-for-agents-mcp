"""
Test extraction and chunking without database - validates the core improvements
"""
import sys
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, '/Users/juanbernal/Coding/knowledge-base-mcp')

from processing.extraction import extract_documents
from processing.chunking import chunk_documents

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Test configuration
TEST_URL = "https://www.melbourneathleticdevelopment.com.au/"
MAX_TOKENS = 512


def analyze_chunks(chunks):
    """Analyze chunk quality"""
    if not chunks:
        return {"error": "No chunks created"}

    # Extract all text and metadata
    titles = []
    contents = []
    headings_list = []

    for chunk in chunks:
        contents.append(chunk.text)

        # Get title from metadata
        if chunk.meta and chunk.meta.headings:
            headings_list.append(chunk.meta.headings)
            if len(chunk.meta.headings) > 1:
                titles.append(" > ".join(chunk.meta.headings[-2:]))
            else:
                titles.append(chunk.meta.headings[0])
        else:
            titles.append("No title")

    # Statistics
    word_counts = [len(content.split()) for content in contents]
    char_counts = [len(content) for content in contents]

    avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
    min_words = min(word_counts) if word_counts else 0
    max_words = max(word_counts) if word_counts else 0
    avg_chars = sum(char_counts) / len(char_counts) if char_counts else 0

    # Check for key content
    all_content = " ".join(contents).lower()

    # Check for hierarchical titles
    hierarchical_titles = [t for t in titles if " > " in t]

    # Check for problematic patterns
    has_stats_fragmented = any(
        ("years" in c.lower() and len(c.split()) < 10) or
        ("experience" in c.lower() and len(c.split()) < 10)
        for c in contents
    )

    has_right_txt = any("right txt" in c.lower() for c in contents)

    return {
        "total_chunks": len(chunks),
        "statistics": {
            "avg_words_per_chunk": round(avg_words, 1),
            "min_words": min_words,
            "max_words": max_words,
            "avg_chars_per_chunk": round(avg_chars, 1),
        },
        "content_quality": {
            "has_physio_content": "physio" in all_content,
            "has_team_info": "team" in all_content or "staff" in all_content,
            "has_services": "service" in all_content,
            "no_right_txt_artifact": not has_right_txt,
            "no_fragmented_stats": not has_stats_fragmented,
        },
        "hierarchical_titles": {
            "count": len(hierarchical_titles),
            "examples": hierarchical_titles[:5],
        },
        "unique_titles": len(set(titles)),
        "example_chunks": [
            {
                "title": titles[i] if i < len(titles) else "N/A",
                "headings": headings_list[i] if i < len(headings_list) else [],
                "content_preview": contents[i][:200] + "...",
                "word_count": word_counts[i],
            }
            for i in range(min(5, len(chunks)))
        ]
    }


def print_report(analysis):
    """Print formatted analysis report"""
    print("\n" + "="*80)
    print("📊 EXTRACTION & CHUNKING ANALYSIS")
    print("="*80)

    if "error" in analysis:
        print(f"❌ ERROR: {analysis['error']}")
        return

    print(f"\n📈 BASIC STATISTICS:")
    print(f"  Total Chunks: {analysis['total_chunks']}")
    print(f"  Unique Titles: {analysis['unique_titles']}")
    print(f"  Hierarchical Titles: {analysis['hierarchical_titles']['count']}")

    stats = analysis['statistics']
    print(f"\n📏 CHUNK SIZE METRICS:")
    print(f"  Average Words/Chunk: {stats['avg_words_per_chunk']}")
    print(f"  Min Words: {stats['min_words']}")
    print(f"  Max Words: {stats['max_words']}")
    print(f"  Average Chars/Chunk: {stats['avg_chars_per_chunk']}")

    print(f"\n✅ QUALITY CHECKS:")
    for check, passed in analysis['content_quality'].items():
        status = "✅" if passed else "❌"
        print(f"  {status} {check.replace('_', ' ').title()}: {passed}")

    if analysis['hierarchical_titles']['examples']:
        print(f"\n🏷️  HIERARCHICAL TITLE EXAMPLES:")
        for title in analysis['hierarchical_titles']['examples']:
            print(f"  • {title}")

    print(f"\n📝 EXAMPLE CHUNKS (First 5):")
    for i, example in enumerate(analysis['example_chunks'], 1):
        print(f"\n  [{i}] Title: {example['title']}")
        if example['headings']:
            print(f"      Full Hierarchy: {' > '.join(example['headings'])}")
        print(f"      Words: {example['word_count']}")
        print(f"      Preview: {example['content_preview']}")

    # Quality assessment
    print(f"\n" + "="*80)
    quality_issues = []

    if stats['avg_words_per_chunk'] < 50:
        quality_issues.append("⚠️  Chunks too small (avg < 50 words)")
    elif stats['avg_words_per_chunk'] > 600:
        quality_issues.append("⚠️  Chunks too large (avg > 600 words)")
    else:
        print("✅ Chunk sizes are optimal (50-600 words)")

    if not analysis['content_quality']['has_physio_content']:
        quality_issues.append("❌ Missing physio content")

    if not analysis['content_quality']['no_right_txt_artifact']:
        quality_issues.append("❌ Found 'right txt' artifacts")

    if not analysis['content_quality']['no_fragmented_stats']:
        quality_issues.append("⚠️  Stats might be fragmented")

    if analysis['hierarchical_titles']['count'] == 0:
        quality_issues.append("⚠️  No hierarchical titles (expected some)")

    if quality_issues:
        print("\n⚠️  ISSUES FOUND:")
        for issue in quality_issues:
            print(f"   {issue}")
    else:
        print("✅ ALL QUALITY CHECKS PASSED!")

    print("="*80 + "\n")


def main():
    """Run the extraction and chunking test"""
    print("\n" + "="*80)
    print("🧪 MELBOURNE ATHLETIC - EXTRACTION & CHUNKING TEST")
    print("="*80)
    print(f"🌐 Test URL: {TEST_URL}")
    print(f"📏 Max Tokens: {MAX_TOKENS}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    try:
        # Step 1: Extract documents
        logger.info("🔍 Step 1: Extracting documents...")
        documents = extract_documents(
            sources=[TEST_URL],
            crawl_internal=True  # Test the full crawling
        )
        logger.info(f"✅ Extracted {len(documents)} documents")

        if not documents:
            logger.error("❌ No documents extracted!")
            sys.exit(1)

        # Step 2: Chunk documents
        logger.info(f"\n✂️  Step 2: Chunking documents (max_tokens={MAX_TOKENS})...")
        chunks = chunk_documents(documents, max_tokens=MAX_TOKENS)
        logger.info(f"✅ Created {len(chunks)} chunks")

        if not chunks:
            logger.error("❌ No chunks created!")
            sys.exit(1)

        # Step 3: Analyze chunks
        logger.info("\n🔍 Step 3: Analyzing chunk quality...")
        analysis = analyze_chunks(chunks)
        print_report(analysis)

        print("\n🎉 TEST COMPLETED!")
        print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
