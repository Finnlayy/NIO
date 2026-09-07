import logging
import json
import hashlib
from pathlib import Path

logger = logging.getLogger(__name__)

class Archive:
    """Archive / ledger system for durable job storage with SHA-256 digests."""

    def __init__(self, archive_dir: str = "Architect/runtime/archive"):
        self.archive_dir = Path(archive_dir)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def save(self, job_id: str, job_data: dict, history_lines: list = None):
        """Save job data to archive with digest."""
        archive_path = self.archive_dir / f"{job_id}.json"
        # Compact serialization (machine format) for performance; CLI pretty-prints on lookup
        content_str = json.dumps(job_data, separators=(",", ":"))
        digest = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
        archive_data = {
            "job_id": job_id,
            "digest_sha256": digest,
            "archive_path": str(archive_path),
            "data": job_data,
        }
        with open(archive_path, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, indent=2, ensure_ascii=False)
        # Save history (.history.jsonl) if provided
        if history_lines:
            history_path = self.archive_dir / f"{job_id}.history.jsonl"
            with open(history_path, "a", encoding="utf-8") as f:
                for line in history_lines:
                    f.write(json.dumps(line, separators=(",", ":")) + "\n")
        logger.info("Archive saved: %s (digest=%s)", archive_path, digest)
        return digest

    def lookup(self, job_id: str) -> dict:
        archive_path = self.archive_dir / f"{job_id}.json"
        if not archive_path.exists():
            logger.warning("Archive lookup failed: %s not found", archive_path)
            return {}
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Verify digest
            expected_digest = data.get("digest_sha256", "")
            content_str = json.dumps(data.get("data", {}), separators=(",", ":"))
            actual_digest = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
            if expected_digest and actual_digest != expected_digest:
                logger.warning("Archive digest mismatch for %s: expected %s, got %s", job_id, expected_digest, actual_digest)
            return data.get("data", {})
        except Exception as exc:
            logger.error("Archive lookup error for %s: %s", job_id, exc)
            return {}

    def stats(self) -> dict:
        files = list(self.archive_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        job_ids = [f.stem for f in files if not f.name.endswith(".history.jsonl")]
        return {
            "archive_file_count": len(files),
            "total_bytes": total_size,
            "oldest_job": min(job_ids) if job_ids else None,
            "newest_job": max(job_ids) if job_ids else None,
        }

    def verify(self) -> list:
        """Verify all archive file digests; return list of failures."""
        failures = []
        for file_path in self.archive_dir.glob("*.json"):
            if file_path.name.endswith(".history.jsonl"):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                expected_digest = data.get("digest_sha256", "")
                content_str = json.dumps(data.get("data", {}), separators=(",", ":"))
                actual_digest = hashlib.sha256(content_str.encode("utf-8")).hexdigest()
                if expected_digest and actual_digest != expected_digest:
                    failures.append(str(file_path))
            except Exception as exc:
                failures.append(str(file_path) + f" (exception: {exc})")
        return failures

    def compact(self) -> bool:
        """Compact archive by removing redundant history files and merging if needed."""
        # Phase 3: basic compaction — for full implementation, merge .history.jsonl into archive
        # and remove history file. For now, we ensure archive files exist and clean empty ones.
        cleaned = 0
        for file_path in self.archive_dir.glob("*.json"):
            try:
                if file_path.stat().st_size == 0:
                    file_path.unlink()
                    cleaned += 1
            except Exception:
                pass
        logger.info("Archive compacted: removed %d empty files.", cleaned)
        return True
