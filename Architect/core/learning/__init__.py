"""Continuous-learning engine (Phase 4 — RLHF Integration).

Python counterpart of the blueprint's TypeScript `src/learning/` subsystem:
skill profiles (Wilson-score), SM-2 spaced repetition, error pattern memory,
knowledge base, risk guards and the preference model updater.

Modules are stdlib-only by design (blueprint dependency model divergence is
preserved: no numpy/torch/onnx required for the learning core).
"""
