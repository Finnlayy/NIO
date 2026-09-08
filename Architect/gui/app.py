import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTabWidget
from PyQt6.QtCore import Qt
from gui.theme import apply_theme
from gui.widgets.command_bar import CommandBar
from gui.widgets.ticker_tape import TickerTape
from gui.views.unified_chart_tab import UnifiedChartTab

# Phase 4/5 tabs (RLHF feedback + self-model dashboards). Import-guarded so
# the terminal still boots if a Phase 5 visualization dependency is missing.
try:
    from gui.views.feedback_dialog import FeedbackDialog
    PHASE4_FEEDBACK_AVAILABLE = True
except ImportError:
    FeedbackDialog = None
    PHASE4_FEEDBACK_AVAILABLE = False

try:
    from gui.views.trajectory_visualizer import TrajectoryVisualizer
    from gui.views.alignment_dashboard import AlignmentDashboardTab
    PHASE5_TABS_AVAILABLE = True
except ImportError:
    TrajectoryVisualizer = None
    AlignmentDashboardTab = None
    PHASE5_TABS_AVAILABLE = False


class GMTMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GMT (Global Market Terminal) - OMEGA")
        self.resize(1280, 720)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)

        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        self.cmd_bar = CommandBar()
        layout.addWidget(self.cmd_bar)

        if PHASE5_TABS_AVAILABLE:
            # Phase 5: tabbed shell — chart, trajectory timeline, alignment dashboard.
            self.tabs = QTabWidget()
            self.chart = UnifiedChartTab()
            self.tabs.addTab(self.chart, "Chart")
            self.trajectory_visualizer = TrajectoryVisualizer()
            self.tabs.addTab(self.trajectory_visualizer, "Trajectory")
            self.alignment_dashboard = AlignmentDashboardTab()
            self.tabs.addTab(self.alignment_dashboard, "Alignment")
            layout.addWidget(self.tabs)
        else:
            self.chart = UnifiedChartTab()
            layout.addWidget(self.chart)

        self.tape = TickerTape()
        layout.addWidget(self.tape)

def main():
    app = QApplication(sys.argv)
    apply_theme(app)
    window = GMTMainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
