"""
Test extraction and chunking across 10 diverse websites
Mix of good/bad HTML structure, different industries, modern/legacy sites
"""
import sys
import logging
from datetime import datetime

sys.path.insert(0, '/Users/juanbernal/Coding/knowledge-base-mcp')

from processing.extraction import extract_documents
from processing.chunking import chunk_documents

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings/errors to keep output clean
    format='%(levelname)s - %(message)s'
)

# Test websites - diverse mix
TEST_WEBSITES = [
    {
        "name": "Python.org",
        "url": "https://www.python.org/",
        "category": "Documentation",
        "expected_quality": "Good - Modern semantic HTML"
    },
    {
        "name": "Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "category": "Encyclopedia",
        "expected_quality": "Good - Clean semantic structure"
    },
    {
        "name": "Nike",
        "url": "https://www.nike.com/",
        "category": "E-commerce",
        "expected_quality": "Medium - Heavy JS, complex structure"
    },
    {
        "name": "BBC News",
        "url": "https://www.bbc.com/news",
        "category": "News",
        "expected_quality": "Good - News article structure"
    },
    {
        "name": "GitHub",
        "url": "https://github.com/",
        "category": "Tech Platform",
        "expected_quality": "Good - Modern web app"
    },
    {
        "name": "Stack Overflow",
        "url": "https://stackoverflow.com/",
        "category": "Q&A Platform",
        "expected_quality": "Good - Clean content structure"
    },
    {
        "name": "Medium",
        "url": "https://medium.com/",
        "category": "Blog Platform",
        "expected_quality": "Good - Article-focused"
    },
    {
        "name": "Craigslist",
        "url": "https://sfbay.craigslist.org/",
        "category": "Classifieds",
        "expected_quality": "Bad - Legacy HTML, minimal structure"
    },
    {
        "name": "HackerNews",
        "url": "https://news.ycombinator.com/",
        "category": "Tech News",
        "expected_quality": "Bad - Very minimal HTML tables"
    },
    {
        "name": "Melbourne Athletic (Test)",
        "url": "https://www.melbourneathleticdevelopment.com.au/",
        "category": "Small Business",
        "expected_quality": "Bad - Content in header tags"
    }
]


def analyze_extraction(website_info, docs, chunks):
    """Analyze extraction quality"""
    if not docs:
        return {
            "status": "❌ FAILED",
            "error": "No documents extracted",
            "chunks": 0,
            "avg_words": 0
        }

    if not chunks:
        return {
            "status": "⚠️  POOR",
            "error": "No chunks created",
            "chunks": 0,
            "avg_words": 0,
            "docs_extracted": len(docs)
        }

    # Calculate statistics
    word_counts = [len(c.text.split()) for c in chunks]
    avg_words = sum(word_counts) / len(word_counts)

    # Check for hierarchical titles
    hierarchical_count = sum(1 for c in chunks if c.meta and c.meta.headings and len(c.meta.headings) > 1)

    # Quality assessment
    if avg_words < 30:
        status = "⚠️  POOR"
    elif avg_words < 50:
        status = "🟡 FAIR"
    elif avg_words < 100:
        status = "✅ GOOD"
    else:
        status = "✅ EXCELLENT"

    return {
        "status": status,
        "docs_extracted": len(docs),
        "chunks": len(chunks),
        "avg_words": round(avg_words, 1),
        "min_words": min(word_counts),
        "max_words": max(word_counts),
        "hierarchical_pct": round(100 * hierarchical_count / len(chunks), 1) if chunks else 0,
        "tiny_chunks": sum(1 for w in word_counts if w < 20),
        "quality_chunks": sum(1 for w in word_counts if 30 <= w <= 200)
    }


def main():
    print("\n" + "="*80)
    print("🧪 COMPREHENSIVE WEBSITE EXTRACTION TEST")
    print("="*80)
    print(f"Testing {len(TEST_WEBSITES)} diverse websites")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")

    results = []

    for i, website in enumerate(TEST_WEBSITES, 1):
        print(f"\n[{i}/{len(TEST_WEBSITES)}] {website['name']} ({website['category']})")
        print(f"URL: {website['url']}")
        print(f"Expected: {website['expected_quality']}")
        print("-" * 80)

        try:
            # Extract (no crawling for speed)
            print("  Extracting...", end=" ", flush=True)
            docs = extract_documents([website['url']], crawl_internal=False)
            print(f"✓ {len(docs)} docs")

            # Chunk
            print("  Chunking...", end=" ", flush=True)
            chunks = chunk_documents(docs, max_tokens=512) if docs else []
            print(f"✓ {len(chunks)} chunks")

            # Analyze
            analysis = analyze_extraction(website, docs, chunks)
            analysis['name'] = website['name']
            analysis['category'] = website['category']
            analysis['expected'] = website['expected_quality']
            results.append(analysis)

            print(f"  {analysis['status']} - {analysis['avg_words']} avg words/chunk, "
                  f"{analysis.get('hierarchical_pct', 0)}% hierarchical")

        except Exception as e:
            print(f"  ❌ FAILED: {str(e)[:100]}")
            results.append({
                "name": website['name'],
                "category": website['category'],
                "expected": website['expected_quality'],
                "status": "❌ ERROR",
                "error": str(e)[:100],
                "chunks": 0,
                "avg_words": 0
            })

    # Summary Report
    print("\n\n" + "="*80)
    print("📊 SUMMARY REPORT")
    print("="*80)

    # Results table
    print(f"\n{'Website':<25} {'Category':<15} {'Status':<12} {'Chunks':<8} {'Avg Words':<10} {'Quality'}")
    print("-" * 105)

    for r in results:
        quality_score = "N/A"
        if r.get('quality_chunks'):
            quality_score = f"{r.get('quality_chunks', 0)}/{r['chunks']}"

        print(f"{r['name']:<25} {r['category']:<15} {r['status']:<12} "
              f"{r['chunks']:<8} {r.get('avg_words', 0):<10.1f} {quality_score}")

    # Statistics
    successful = [r for r in results if r['chunks'] > 0]
    failed = [r for r in results if r['chunks'] == 0]

    print("\n" + "="*80)
    print(f"✅ Successful: {len(successful)}/{len(TEST_WEBSITES)}")
    print(f"❌ Failed: {len(failed)}/{len(TEST_WEBSITES)}")

    if successful:
        avg_chunks = sum(r['chunks'] for r in successful) / len(successful)
        avg_words = sum(r.get('avg_words', 0) for r in successful) / len(successful)
        avg_hierarchical = sum(r.get('hierarchical_pct', 0) for r in successful) / len(successful)

        print(f"\n📈 Average Statistics (successful sites):")
        print(f"  Chunks per site: {avg_chunks:.1f}")
        print(f"  Words per chunk: {avg_words:.1f}")
        print(f"  Hierarchical titles: {avg_hierarchical:.1f}%")

    # Best and worst performers
    if successful:
        best = max(successful, key=lambda x: x.get('avg_words', 0))
        print(f"\n🏆 Best: {best['name']} - {best['avg_words']:.1f} avg words/chunk")

        if len(successful) > 1:
            worst = min(successful, key=lambda x: x.get('avg_words', 0))
            print(f"⚠️  Worst (but working): {worst['name']} - {worst['avg_words']:.1f} avg words/chunk")

    if failed:
        print(f"\n❌ Failed sites:")
        for f in failed:
            print(f"  • {f['name']}: {f.get('error', 'Unknown error')}")

    print("\n" + "="*80)
    print(f"⏰ Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
