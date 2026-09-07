"""Trajectory visualizer (Phase 5 — Self-Model & Insights).

Renders a plan trajectory (time axis vs. execution state) with highlighted
state transitions and event markers. Uses a plain QPainter timeline so Phase 5
does not add a hard pyqtgraph/matplotlib dependency (divergence documented in
Architect/docs/DIVERGENCES.md); data preparation lives in the headless
`TrajectoryModel` so it is testable without PyQt6.
"""

import logging
import datetime

from core.trajectory.trajectory_collector import TrajectoryPoint
from core.state_machine import SystemExecutionState

logger = logging.getLogger(__name__)

STATE_ORDER = ["PLANNING", "DISPATCHED", "RUNNING", "REFLECTING", "COMPLETE"]


class TrajectoryModel:
    """Headless timeline model: points -> normalized (x, y) + transitions."""

    @staticmethod
    def _ts(value) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return datetime.datetime.fromisoformat(str(value).replace("Z", "")).timestamp()
        except (ValueError, TypeError):
            return 0.0

    @classmethod
    def build(cls, trajectory_points: list) -> dict:
        """Return {points: [{x, y, state, event_ids, event_kind, timestamp}],
        transitions: [{from, to, x}], states: STATE_ORDER}."""
        points = [p for p in (trajectory_points or [])]
        if not points:
            return {"points": [], "transitions": [], "states": STATE_ORDER}

        times = [cls._ts(cls._field(p, "timestamp")) for p in points]
        t_min, t_max = min(times), max(times)
        span = (t_max - t_min) or 1.0

        model_points = []
        transitions = []
        prev_state = None
        for point, t in zip(points, times):
            state = str(cls._field(point, "state", "PLANNING"))
            x = (t - t_min) / span
            y = STATE_ORDER.index(state) / (len(STATE_ORDER) - 1) if state in STATE_ORDER else 0.0
            if prev_state is not None and prev_state != state:
                transitions.append({"from": prev_state, "to": state, "x": x})
            prev_state = state
            model_points.append({
                "x": round(x, 6),
                "y": round(y, 6),
                "state": state,
                "event_ids": cls._field(point, "event_ids", []) or [],
                "event_kind": cls._field(point, "event_kind", ""),
                "timestamp": cls._field(point, "timestamp", ""),
            })
        return {"points": model_points, "transitions": transitions, "states": STATE_ORDER}

    @classmethod
    def _field(cls, point, name, default=None):
        if isinstance(point, dict):
            return point.get(name, default)
        return getattr(point, name, default)

    @classmethod
    def highlight_events(cls, trajectory_points: list, event_ids: list) -> list:
        """Model points containing any of `event_ids` (for timeline highlighting)."""
        wanted = set(event_ids or [])
        model = cls.build(trajectory_points)
        return [p for p in model["points"] if wanted.intersection(p["event_ids"])]


# ---- PyQt6 shell (import-guarded) ---------------------------------------------

try:  # pragma: no cover - exercised only when PyQt6 is installed
    from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
    from PyQt6.QtGui import QPainter, QColor, QPen
    from PyQt6.QtCore import Qt

    PYQT6_AVAILABLE = True
except ImportError:  # pragma: no cover
    PYQT6_AVAILABLE = False


if PYQT6_AVAILABLE:

    class TrajectoryVisualizer(QWidget):
        """Timeline widget: x = time, y = execution state; transitions highlighted."""

        STATE_COLORS = {
            "PLANNING": QColor("#F28C00"),
            "DISPATCHED": QColor("#FFD600"),
            "RUNNING": QColor("#00C176"),
            "REFLECTING": QColor("#00A8FF"),
            "COMPLETE": QColor("#8A8AFF"),
        }

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setMinimumHeight(220)
            self.model = {"points": [], "transitions": [], "states": STATE_ORDER}
            self.highlighted_event_ids = set()
            layout = QVBoxLayout()
            self.title_label = QLabel("Plan Trajectory")
            layout.addWidget(self.title_label)
            self.setLayout(layout)

        def update(self, trajectory_points):
            """(Re)render the trajectory from a list of TrajectoryPoint/dict."""
            self.model = TrajectoryModel.build(trajectory_points)
            self.update()  # QWidget.repaint

        def show_events(self, event_ids):
            """Highlight trajectory points tied to the given event ids."""
            self.highlighted_event_ids = set(event_ids or [])
            self.update()

        def paintEvent(self, event):  # noqa: N802 (Qt naming)
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#000000"))
            w, h = self.width(), self.height()
            left, right, top, bottom = 60, 20, 30, 40
            plot_w = max(1, w - left - right)
            plot_h = max(1, h - top - bottom)

            # Axis + state guide lines
            pen = QPen(QColor("#333333"))
            painter.setPen(pen)
            for i, state in enumerate(self.model["states"]):
                y = top + int(plot_h * i / (len(self.model["states"]) - 1))
                painter.drawLine(left, y, w - right, y)
                painter.setPen(QPen(QColor("#777777")))
                painter.drawText(5, y + 4, state)
                painter.setPen(pen)

            # Points + connecting line
            prev_px = prev_py = None
            for point in self.model["points"]:
                px = left + int(point["x"] * plot_w)
                py = top + int((1.0 - point["y"]) * plot_h)
                color = self.STATE_COLORS.get(point["state"], QColor("#FFFFFF"))
                if prev_px is not None:
                    painter.setPen(QPen(color, 1))
                    painter.drawLine(prev_px, prev_py, px, py)
                radius = 6 if (set(point["event_ids"]) & self.highlighted_event_ids) else 4
                painter.setBrush(color)
                painter.setPen(QPen(color))
                painter.drawEllipse(px - radius, py - radius, radius * 2, radius * 2)
                prev_px, prev_py = px, py

            # Transition markers
            painter.setPen(QPen(QColor("#FF4D4F")))
            for transition in self.model["transitions"]:
                tx = left + int(transition["x"] * plot_w)
                painter.drawLine(tx, top, tx, top + plot_h)
                painter.drawText(tx + 2, top - 8,
                                 f"{transition['from']}->{transition['to']}")
            painter.end()

else:

    class TrajectoryVisualizer:  # pragma: no cover - fallback when PyQt6 is absent
        """Placeholder raising a clear error when PyQt6 is not installed."""

        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "TrajectoryVisualizer requires PyQt6. Use the headless "
                "TrajectoryModel API for data preparation instead."
            )
