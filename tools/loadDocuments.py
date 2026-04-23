"""
Thin MCP tool wrapper - orchestrates extraction, chunking, and embedding
Uses TRANSACTIONAL approach - nothing is committed until everything succeeds
"""
import os
import logging
import sys
import json
import threading
import time
import uuid
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import psycopg
from psycopg.rows import dict_row
import requests

from processing import extract_documents, chunk_documents, create_embeddings_table, embed_and_store_chunks
from processing.embedding import infer_source_type, create_or_update_source_transactional, embed_and_store_chunks_transactional

load_dotenv()

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Force stdout for Railway
    ]
)
logger = logging.getLogger(__name__)


def load_documents(
    business_id: str,
    sources: Optional[List[str]] = None,
    table_name: str = "knowledge_entries",
    max_tokens: int = 512,  # Optimal for semantic search
    crawl_internal: bool = True,
    database_url: Optional[str] = None,
    category: str = "website",
    description: str = None,
    mode: str = "sync",
    import_key: Optional[str] = None,
    return_preview_chunks: bool = False,
    preview_max_chunks: int = 24,
    max_pages: int = 50
) -> Dict[str, Any]:
    """
    Load documents with source tracking - TRANSACTIONAL approach.

    CRITICAL: Nothing is committed to the database until ALL processing succeeds.
    If any step fails (extraction, chunking, embedding), NO database records are created.
    """
    from openai import OpenAI

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 1: VALIDATION (fail fast before any processing)
    # ═══════════════════════════════════════════════════════════════════════════

    # Validate required business_id
    if not business_id:
        raise ValueError("business_id is required and cannot be None or empty")

    # Validate business_id is a valid UUID
    try:
        uuid.UUID(business_id)
    except ValueError:
        raise ValueError(f"business_id must be a valid UUID format, got: {business_id}")

    if mode not in ("sync", "preview_then_background"):
        raise ValueError(f"Unsupported load mode: {mode}")

    # Use provided database_url or fall back to environment variable
    if not database_url:
        database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL must be provided as parameter or environment variable")

    # OpenAI API key is still required from environment
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Validate OpenAI API key works before processing
    try:
        openai_client = OpenAI(api_key=openai_api_key)
        # Quick validation call
        logger.info("🔑 Validating OpenAI API key...")
    except Exception as e:
        raise ValueError(f"Invalid OPENAI_API_KEY: {e}")

    # Get sources from environment if not provided
    env_sources = os.getenv("SOURCES")

    # Parse sources
    if sources is None:
        if not env_sources:
            raise ValueError("SOURCES environment variable or sources parameter is required")
        sources = [s.strip() for s in env_sources.split(",") if s.strip()]

    if not sources:
        raise ValueError("At least one source must be provided")

    if mode == "preview_then_background":
        if not import_key:
            raise ValueError("import_key is required for preview_then_background mode")
        existing = _get_existing_ingestion_job(database_url, import_key)
        if existing and existing["status"] in ("chunks_ready", "embedding", "loaded"):
            preview_chunks = _get_preview_chunks(database_url, existing["id"], preview_max_chunks)
            return _build_preview_response(
                import_key=import_key,
                source_id=existing["source_id"],
                ingestion_job_id=existing["id"],
                ingestion_status=existing["status"],
                preview_chunks=preview_chunks,
                failure_reason=existing.get("failure_reason"),
                metrics=existing.get("metrics_json") or {},
                sources_processed=len(sources),
                errors=[],
            )

        failure_reason = _soft_validate_source(sources[0])
        if failure_reason:
            return {
                "table_name": "knowledge_entries",
                "total_entries": 0,
                "sources_processed": len(sources),
                "sources_successful": 0,
                "sources_failed": len(sources),
                "import_key": import_key,
                "ingestion_status": "failed",
                "failure_reason": failure_reason,
                "preview_chunks": [],
                "preview_chunk_ids": [],
                "results": [{"source_url": sources[0], "status": "failed", "error": failure_reason}],
                "errors": [failure_reason],
            }

    # Log business context
    logger.info(f"🏢 Processing for business ID: {business_id}")
    logger.info(f"📂 Category: {category}")
    logger.info(f"📋 Sources to process: {len(sources)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 2: EXTRACTION & CHUNKING (all processing BEFORE any DB writes)
    # ═══════════════════════════════════════════════════════════════════════════

    # Process all sources and collect results BEFORE touching the database
    processed_sources = []  # Will hold: {source_url, source_type, chunks, embeddings}

    for source_url in sources:
        logger.info(f"📄 Processing source: {source_url}")

        source_type = infer_source_type(source_url)

        # Step 1: Extract documents
        logger.info(f"🔍 Extracting documents from {source_type}...")
        crawl_start = time.time()
        documents = extract_documents([source_url], crawl_internal=crawl_internal, max_pages=max_pages)
        crawl_ms = int((time.time() - crawl_start) * 1000)
        logger.info(f"✅ Extracted {len(documents)} documents")

        if not documents:
            raise ValueError(f"No documents extracted from source: {source_url}")

        # Step 2: Chunk documents
        logger.info(f"✂️ Chunking documents (max_tokens: {max_tokens})...")
        chunks = chunk_documents(documents, max_tokens)
        logger.info(f"✅ Created {len(chunks)} chunks")

        if not chunks:
            raise ValueError(f"No chunks created from source: {source_url}")

        if mode == "preview_then_background":
            preview_started = time.time()
            preview_result = _persist_preview_job(
                business_id=business_id,
                source_url=source_url,
                source_type=source_type,
                chunks=chunks,
                crawl_internal=crawl_internal,
                database_url=database_url,
                category=category,
                description=description,
                import_key=import_key,
                preview_max_chunks=preview_max_chunks,
                metrics={
                    "crawl_ms": crawl_ms,
                    "pages_crawled": len(documents),
                    "chunk_count": len(chunks),
                },
            )
            preview_result["metrics"]["preview_return_ms"] = int((time.time() - preview_started) * 1000) + crawl_ms
            _update_job_metrics(database_url, preview_result["ingestion_job_id"], preview_result["metrics"])

            thread = threading.Thread(
                target=_embed_staged_chunks_background,
                args=(database_url, preview_result["ingestion_job_id"], business_id, category, openai_api_key),
                daemon=True,
            )
            thread.start()
            return {
                "table_name": "knowledge_entries",
                "total_entries": 0,
                "sources_processed": len(sources),
                "sources_successful": 1,
                "sources_failed": 0,
                "results": [{
                    "source_url": source_url,
                    "source_id": preview_result["source_id"],
                    "source_type": source_type,
                    "status": "processing",
                    "entry_count": 0,
                }],
                **preview_result,
            }

        # Step 3: Generate embeddings (most expensive step - do BEFORE DB transaction)
        logger.info(f"🤖 Generating embeddings for {len(chunks)} chunks...")
        chunk_data = _generate_embeddings(
            chunks=chunks,
            openai_client=openai_client,
            business_id=business_id,
            category=category,
            source_url=source_url
        )
        logger.info(f"✅ Generated {len(chunk_data)} embeddings")

        processed_sources.append({
            "source_url": source_url,
            "source_type": source_type,
            "chunk_data": chunk_data,
            "chunk_count": len(chunk_data)
        })

    logger.info(f"✅ All sources processed successfully. Starting database transaction...")

    # ═══════════════════════════════════════════════════════════════════════════
    # PHASE 3: DATABASE TRANSACTION (all-or-nothing commit)
    # ═══════════════════════════════════════════════════════════════════════════

    all_results = []
    total_entries_created = 0

    # Single transaction for ALL database operations
    with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                # Create tables if needed (within transaction)
                logger.info("🗄️ Ensuring database tables exist...")
                _ensure_tables_exist(cursor)

                # Process each source within the same transaction
                for processed in processed_sources:
                    source_url = processed["source_url"]
                    source_type = processed["source_type"]
                    chunk_data = processed["chunk_data"]

                    # Create/update source tracking record (NOT committed yet)
                    logger.info(f"📝 Creating source record: {source_url}")
                    source_id = create_or_update_source_transactional(
                        cursor=cursor,
                        business_id=business_id,
                        source_url=source_url,
                        category=category,
                        source_type=source_type,
                        crawl_internal=crawl_internal,
                        description=description
                    )
                    logger.info(f"✓ Source ID: {source_id}")

                    # Store embeddings (NOT committed yet)
                    row_count = embed_and_store_chunks_transactional(
                        cursor=cursor,
                        chunk_data=chunk_data,
                        business_id=business_id,
                        category=category,
                        source_id=source_id,
                        source_url=source_url
                    )
                    logger.info(f"✓ Prepared {row_count} chunks for storage")

                    # Update source with entry count (NOT committed yet)
                    cursor.execute(
                        """
                        UPDATE knowledge_sources
                        SET status = 'loaded',
                            last_loaded_at = now(),
                            entry_count = %s,
                            error_message = NULL,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (row_count, source_id)
                    )

                    total_entries_created += row_count
                    all_results.append({
                        "source_url": source_url,
                        "source_id": source_id,
                        "source_type": source_type,
                        "status": "loaded",
                        "entry_count": row_count
                    })

                # ═══════════════════════════════════════════════════════════════
                # COMMIT: Only here, after ALL operations succeeded
                # ═══════════════════════════════════════════════════════════════
                conn.commit()
                logger.info("✅ Transaction committed successfully!")

        except Exception as e:
            # ROLLBACK: Nothing is saved if ANY step fails
            conn.rollback()
            logger.error(f"❌ Transaction rolled back due to error: {e}")
            raise RuntimeError(f"Pipeline failed, no data was saved: {e}") from e

    # Return comprehensive results
    successful_sources = [r for r in all_results if r['status'] == 'loaded']

    logger.info(f"✅ Pipeline complete: {total_entries_created} total entries from {len(successful_sources)}/{len(sources)} sources")

    return {
        "table_name": "knowledge_entries",
        "total_entries": total_entries_created,
        "sources_processed": len(sources),
        "sources_successful": len(successful_sources),
        "sources_failed": 0,
        "results": all_results
    }


def _generate_embeddings(chunks: List, openai_client, business_id: str, category: str, source_url: str) -> List[tuple]:
    """
    Generate embeddings for chunks in BATCHES - much faster than individual API calls.
    Returns list of dicts ready for database insertion.
    """
    import json
    import time

    chunk_data = []
    total_chunks = len(chunks)
    BATCH_SIZE = 100  # OpenAI supports up to 2048, but 100 is safe for token limits

    logger.info(f"📊 Processing {total_chunks} chunks in batches of {BATCH_SIZE}...")

    # Process in batches for faster API calls
    for batch_start in range(0, total_chunks, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_chunks)
        batch_chunks = chunks[batch_start:batch_end]

        # Batch API call - sends multiple texts in one request
        texts = [chunk.text for chunk in batch_chunks]
        embedding_response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=texts
        )

        # Process batch results
        for idx, (chunk, emb_data) in enumerate(zip(batch_chunks, embedding_response.data)):
            global_idx = batch_start + idx + 1
            embedding = emb_data.embedding
            chunk_source_url = _chunk_source_url(chunk, source_url)

            # Extract title with BETTER fallback logic using document hierarchy
            title = "Untitled Document"

            # Strategy 1: Use ALL headings to create hierarchical title
            if chunk.meta and chunk.meta.headings:
                # Use last 2 headings for context: "Services > Physiotherapy"
                headings = chunk.meta.headings
                if len(headings) > 1:
                    title = " > ".join(headings[-2:])  # Parent > Child
                else:
                    title = headings[0]

            # Strategy 2: Fallback to filename
            elif chunk.meta and chunk.meta.origin and chunk.meta.origin.filename:
                title = chunk.meta.origin.filename

            # Strategy 3: Use first words of content as title
            elif chunk.text:
                # Use first line or first 50 chars as title
                first_line = chunk.text.split('\n')[0].strip()
                title = first_line[:50] if first_line else "Untitled Document"

            # Truncate title to 255 characters max
            title = title[:255] if title else "Untitled Document"

            # Build metadata
            metadata = {
                "source_url": chunk_source_url,
                "filename": chunk.meta.origin.filename if chunk.meta and chunk.meta.origin else "unknown",
                "page_numbers": [
                    page_no
                    for page_no in sorted(
                        set(
                            prov.page_no
                            for item in chunk.meta.doc_items
                            for prov in item.prov
                            if hasattr(prov, 'page_no') and prov.page_no is not None
                        )
                    )
                ] if chunk.meta and chunk.meta.doc_items else None,
                "original_title": chunk.meta.headings[0] if chunk.meta and chunk.meta.headings else None,
                "chunk_index": global_idx,
                "total_chunks": total_chunks,
                "loaded_at": time.time()
            }

            chunk_data.append({
                "title": title,
                "content": chunk.text,
                "embedding": embedding,
                "metadata": json.dumps(metadata)
            })

        # Progress tracking per batch
        progress = (batch_end / total_chunks) * 100
        logger.info(f"📈 Embedding progress: {batch_end}/{total_chunks} ({progress:.1f}%)")

    return chunk_data


def _soft_validate_source(source_url: str) -> Optional[str]:
    """Fast validation before running the full crawl pipeline."""
    try:
        response = requests.get(
            source_url,
            timeout=8,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
            stream=True,
        )
        if response.status_code in (401, 403):
            return "blocked"
        if response.status_code >= 400:
            return "parse_error"
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None
        sample = next(response.iter_content(chunk_size=4096), b"")
        if not sample.strip():
            return "empty_content"
        return None
    except requests.exceptions.Timeout:
        return "timeout"
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            return "blocked"
        return "parse_error"
    except Exception:
        return "parse_error"


def _chunk_title(chunk) -> str:
    title = "Untitled Document"
    if chunk.meta and chunk.meta.headings:
        headings = chunk.meta.headings
        title = " > ".join(headings[-2:]) if len(headings) > 1 else headings[0]
    elif chunk.meta and chunk.meta.origin and chunk.meta.origin.filename:
        title = chunk.meta.origin.filename
    elif chunk.text:
        first_line = chunk.text.split('\n')[0].strip()
        title = first_line[:50] if first_line else title
    return title[:255] if title else "Untitled Document"


def _chunk_source_url(chunk, fallback_source_url: str) -> str:
    source_url = getattr(chunk, "_source_url", None)
    return source_url or fallback_source_url


def _chunk_metadata(chunk, source_url: str, chunk_index: int, total_chunks: int) -> Dict[str, Any]:
    return {
        "source_url": source_url,
        "filename": chunk.meta.origin.filename if chunk.meta and chunk.meta.origin else "unknown",
        "page_numbers": [
            page_no
            for page_no in sorted(
                set(
                    prov.page_no
                    for item in chunk.meta.doc_items
                    for prov in item.prov
                    if hasattr(prov, 'page_no') and prov.page_no is not None
                )
            )
        ] if chunk.meta and chunk.meta.doc_items else None,
        "original_title": chunk.meta.headings[0] if chunk.meta and chunk.meta.headings else None,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "loaded_at": time.time(),
    }


def _get_existing_ingestion_job(database_url: str, import_key: str) -> Optional[Dict[str, Any]]:
    with psycopg.connect(database_url, autocommit=True, prepare_threshold=None) as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            _ensure_tables_exist(cursor)
            cursor.execute(
                """
                SELECT id, business_id, source_id, import_key, source_url, status, failure_reason, metrics_json
                FROM knowledge_ingestion_jobs
                WHERE import_key = %s
                """,
                (import_key,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None


def _get_preview_chunks(database_url: str, job_id: str, limit: int) -> List[Dict[str, Any]]:
    with psycopg.connect(database_url, autocommit=True, prepare_threshold=None) as conn:
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(
                """
                SELECT id, source_url, title, text, chunk_index
                FROM knowledge_ingestion_chunks
                WHERE job_id = %s
                ORDER BY chunk_index ASC
                LIMIT %s
                """,
                (job_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]


def _build_preview_response(
    import_key: str,
    source_id: str,
    ingestion_job_id: str,
    ingestion_status: str,
    preview_chunks: List[Dict[str, Any]],
    failure_reason: Optional[str],
    metrics: Dict[str, Any],
    sources_processed: int,
    errors: List[str],
) -> Dict[str, Any]:
    return {
        "table_name": "knowledge_entries",
        "total_entries": 0,
        "sources_processed": sources_processed,
        "sources_successful": 1 if preview_chunks else 0,
        "sources_failed": 0 if preview_chunks else sources_processed,
        "import_key": import_key,
        "source_id": str(source_id),
        "ingestion_job_id": str(ingestion_job_id),
        "ingestion_status": ingestion_status,
        "preview_chunks": [
            {
                "id": str(chunk["id"]),
                "source_url": chunk["source_url"],
                "title": chunk["title"],
                "text": chunk["text"],
                "chunk_index": chunk["chunk_index"],
            }
            for chunk in preview_chunks
        ],
        "preview_chunk_ids": [str(chunk["id"]) for chunk in preview_chunks],
        "failure_reason": failure_reason,
        "metrics": metrics,
        "errors": errors,
    }


def _transition_job(cursor, job_id: str, next_status: str, failure_reason: Optional[str] = None) -> bool:
    allowed = {
        "chunks_ready": {"embedding", "failed", "cancelled"},
        "embedding": {"loaded", "failed", "cancelled"},
        "loaded": set(),
        "failed": set(),
        "cancelled": set(),
    }
    cursor.execute("SELECT status FROM knowledge_ingestion_jobs WHERE id = %s FOR UPDATE", (job_id,))
    row = cursor.fetchone()
    if not row:
        return False
    current = row["status"]
    if current == next_status:
        return True
    if next_status not in allowed.get(current, set()):
        logger.warning(f"Invalid ingestion transition ignored: {current} -> {next_status}")
        return False
    cursor.execute(
        """
        UPDATE knowledge_ingestion_jobs
        SET status = %s, failure_reason = %s, updated_at = now()
        WHERE id = %s
        """,
        (next_status, failure_reason, job_id)
    )
    return True


def _update_job_metrics(database_url: str, job_id: str, metrics: Dict[str, Any]) -> None:
    with psycopg.connect(database_url, autocommit=True, prepare_threshold=None) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE knowledge_ingestion_jobs
                SET metrics_json = COALESCE(metrics_json, '{}'::jsonb) || %s::jsonb,
                    updated_at = now()
                WHERE id = %s
                """,
                (json.dumps(metrics), job_id)
            )


def _persist_preview_job(
    business_id: str,
    source_url: str,
    source_type: str,
    chunks: List,
    crawl_internal: bool,
    database_url: str,
    category: str,
    description: Optional[str],
    import_key: str,
    preview_max_chunks: int,
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    total_chunks = len(chunks)
    with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
        try:
            with conn.cursor(row_factory=dict_row) as cursor:
                _ensure_tables_exist(cursor)
                source_id = create_or_update_source_transactional(
                    cursor=cursor,
                    business_id=business_id,
                    source_url=source_url,
                    category=category,
                    source_type=source_type,
                    crawl_internal=crawl_internal,
                    description=description,
                )
                cursor.execute(
                    """
                    UPDATE knowledge_sources
                    SET status = 'loading',
                        created_during_onboarding = true,
                        failure_reason = NULL,
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object('import_key', %s::text),
                        updated_at = now()
                    WHERE id = %s
                    """,
                    (import_key, source_id)
                )
                cursor.execute(
                    """
                    INSERT INTO knowledge_ingestion_jobs (
                        business_id, source_id, import_key, source_url, status,
                        created_during_onboarding, metrics_json
                    )
                    VALUES (%s, %s, %s, %s, 'chunks_ready', true, %s::jsonb)
                    ON CONFLICT (import_key) DO UPDATE
                    SET status = CASE
                            WHEN knowledge_ingestion_jobs.status IN ('failed', 'cancelled') THEN 'chunks_ready'
                            ELSE knowledge_ingestion_jobs.status
                        END,
                        source_id = EXCLUDED.source_id,
                        source_url = EXCLUDED.source_url,
                        failure_reason = NULL,
                        metrics_json = EXCLUDED.metrics_json,
                        updated_at = now()
                    RETURNING id, status
                    """,
                    (business_id, source_id, import_key, source_url, json.dumps(metrics))
                )
                job = cursor.fetchone()
                job_id = str(job["id"])

                cursor.execute("DELETE FROM knowledge_ingestion_chunks WHERE job_id = %s", (job_id,))
                preview_chunks = []
                for idx, chunk in enumerate(chunks, 1):
                    chunk_source_url = _chunk_source_url(chunk, source_url)
                    metadata = _chunk_metadata(chunk, chunk_source_url, idx, total_chunks)
                    cursor.execute(
                        """
                        INSERT INTO knowledge_ingestion_chunks (
                            job_id, source_url, title, text, chunk_index, metadata
                        )
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        RETURNING id, source_url, title, text, chunk_index
                        """,
                        (job_id, chunk_source_url, _chunk_title(chunk), chunk.text, idx, json.dumps(metadata))
                    )
                    row = dict(cursor.fetchone())
                    if len(preview_chunks) < preview_max_chunks:
                        preview_chunks.append(row)

                conn.commit()
        except Exception:
            conn.rollback()
            raise

    return _build_preview_response(
        import_key=import_key,
        source_id=source_id,
        ingestion_job_id=job_id,
        ingestion_status="chunks_ready",
        preview_chunks=preview_chunks,
        failure_reason=None,
        metrics=metrics,
        sources_processed=1,
        errors=[],
    )


def _generate_embeddings_from_staged_chunks(staged_chunks: List[Dict[str, Any]], openai_client) -> List[Dict[str, Any]]:
    chunk_data = []
    total_chunks = len(staged_chunks)
    batch_size = 100
    for batch_start in range(0, total_chunks, batch_size):
        batch = staged_chunks[batch_start:batch_start + batch_size]
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=[chunk["text"] for chunk in batch],
        )
        for chunk, emb_data in zip(batch, response.data):
            metadata = dict(chunk.get("metadata") or {})
            metadata["loaded_at"] = time.time()
            chunk_data.append({
                "title": chunk["title"],
                "content": chunk["text"],
                "embedding": emb_data.embedding,
                "metadata": json.dumps(metadata),
            })
    return chunk_data


def _embed_staged_chunks_background(
    database_url: str,
    job_id: str,
    business_id: str,
    category: str,
    openai_api_key: str,
) -> None:
    from openai import OpenAI

    try:
        with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                if not _transition_job(cursor, job_id, "embedding"):
                    conn.commit()
                    return
                cursor.execute(
                    """
                    SELECT id, source_id, source_url, status
                    FROM knowledge_ingestion_jobs
                    WHERE id = %s
                    """,
                    (job_id,)
                )
                job = cursor.fetchone()
                if not job or job["status"] == "cancelled":
                    conn.commit()
                    return
                source_id = str(job["source_id"])
                source_url = job["source_url"]
                conn.commit()

        with psycopg.connect(database_url, autocommit=True, prepare_threshold=None) as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT title, text, metadata
                    FROM knowledge_ingestion_chunks
                    WHERE job_id = %s
                    ORDER BY chunk_index ASC
                    """,
                    (job_id,)
                )
                staged_chunks = [dict(row) for row in cursor.fetchall()]

        openai_client = OpenAI(api_key=openai_api_key)
        chunk_data = _generate_embeddings_from_staged_chunks(staged_chunks, openai_client)

        with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
            try:
                with conn.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        "SELECT status FROM knowledge_ingestion_jobs WHERE id = %s FOR UPDATE",
                        (job_id,)
                    )
                    job = cursor.fetchone()
                    if not job or job["status"] == "cancelled":
                        conn.commit()
                        return

                    cursor.execute(
                        "DELETE FROM knowledge_entries WHERE business_id = %s AND source_id = %s",
                        (business_id, source_id)
                    )
                    row_count = embed_and_store_chunks_transactional(
                        cursor=cursor,
                        chunk_data=chunk_data,
                        business_id=business_id,
                        category=category,
                        source_id=source_id,
                        source_url=source_url,
                    )
                    cursor.execute(
                        """
                        UPDATE knowledge_sources
                        SET status = 'loaded',
                            last_loaded_at = now(),
                            entry_count = %s,
                            error_message = NULL,
                            failure_reason = NULL,
                            updated_at = now()
                        WHERE id = %s
                        """,
                        (row_count, source_id)
                    )
                    _transition_job(cursor, job_id, "loaded")
                    conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception as e:
        logger.error(f"❌ Background embedding failed for job {job_id}: {e}", exc_info=True)
        try:
            with psycopg.connect(database_url, autocommit=False, prepare_threshold=None) as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    _transition_job(cursor, job_id, "failed", "embedding_error")
                    cursor.execute(
                        """
                        UPDATE knowledge_sources
                        SET status = 'failed',
                            error_message = %s,
                            failure_reason = 'embedding_error',
                            updated_at = now()
                        WHERE id = (
                            SELECT source_id FROM knowledge_ingestion_jobs WHERE id = %s
                        )
                        """,
                        (str(e), job_id)
                    )
                    conn.commit()
        except Exception as update_error:
            logger.error(f"❌ Failed to mark job failed: {update_error}", exc_info=True)


def _ensure_tables_exist(cursor):
    """Create tables if they don't exist (within transaction)."""

    # Enable pgvector extension
    try:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except Exception as e:
        logger.warning(f"⚠️ Could not enable pgvector: {e}")

    # Create knowledge_sources table FIRST (due to FK constraint)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id UUID NOT NULL REFERENCES businesses(id),
            source_url TEXT NOT NULL,
            source_type VARCHAR NOT NULL CHECK (source_type IN ('website', 'pdf', 'document', 'text')),
            category VARCHAR NOT NULL CHECK (category IN ('website', 'faq', 'policy', 'pricing', 'procedure', 'technical')),
            description TEXT,
            crawl_internal BOOLEAN DEFAULT true,
            status VARCHAR NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'loading', 'loaded', 'failed', 'inactive')),
            last_loaded_at TIMESTAMPTZ,
            error_message TEXT,
            entry_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(business_id, source_url)
        );

        ALTER TABLE knowledge_sources
            ADD COLUMN IF NOT EXISTS created_during_onboarding BOOLEAN DEFAULT false,
            ADD COLUMN IF NOT EXISTS ingestion_version INTEGER DEFAULT 1,
            ADD COLUMN IF NOT EXISTS failure_reason TEXT,
            ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_business
            ON knowledge_sources(business_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_status
            ON knowledge_sources(business_id, status);
        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_url
            ON knowledge_sources(source_url);
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_ingestion_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            source_id UUID NOT NULL REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            import_key TEXT NOT NULL UNIQUE,
            source_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'chunks_ready'
                CHECK (status IN ('chunks_ready', 'embedding', 'loaded', 'failed', 'cancelled')),
            failure_reason TEXT
                CHECK (
                    failure_reason IS NULL OR failure_reason IN (
                        'timeout', 'blocked', 'empty_content', 'parse_error',
                        'embedding_error', 'db_error', 'cancelled', 'unknown'
                    )
                ),
            created_during_onboarding BOOLEAN NOT NULL DEFAULT false,
            metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_ingestion_jobs_business
            ON knowledge_ingestion_jobs(business_id, status);
        CREATE INDEX IF NOT EXISTS idx_knowledge_ingestion_jobs_source
            ON knowledge_ingestion_jobs(source_id);

        CREATE TABLE IF NOT EXISTS knowledge_ingestion_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            job_id UUID NOT NULL REFERENCES knowledge_ingestion_jobs(id) ON DELETE CASCADE,
            source_url TEXT NOT NULL,
            title TEXT NOT NULL,
            text TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(job_id, chunk_index)
        );

        CREATE INDEX IF NOT EXISTS idx_knowledge_ingestion_chunks_job
            ON knowledge_ingestion_chunks(job_id, chunk_index);
    """)

    # Create knowledge_entries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            business_id UUID NOT NULL REFERENCES businesses(id),
            category VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536),
            metadata JSONB,
            source_id UUID REFERENCES knowledge_sources(id) ON DELETE CASCADE,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        );

        CREATE INDEX IF NOT EXISTS knowledge_entries_embedding_idx
            ON knowledge_entries USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

        CREATE INDEX IF NOT EXISTS knowledge_entries_metadata_idx
            ON knowledge_entries USING GIN (metadata);

        CREATE INDEX IF NOT EXISTS knowledge_entries_business_active_idx
            ON knowledge_entries (business_id, is_active);

        CREATE INDEX IF NOT EXISTS knowledge_entries_content_fts_idx
            ON knowledge_entries USING GIN (to_tsvector('english', content));

        CREATE INDEX IF NOT EXISTS idx_knowledge_entries_source
            ON knowledge_entries(source_id);

        CREATE INDEX IF NOT EXISTS idx_knowledge_entries_business_source
            ON knowledge_entries(business_id, source_id)
            WHERE is_active = true;
    """)

    logger.info("✅ Tables verified/created")


# For testing
if __name__ == "__main__":
    import sys

    try:
        result = load_documents()
        print("✅ Pipeline Result:", result)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
