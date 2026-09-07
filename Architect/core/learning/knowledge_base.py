"""Knowledge base (Phase 4 — RLHF Integration).

Versioned store of notes, corrections and research summaries that the learning
engine ingests to upgrade skills. Python counterpart of blueprint
`KnowledgeEntry` in `src/learning/schemas.ts` (deterministic token retrieval,
no vector store required).

Storage: `Architect/runtime/learning/knowledge/<entry_id>.json`
"""

import json
import logging
import datetime
import hashlib
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _make_entry_id(title: str, content: str, tags: list) -> str:
    """Content-derived id: re-saving the same entry updates it in place."""
    fingerprint = "|".join([title, content, ",".join(sorted(str(t) for t in tags))])
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()
    return f"kb_{digest[:12]}"


class KnowledgeBase:
    """Deterministic, file-backed knowledge store with tag/substring search."""

    def __init__(self, kb_dir: str = "Architect/runtime/learning/knowledge"):
        self.kb_dir = Path(kb_dir)
        self.kb_dir.mkdir(parents=True, exist_ok=True)

    def save(self, entry: dict) -> dict:
        """Persist a knowledge entry; assigns entry_id/timestamp when missing."""
        entry = dict(entry)
        timestamp = entry.get("timestamp") or datetime.datetime.utcnow().isoformat() + "Z"
        entry["timestamp"] = timestamp
        if not entry.get("entry_id"):
            entry["entry_id"] = _make_entry_id(entry.get("title", ""), entry.get("content", ""), entry.get("tags", []))
        entry.setdefault("title", "")
        entry.setdefault("content", "")
        entry.setdefault("tags", [])
        entry.setdefault("source", "internal")
        entry.setdefault("confidence", 0.5)
        entry["updated_at"] = timestamp

        path = self.kb_dir / f"{entry['entry_id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
        logger.info("Knowledge entry saved: %s (%s)", path, entry["title"][:60])
        return entry

    def load(self, entry_id: str) -> dict:
        path = self.kb_dir / f"{entry_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Knowledge entry not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def all(self) -> list:
        entries = []
        for path in sorted(self.kb_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entries.append(json.load(f))
            except Exception as exc:
                logger.error("Failed to load knowledge entry %s: %s", path, exc)
        return entries

    def search(self, query_tags: list = None, query_content: str = None, limit: int = 10) -> list:
        """Search by tag overlap and/or content substring; returns scored matches.

        Score = 2 * matched_tags + content_hit_frequency. Entries with zero score
        are excluded; results are sorted by score descending, newest first on ties.
        """
        query_tags = [t.lower() for t in (query_tags or [])]
        query_content = (query_content or "").lower().strip()
        results = []
        for entry in self.all():
            tags = [str(t).lower() for t in entry.get("tags", [])]
            matched_tags = [t for t in query_tags if t in tags]
            content = str(entry.get("content", "")).lower()
            content_hits = content.count(query_content) if query_content else 0
            score = 2.0 * len(matched_tags) + (1.0 if content_hits > 0 else 0.0) + min(content_hits, 5) * 0.1
            if score <= 0:
                continue
            results.append({
                "entry": entry,
                "score": round(score, 4),
                "matched_tags": matched_tags,
                "content_hits": content_hits,
            })
        # Stable two-pass sort: newest first on ties, then score descending.
        results.sort(key=lambda r: str(r["entry"].get("timestamp", "")), reverse=True)
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    def query(self, query_text: str, limit: int = 10) -> list:
        """Convenience: split `query_text` into tag candidates + content query."""
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_-]{2,}", query_text.lower())
        return self.search(query_tags=tokens, query_content=query_text, limit=limit)


class KnowledgeEntryParser:
    """Extract knowledge entries from reflection outputs (journal / DSR)."""

    @staticmethod
    def extract_from_reflection(reflection_output) -> list:
        """Parse a GenAIClient reflection (dict or string) into knowledge entries.

        Accepts:
          - journal dict:  {structured_insights: {summary, observations, anomalies, hypothesis}}
          - DSR dict:      {structured_reflection: {diagnosis, summary, recommendation, confidence, ...}}
          - plain string
        Returns a list of entry dicts ready for KnowledgeBase.save().
        """
        now = datetime.datetime.utcnow().isoformat() + "Z"
        entries = []

        if isinstance(reflection_output, str):
            text = reflection_output.strip()
            if not text:
                return entries
            entries.append({
                "title": text.splitlines()[0][:80] if text else "Reflection note",
                "content": text,
                "tags": ["reflection"],
                "source": "reflection",
                "confidence": 0.5,
                "timestamp": now,
            })
            return entries

        if not isinstance(reflection_output, dict):
            logger.warning("KnowledgeEntryParser: unsupported reflection type %s", type(reflection_output).__name__)
            return entries

        insights = reflection_output.get("structured_insights") or {}
        if insights:
            summary = str(insights.get("summary", "")).strip()
            body_parts = [p for p in [
                summary,
                str(insights.get("hypothesis", "")).strip(),
            ] + [str(o) for o in (insights.get("observations") or [])] if p]
            if body_parts:
                entries.append({
                    "title": (summary[:80] or "Journal insight"),
                    "content": "\n".join(body_parts),
                    "tags": ["reflection", "journal"],
                    "source": "reflection",
                    "confidence": 0.5,
                    "timestamp": now,
                })
            for anomaly in insights.get("anomalies") or []:
                entries.append({
                    "title": f"Anomaly: {str(anomaly)[:70]}",
                    "content": str(anomaly),
                    "tags": ["reflection", "anomaly"],
                    "source": "reflection",
                    "confidence": 0.6,
                    "timestamp": now,
                })

        dsr = reflection_output.get("structured_reflection") or {}
        if dsr:
            confidence = dsr.get("confidence", 0.5)
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = 0.5
            diagnosis = str(dsr.get("diagnosis", "")).strip()
            recommendation = str(dsr.get("recommendation", "")).strip()
            body = "\n".join(p for p in [
                str(dsr.get("summary", "")).strip(),
                f"Diagnosis: {diagnosis}" if diagnosis else "",
                f"Recommendation: {recommendation}" if recommendation else "",
            ] if p)
            if body:
                tags = ["reflection", "dsr"]
                risk_flags = dsr.get("risk_flags") or []
                if risk_flags:
                    tags.append("risk")
                entries.append({
                    "title": (diagnosis[:80] or "DSR reflection"),
                    "content": body,
                    "tags": tags,
                    "source": "reflection",
                    "confidence": confidence,
                    "timestamp": now,
                })

        return entries
