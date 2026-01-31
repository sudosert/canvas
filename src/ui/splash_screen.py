"""Splash screen for application startup."""
from PyQt6.QtWidgets import QSplashScreen, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont


class SplashScreen(QSplashScreen):
    """Custom splash screen with progress indicator."""
    
    def __init__(self):
        # Create a simple colored pixmap
        pixmap = QPixmap(500, 300)
        pixmap.fill(QColor(35, 35, 35))
        
        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint)
        
        # Set up the UI
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the splash screen UI."""
        # Create a widget to hold our layout
        widget = QWidget(self)
        widget.setGeometry(0, 0, 500, 300)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("SD Image Viewer")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 32px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title)
        
        # Version
        version = QLabel("v1.0.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 14px;
            }
        """)
        layout.addWidget(version)
        
        layout.addStretch()
        
        # Status message
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #555;
                border-radius: 3px;
                background-color: #2a2a2a;
                height: 6px;
            }
            QProgressBar::chunk {
                background-color: #4a9eff;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
    def update_status(self, message: str):
        """Update the status message."""
        self.status_label.setText(message)
        self.repaint()
        
    def set_progress(self, value: int, maximum: int = 100):
        """Set progress bar value."""
        self.progress_bar.setRange(0, maximum)
        self.progress_bar.setValue(value)
        self.repaint()
