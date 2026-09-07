"""Alignment dashboard tab (Phase 5 — Self-Model & Insights).

Displays current alignment / safety / learning-efficiency metrics, their
trend, and the latest risk-guard status. The headless `AlignmentDashboardModel`
prepares all display data (testable without PyQt6); `AlignmentDashboardTab`
is the PyQt6 shell wired into `GMTMainWindow`.
"""

import logging
from pathlib import Path

from core.alignment.alignment_tracker import AlignmentTracker
from core.alignment.alignment_dashboard import AlignmentDashboard
from core.learning.risk_guards import RiskGuardStorage
from core.self_model.insight_display import InsightDisplay

logger = logging.getLogger(__name__)


class AlignmentDashboardModel:
    """Headless presenter: composes metrics for the dashboard tab."""

    def __init__(self, alignment_service: AlignmentDashboard = None,
                 tracker: AlignmentTracker = None, risk_storage: RiskGuardStorage = None,
                 plan_id: str = None):
        self.alignment_service = alignment_service or AlignmentDashboard()
        self.tracker = tracker or AlignmentTracker()
        self.risk_storage = risk_storage or RiskGuardStorage()
        self.plan_id = plan_id

    def compose(self, plan_id: str = None) -> dict:
        """Return display-ready metrics for the latest plan snapshot."""
        plan_id = plan_id or self.plan_id
        latest = self.alignment_service.latest(plan_id) if plan_id else {}
        aggregate = self.alignment_service.aggregate_metrics(plan_id) if plan_id else {"snapshot_count": 0}
        guards = self.risk_storage.load_all()
        guards_passed = sum(1 for g in guards if g.get("passed") is True)

        rows = [
            ("alignment_score", latest.get("alignment_score", "n/a")),
            ("safety_score", latest.get("safety_score", "n/a")),
            ("learning_efficiency", latest.get("learning_efficiency", latest.get("components", {}).get("learning_efficiency", "n/a"))),
            ("risk_guards_passed", f"{guards_passed}/{len(guards)}"),
            ("snapshots", aggregate.get("snapshot_count", 0)),
        ]
        trend = [h.get("alignment_score") for h in aggregate.get("history", [])
                 if h.get("alignment_score") is not None]
        return {
            "plan_id": plan_id,
            "rows": rows,
            "alignment_trend": trend,
            "stats": {
                "alignment_score_stats": aggregate.get("alignment_score_stats"),
                "safety_score_stats": aggregate.get("safety_score_stats"),
            },
        }

    def format_summary(self, plan_id: str = None) -> str:
        data = self.compose(plan_id)
        lines = [f"Plan: {data['plan_id'] or 'n/a'}"]
        for key, value in data["rows"]:
            lines.append(f"{key}: {value}")
        return "\n".join(lines)


# ---- PyQt6 shell (import-guarded) ---------------------------------------------

try:  # pragma: no cover - exercised only when PyQt6 is installed
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QTextEdit

    PYQT6_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYQT6_AVAILABLE = False


if PYQT6_AVAILABLE:

    class AlignmentDashboardTab(QWidget):
        """Dashboard tab showing alignment metrics, trends and risk-guard status."""

        def __init__(self, model: AlignmentDashboardModel = None, parent=None):
            super().__init__(parent)
            self.model = model or AlignmentDashboardModel()

            layout = QVBoxLayout()
            self.setLayout(layout)

            self.title_label = QLabel("Alignment Dashboard — human preference & safety tracking")
            layout.addWidget(self.title_label)

            self.metrics_labels = {}
            for key in ("alignment_score", "safety_score", "learning_efficiency",
                        "risk_guards_passed", "snapshots"):
                label = QLabel(f"{key}: —")
                self.metrics_labels[key] = label
                layout.addWidget(label)

            self.trend_view = QTextEdit()
            self.trend_view.setReadOnly(True)
            self.trend_view.setMaximumHeight(160)
            layout.addWidget(self.trend_view)

            self.refresh_btn = QPushButton("Refresh")
            self.refresh_btn.clicked.connect(self.refresh)
            layout.addWidget(self.refresh_btn)

        def refresh(self, plan_id: str = None):
            """Reload latest metrics and update the labels."""
            data = self.model.compose(plan_id)
            for key, value in data["rows"]:
                self.metrics_labels[key].setText(f"{key}: {value}")
            trend = data["alignment_trend"]
            self.trend_view.setPlainText("alignment trend: " +
                                         (" -> ".join(f"{t:.2f}" for t in trend) if trend else "(no data)"))

else:

    class AlignmentDashboardTab:  # pragma: no cover - fallback when PyQt6 is absent
        """Placeholder raising a clear error when PyQt6 is not installed."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "AlignmentDashboardTab requires PyQt6. Use the headless "
                "AlignmentDashboardModel (or core.alignment) APIs instead."
            )
