"""Error pattern detection (Phase 4 — RLHF Integration).

Groups recurring failure signatures so the engine can warn the orchestrator
before repeating the same error. Python counterpart of blueprint
`ErrorPattern` in `src/learning/schemas.ts`.

Known error codes follow the protocol error taxonomy
(`E_SAFETY_NET`, `E_TRIGGER_INVALID`, `E_SCHEMA_INVALID`, `E_INTERNAL`, ...)
with a keyword fallback for unclassified errors.

Storage: `Architect/runtime/learning/error_patterns/<pattern_id>.json`
"""

import json
import logging
import datetime
import hashlib
import re
from pathlib import Path

logger = logging.getLogger(__name__)

KNOWN_ERROR_TYPES = [
    "E_SAFETY_NET",
    "E_TRIGGER_INVALID",
    "E_SCHEMA_INVALID",
    "E_INTERNAL",
    "E_FORBIDDEN_ZONE",
    "E_TIMEOUT",
    "E_PERMISSION_DENIED",
    "E_UNKNOWN",
]

# Keyword heuristics for errors that arrive without an explicit error code.
_KEYWORD_MAP = [
    (r"safety[_ ]?net", "E_SAFETY_NET"),
    (r"trigger", "E_TRIGGER_INVALID"),
    (r"schema|invalid[_ ]?json|validation", "E_SCHEMA_INVALID"),
    (r"forbidden[_ ]?zone", "E_FORBIDDEN_ZONE"),
    (r"timeout|timed[_ ]?out", "E_TIMEOUT"),
    (r"permission|denied|sandbox", "E_PERMISSION_DENIED"),
]

DEFAULT_ALERT_THRESHOLD = 3


def classify_error(error) -> str:
    """Map an error (string or dict) to an error_type from the taxonomy."""
    if isinstance(error, dict):
        for key in ("error_type", "type", "code", "kind"):
            value = error.get(key)
            if isinstance(value, str) and value.upper() in KNOWN_ERROR_TYPES:
                return value.upper()
        message = str(error.get("message", ""))
    else:
        message = str(error)

    upper = message.upper()
    for known in KNOWN_ERROR_TYPES:
        if known in upper:
            return known
    lowered = message.lower()
    for pattern, error_type in _KEYWORD_MAP:
        if re.search(pattern, lowered):
            return error_type
    return "E_UNKNOWN"


def make_pattern_id(error_type: str, tokens: list) -> str:
    """Deterministic fingerprint for an error signature (blueprint `fingerprint`)."""
    fingerprint = "|".join([error_type] + sorted(tokens))
    return "ep_" + hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:12]


class ErrorPattern:
    """A recurring failure signature with occurrence statistics."""

    def __init__(self, pattern_id: str, error_type: str, frequency: int = 0,
                 first_seen: str = None, last_seen: str = None,
                 sample_messages: list = None, tokens: list = None):
        self.pattern_id = pattern_id
        self.error_type = error_type
        self.frequency = frequency
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.sample_messages = sample_messages or []
        self.tokens = tokens or []

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "error_type": self.error_type,
            "frequency": self.frequency,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "sample_messages": self.sample_messages[:5],
            "tokens": self.tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorPattern":
        return cls(
            pattern_id=data.get("pattern_id", ""),
            error_type=data.get("error_type", "E_UNKNOWN"),
            frequency=int(data.get("frequency", 0)),
            first_seen=data.get("first_seen"),
            last_seen=data.get("last_seen"),
            sample_messages=data.get("sample_messages") or [],
            tokens=data.get("tokens") or [],
        )


class ErrorPatternDetector:
    """Detect and track recurring error patterns from raw error lists."""

    def __init__(self, event_bus=None, storage: "ErrorPatternStorage" = None):
        self.event_bus = event_bus
        self.storage = storage

    def detect(self, errors: list) -> list:
        """Group errors by taxonomy type; returns list[ErrorPattern] sorted by frequency.

        The pattern fingerprint is the error *type* (TODO Phase 4: "group errors
        by type"), so `E_SAFETY_NET: feed stale` and `E_SAFETY_NET: feed stale
        again` fold into one pattern with per-message samples retained.
        """
        now = datetime.datetime.utcnow().isoformat() + "Z"
        groups = {}
        for error in errors or []:
            error_type = classify_error(error)
            message = error.get("message", "") if isinstance(error, dict) else str(error)
            timestamp = (error.get("timestamp") if isinstance(error, dict) else None) or now
            tokens = sorted(set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", message.lower())))[:12]
            pattern_id = make_pattern_id(error_type, [])
            group = groups.setdefault(pattern_id, ErrorPattern(
                pattern_id=pattern_id,
                error_type=error_type,
                first_seen=timestamp,
                last_seen=timestamp,
                tokens=tokens,
            ))
            group.frequency += 1
            group.last_seen = timestamp
            if len(tokens) > len(group.tokens):
                group.tokens = tokens
            if message and message not in group.sample_messages:
                group.sample_messages.append(message[:300])

        patterns = sorted(groups.values(), key=lambda p: (p.frequency, p.first_seen), reverse=True)
        if self.storage:
            patterns = [self._merge_with_storage(p) for p in patterns]
        return patterns

    def _merge_with_storage(self, pattern: ErrorPattern) -> ErrorPattern:
        """Fold persisted occurrences into the freshly detected pattern."""
        if not self.storage:
            return pattern
        persisted = self.storage.load(pattern.pattern_id)
        if persisted:
            pattern.frequency += persisted.frequency
            if persisted.first_seen and (not pattern.first_seen or persisted.first_seen < pattern.first_seen):
                pattern.first_seen = persisted.first_seen
            if persisted.sample_messages:
                merged = list(pattern.sample_messages)
                for msg in persisted.sample_messages:
                    if msg not in merged:
                        merged.append(msg)
                pattern.sample_messages = merged[:5]
        return pattern

    def detect_and_store(self, errors: list) -> list:
        """Detect, merge with persisted stats, and persist back."""
        patterns = self.detect(errors)
        if self.storage:
            for pattern in patterns:
                self.storage.save(pattern)
        return patterns

    def alert_if_threshold_exceeded(self, pattern: ErrorPattern, threshold: int = DEFAULT_ALERT_THRESHOLD) -> bool:
        """Emit an `error_pattern_alert` event when frequency exceeds threshold."""
        if pattern.frequency <= threshold:
            return False
        if self.event_bus:
            self.event_bus.emit(self.event_bus.build_event(
                event_kind="error_pattern_alert",
                job_id=pattern.pattern_id,
                message=(f"Error pattern {pattern.error_type} exceeded threshold "
                         f"({pattern.frequency} > {threshold})."),
                pattern_id=pattern.pattern_id,
                error_type=pattern.error_type,
                frequency=pattern.frequency,
                threshold=threshold,
            ))
        return True


class ErrorPatternStorage:
    """Persistence for error patterns (`<patterns_dir>/<pattern_id>.json`)."""

    def __init__(self, patterns_dir: str = "Architect/runtime/learning/error_patterns"):
        self.patterns_dir = Path(patterns_dir)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

    def save(self, pattern: ErrorPattern) -> Path:
        path = self.patterns_dir / f"{pattern.pattern_id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pattern.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Error pattern saved: %s (%s, freq=%d)", path, pattern.error_type, pattern.frequency)
        return path

    def load(self, pattern_id: str) -> ErrorPattern:
        path = self.patterns_dir / f"{pattern_id}.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return ErrorPattern.from_dict(json.load(f))

    def load_all(self) -> list:
        patterns = []
        for path in sorted(self.patterns_dir.glob("*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    patterns.append(ErrorPattern.from_dict(json.load(f)))
            except Exception as exc:
                logger.error("Failed to load error pattern %s: %s", path, exc)
        return sorted(patterns, key=lambda p: p.frequency, reverse=True)

    def frequent(self, threshold: int = DEFAULT_ALERT_THRESHOLD) -> list:
        return [p for p in self.load_all() if p.frequency > threshold]
