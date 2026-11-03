"""Apollo-Python-Paket (Backend-Seite von Apollo).

Historisch lebte „Apollo" in diesem Repository nur als Frontend-UI
(``frontend/src/apollo/``). Dieses Paket hosts die serverseitige
Orchestrator-Schicht — namentlich den **Ciel** JIT-Tool-Orchestrator
(``apollo.ciel``) — ohne bestehenden Code zu verändern.
"""

from __future__ import annotations

__all__: list[str] = ["__version__"]

__version__ = "0.1.0"
