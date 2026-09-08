"""Insight display (Phase 5 — Self-Model & Insights).

Loads persisted insights and formats them for CLI or GUI presentation.
Headless + stdlib-only; the PyQt6 dashboard renders the same strings.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CATEGORY_ICONS = {
    "strength": "[+]",
    "weakness": "[!]",
    "recommendation": "[>]",
}


class InsightDisplay:
    """Load and format self-model insights."""

    def __init__(self, insights_dir: str = "Architect/runtime/insights"):
        self.insights_dir = Path(insights_dir)

    def load_insights(self) -> list:
        """Load all persisted insights, newest file first."""
        insights = []
        files = sorted(self.insights_dir.glob("*.json"), reverse=True)
        for path in files:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
            except Exception as exc:
                logger.error("Failed to load insights from %s: %s", path, exc)
                continue
            for data in payload.get("insights", []):
                if isinstance(data, dict) and data.get("insight_id"):
                    insights.append(data)
        return insights

    @staticmethod
    def format_for_display(insight, style: str = "cli") -> str:
        """Format one insight dict for CLI (`style="cli"`) or GUI (`style="gui"`)."""
        if not isinstance(insight, dict):
            insight = insight.to_dict() if hasattr(insight, "to_dict") else dict(insight)
        icon = _CATEGORY_ICONS.get(insight.get("category", ""), "[?]")
        confidence = insight.get("confidence", 0.0)
        if style == "gui":
            return (f"<b>{icon} {insight.get('category', '?').upper()}</b> "
                    f"(confidence {confidence:.2f})<br>{insight.get('content', '')}")
        return f"{icon} ({confidence:.2f}) {insight.get('content', '')}"

    @staticmethod
    def format_all(insights: list, style: str = "cli") -> str:
        """Format a list of insights grouped by category."""
        order = ["strength", "weakness", "recommendation"]
        sections = []
        for category in order:
            group = [i for i in insights if (i.get("category") if isinstance(i, dict) else i.category) == category]
            if not group:
                continue
            header = {"strength": "Strengths", "weakness": "Weaknesses",
                      "recommendation": "Recommendations"}[category]
            if style == "gui":
                body = "<br>".join(InsightDisplay.format_for_display(i, "gui") for i in group)
                sections.append(f"<h3>{header}</h3>{body}")
            else:
                lines = [InsightDisplay.format_for_display(i, "cli") for i in group]
                sections.append(f"== {header} ==\n" + "\n".join(lines))
        return ("\n\n".join(sections)) if style != "gui" else ("<html>" + "".join(sections) + "</html>")
