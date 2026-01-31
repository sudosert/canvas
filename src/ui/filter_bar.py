"""Filter bar for prompt-based filtering."""
from typing import List, Callable
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QToolButton, QMenu, QApplication
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction


class FilterBar(QWidget):
    """Filter bar with include/exclude prompt filters."""
    
    filter_changed = pyqtSignal()  # Emitted when filter criteria change
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_filter_changed)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(10)
        
        # Include filter
        include_label = QLabel("Include:")
        layout.addWidget(include_label)
        
        self.include_input = QLineEdit()
        self.include_input.setPlaceholderText("Enter terms to include (comma separated)...")
        self.include_input.textChanged.connect(self._on_input_changed)
        self.include_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4a9eff;
            }
        """)
        layout.addWidget(self.include_input, 2)
        
        # Exclude filter
        exclude_label = QLabel("Exclude:")
        layout.addWidget(exclude_label)
        
        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("Enter terms to exclude (comma separated)...")
        self.exclude_input.textChanged.connect(self._on_input_changed)
        self.exclude_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 1px solid #ff6b6b;
            }
        """)
        layout.addWidget(self.exclude_input, 2)
        
        # Clear button
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_filters)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 5px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        layout.addWidget(self.clear_btn)
        
        # Help button
        self.help_btn = QToolButton()
        self.help_btn.setText("?")
        self.help_btn.setToolTip("Filter Help")
        self.help_btn.clicked.connect(self._show_help)
        self.help_btn.setStyleSheet("""
            QToolButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                border-radius: 12px;
                width: 24px;
                height: 24px;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
            }
        """)
        layout.addWidget(self.help_btn)
        
        # Results label
        self.results_label = QLabel("No images loaded")
        self.results_label.setStyleSheet("color: #888;")
        layout.addWidget(self.results_label)
        
        layout.addStretch()
        
        # Set widget style
        self.setStyleSheet("""
            FilterBar {
                background-color: #1e1e1e;
                border-bottom: 1px solid #333;
            }
            QLabel {
                color: #eee;
            }
        """)
    
    def _on_input_changed(self):
        """Handle input changes with debounce."""
        self._debounce_timer.stop()
        self._debounce_timer.start(300)  # 300ms debounce
    
    def _on_filter_changed(self):
        """Emit filter changed signal."""
        self.filter_changed.emit()
    
    def get_include_terms(self) -> List[str]:
        """Get list of include terms."""
        text = self.include_input.text().strip()
        if not text:
            return []
        # Split by comma and clean up
        terms = [t.strip() for t in text.split(',') if t.strip()]
        return terms
    
    def get_exclude_terms(self) -> List[str]:
        """Get list of exclude terms."""
        text = self.exclude_input.text().strip()
        if not text:
            return []
        # Split by comma and clean up
        terms = [t.strip() for t in text.split(',') if t.strip()]
        return terms
    
    def clear_filters(self):
        """Clear all filter inputs."""
        self.include_input.clear()
        self.exclude_input.clear()
        self._on_filter_changed()
    
    def set_results_count(self, count: int, total: int):
        """Update the results count label."""
        self.results_label.setText(f"Showing {count} of {total} images")
    
    def _show_help(self):
        """Show filter help dialog."""
        from PyQt6.QtWidgets import QMessageBox
        
        help_text = """
        <h3>Filter Help</h3>
        <p><b>Include:</b> Only show images whose prompt contains ALL of these terms.<br>
        Separate multiple terms with commas.</p>
        <p><b>Exclude:</b> Hide images whose prompt contains ANY of these terms.<br>
        Separate multiple terms with commas.</p>
        <p><b>Examples:</b></p>
        <ul>
            <li>Include: "blue sky, clouds" → Shows images with both "blue sky" AND "clouds"</li>
            <li>Exclude: "nsfw, blurry" → Hides images with "nsfw" OR "blurry"</li>
        </ul>
        <p>Filtering is case-insensitive.</p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Filter Help")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(help_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
