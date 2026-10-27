"""Embedding-Provider für den NCM-Gatekeeper (Modul B).

Der Gatekeeper matcht Intents „im Latent Concept Space". Dafür gibt es zwei
Backends hinter einer Schnittstelle:

* :class:`OnnxEmbeddingProvider` — echte ONNX-Runtime-Inferenz, wenn ein
  Text-Embedding-Modell **plus** passender Tokenizer konfiguriert sind.
* :class:`HashEmbeddingProvider` — deterministischer, Stdlib-only
  Random-Projection-Vektor (SHA-256-geseedet, L2-normalisiert). Das ist der
  Default und folgt bewusst demselben Divergence-Pattern wie
  ``Architect/core/learning/preference_model_updater.py`` (deterministisch,
  ohne torch/onnx trainier- und ausführbar).

Hinweis: ``Architect/models/weights/omega_regime_16d.onnx`` ist ein
Regime-Klassifikator, **kein** Text-Embedding-Modell, und wird daher hier
nicht zweckentfremdet — :class:`AutoEmbeddingProvider` nutzt ONNX nur, wenn
explizit ein Embedding-Modell konfiguriert wurde.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from pathlib import Path
from typing import Any, Protocol

from .errors import CielConfigError

_TOKEN_RE = re.compile(r"[a-zA-Z0-9_äöüÄÖÜß]+")

#: Deckel für den Token-Vektor-Cache (Bounded State: kein unbegrenztes Wachstum).
_TOKEN_CACHE_MAX = 20_000


class EmbeddingProvider(Protocol):
    """Schnittstelle: Text -> L2-normalisierter Konzeptvektor."""

    @property
    def dim(self) -> int: ...

    @property
    def backend(self) -> str: ...

    def embed(self, text: str) -> list[float]: ...


def cosine_similarity(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    """Cosine-Similarity in [-1, 1]; Nullvektoren ergeben 0.0 (nie NaN)."""
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def tokenize(text: str) -> list[str]:
    """Kleinschreibende Wort-Tokens (Hash-Embedding + Anchor-Texte teilen diese)."""
    return _TOKEN_RE.findall((text or "").lower())


class HashEmbeddingProvider:
    """Deterministischer lokaler Embedding-Vektor (Stdlib-only, Default).

    Jedes Token wird per SHA-256-Seed auf einen pseudo-zufälligen
    Einheitsvektor (Random Projection) abgebildet; der Textvektor ist die
    L2-normalisierte Summe. Identische Texte haben Cosine 1.0, disjunkte
    Texte ≈ 0.0 — stabil über Prozesse (kein ``hash()``-Salting).
    """

    def __init__(self, dim: int = 256) -> None:
        if dim < 8:
            raise CielConfigError(f"Embedding-Dimension zu klein: {dim}")
        self._dim = dim
        self._token_cache: dict[str, list[float]] = {}

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def backend(self) -> str:
        return "hash"

    def _token_vector(self, token: str) -> list[float]:
        cached = self._token_cache.get(token)
        if cached is not None:
            return cached
        seed = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        vec = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        vec = [x / norm for x in vec]
        if len(self._token_cache) >= _TOKEN_CACHE_MAX:
            self._token_cache.clear()
        self._token_cache[token] = vec
        return vec

    def embed(self, text: str) -> list[float]:
        tokens = tokenize(text)
        if not tokens:
            return [0.0] * self._dim
        acc = [0.0] * self._dim
        for token in tokens:
            vec = self._token_vector(token)
            for i, value in enumerate(vec):
                acc[i] += value
        norm = math.sqrt(sum(x * x for x in acc))
        if norm == 0.0:
            return [0.0] * self._dim
        return [x / norm for x in acc]


class OnnxEmbeddingProvider:
    """Echte ONNX-Runtime-Inferenz (optional, nur wenn konfiguriert).

    Benötigt ``onnxruntime`` sowie einen ``tokenizer``-Callable, der Text auf
    das Input-Dict des Modells abbildet (z. B. ``{"input_ids": [...]}``), da
    Tokenizer und Modell immer zusammengehören. Der Output wird per
    Mean-Pooling auf einen Vektor reduziert und L2-normalisiert.
    """

    def __init__(
        self,
        model_path: str | Path,
        *,
        tokenizer: Any = None,
        output_index: int = 0,
    ) -> None:
        try:
            import onnxruntime as ort  # type: ignore[import-not-found]
        except ImportError as exc:
            raise CielConfigError(
                "onnxruntime ist nicht installiert — nutze HashEmbeddingProvider (Default) oder installiere onnxruntime."
            ) from exc
        if tokenizer is None:
            raise CielConfigError("OnnxEmbeddingProvider braucht einen passenden 'tokenizer'-Callable.")
        self._model_path = Path(model_path)
        if not self._model_path.is_file():
            raise CielConfigError(f"ONNX-Modell fehlt: {self._model_path}")
        self._tokenizer = tokenizer
        self._output_index = output_index
        self._session = ort.InferenceSession(str(self._model_path), providers=["CPUExecutionProvider"])
        self._dim = 0

    @property
    def dim(self) -> int:
        return self._dim

    @property
    def backend(self) -> str:
        return f"onnx:{self._model_path.name}"

    def embed(self, text: str) -> list[float]:
        import numpy as _np  # type: ignore[import-not-found]

        feeds = {k: _np.asarray(v) for k, v in dict(self._tokenizer(text)).items()}
        outputs = self._session.run(None, feeds)
        pooled = _np.asarray(outputs[self._output_index], dtype=float)
        while pooled.ndim > 1:
            pooled = pooled.mean(axis=tuple(range(1, pooled.ndim)) if pooled.ndim > 2 else 1)
        vec = [float(x) for x in pooled.reshape(-1)]
        if self._dim == 0:
            self._dim = len(vec)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


class AutoEmbeddingProvider:
    """Wählt ONNX, wenn Modell+Tokenizer konfiguriert sind, sonst Hash.

    Fällt bei jedem ONNX-Konfigurations-/Ladefehler transparent auf den
    Hash-Provider zurück (der Gatekeeper darf nie am Embedding sterben).
    """

    def __init__(
        self,
        *,
        dim: int = 256,
        onnx_model: str | Path | None = None,
        onnx_tokenizer: Any = None,
    ) -> None:
        self._delegate: EmbeddingProvider = HashEmbeddingProvider(dim=dim)
        if onnx_model is not None:
            try:
                self._delegate = OnnxEmbeddingProvider(onnx_model, tokenizer=onnx_tokenizer)
            except CielConfigError:
                self._delegate = HashEmbeddingProvider(dim=dim)

    @property
    def dim(self) -> int:
        return self._delegate.dim

    @property
    def backend(self) -> str:
        return self._delegate.backend

    def embed(self, text: str) -> list[float]:
        return self._delegate.embed(text)


__all__ = [
    "AutoEmbeddingProvider",
    "EmbeddingProvider",
    "HashEmbeddingProvider",
    "OnnxEmbeddingProvider",
    "cosine_similarity",
    "tokenize",
]
