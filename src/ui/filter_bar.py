"""Filter bar for prompt-based filtering."""
from typing import List, Callable, Optional
import shlex
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel,
    QToolButton, QMenu, QApplication, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon


class FilterBar(QWidget):
    """Filter bar with include/exclude prompt filters and sorting options."""
    
    filter_changed = pyqtSignal()  # Emitted when filter criteria change
    sort_changed = pyqtSignal()  # Emitted when sort criteria change
    
    # Sort options mapping - Date is default (newest first)
    SORT_OPTIONS = {
        'Date': 'date',
        'Path': 'path',
        'Dimensions': 'dimensions',
        'File Size': 'file_size',
        'Random': 'random'
    }
    
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
        self.include_input.setPlaceholderText('Enter terms (comma separated, or "quoted phrase")...')
        self.include_input.returnPressed.connect(self._on_filter_changed)  # Trigger on Enter
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
        self.exclude_input.setPlaceholderText('Enter terms (comma separated, or "quoted phrase")...')
        self.exclude_input.returnPressed.connect(self._on_filter_changed)  # Trigger on Enter
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
        
        # Search button
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self._on_filter_changed)
        self.search_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: #fff;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5aa9ff;
            }
            QPushButton:pressed {
                background-color: #3a8eef;
            }
        """)
        layout.addWidget(self.search_btn)
        
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
        
        # Orientation filter checkboxes
        orientation_label = QLabel("Orientation:")
        layout.addWidget(orientation_label)
        
        self.portrait_checkbox = QCheckBox("Portrait")
        self.portrait_checkbox.setChecked(True)
        self.portrait_checkbox.stateChanged.connect(self._on_filter_changed)
        self.portrait_checkbox.setStyleSheet("""
            QCheckBox {
                color: #eee;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
            }
        """)
        layout.addWidget(self.portrait_checkbox)
        
        self.landscape_checkbox = QCheckBox("Landscape")
        self.landscape_checkbox.setChecked(True)
        self.landscape_checkbox.stateChanged.connect(self._on_filter_changed)
        self.landscape_checkbox.setStyleSheet("""
            QCheckBox {
                color: #eee;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
            }
        """)
        layout.addWidget(self.landscape_checkbox)
        
        self.square_checkbox = QCheckBox("Square")
        self.square_checkbox.setChecked(True)
        self.square_checkbox.stateChanged.connect(self._on_filter_changed)
        self.square_checkbox.setStyleSheet("""
            QCheckBox {
                color: #eee;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
            }
        """)
        layout.addWidget(self.square_checkbox)
        
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
        """Handle input changes - no longer auto-triggers search."""
        # Removed auto-trigger, user must press Enter or click Search
        pass
    
    def _on_filter_changed(self):
        """Emit filter changed signal."""
        self.filter_changed.emit()
    
    def _on_sort_changed(self):
        """Emit sort changed signal."""
        self.sort_changed.emit()
    
    def get_sort_by(self) -> str:
        """Get the current sort field."""
        # Use external combo if it exists, otherwise fall back to internal (or default)
        if hasattr(self, '_external_sort_combo'):
            sort_text = self._external_sort_combo.currentText()
        else:
            sort_text = 'Date'  # Default
        return self.SORT_OPTIONS.get(sort_text, 'date')
    
    def get_reverse_sort(self) -> bool:
        """Get whether reverse sort is enabled."""
        # Use external checkbox if it exists
        if hasattr(self, '_external_reverse_checkbox'):
            return self._external_reverse_checkbox.isChecked()
        return False  # Default
    
    def create_sort_controls(self, parent: Optional[QWidget] = None) -> QWidget:
        """Create a widget with sort controls for placement elsewhere."""
        container = QWidget(parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel("Sort by:"))
        
        # Create new combo box (don't reuse the hidden one)
        sort_combo = QComboBox()
        sort_combo.addItems(list(self.SORT_OPTIONS.keys()))
        sort_combo.setCurrentText('Date')
        sort_combo.currentTextChanged.connect(self._on_sort_combo_changed)
        sort_combo.setStyleSheet("""
            QComboBox {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                padding: 5px;
                border-radius: 4px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #2a2a2a;
                color: #eee;
                selection-background-color: #4a9eff;
            }
        """)
        self._external_sort_combo = sort_combo
        layout.addWidget(sort_combo)
        
        # Reverse checkbox
        reverse_checkbox = QCheckBox("Reverse")
        reverse_checkbox.setChecked(False)
        reverse_checkbox.stateChanged.connect(self._on_reverse_checkbox_changed)
        reverse_checkbox.setStyleSheet("""
            QCheckBox {
                color: #eee;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background-color: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #4a9eff;
            }
        """)
        self._external_reverse_checkbox = reverse_checkbox
        layout.addWidget(reverse_checkbox)
        
        layout.addStretch()
        
        return container
    
    def _on_sort_combo_changed(self, text: str):
        """Handle external sort combo change."""
        # Emit sort changed signal
        self.sort_changed.emit()
    
    def _on_reverse_checkbox_changed(self, state):
        """Handle external reverse checkbox change."""
        # Emit sort changed signal
        self.sort_changed.emit()
    
    def _parse_terms(self, text: str) -> List[str]:
        """
        Parse filter terms, handling quoted phrases and comma separation.
        
        Examples:
            'term1, term2' -> ['term1', 'term2']
            '"quoted phrase", term' -> ['quoted phrase', 'term']
            'term1,term2,"phrase 1, phrase 2"' -> ['term1', 'term2', 'phrase 1, phrase 2']
        """
        if not text:
            return []
        
        terms = []
        current_term = []
        in_quotes = False
        
        for char in text:
            if char == '"':
                in_quotes = not in_quotes
            elif char == ',' and not in_quotes:
                # End of term
                term = ''.join(current_term).strip()
                if term:
                    terms.append(term)
                current_term = []
            else:
                current_term.append(char)
        
        # Add last term
        term = ''.join(current_term).strip()
        if term:
            terms.append(term)
        
        return terms
    
    def get_include_terms(self) -> List[str]:
        """Get list of include terms."""
        text = self.include_input.text().strip()
        return self._parse_terms(text)
    
    def get_exclude_terms(self) -> List[str]:
        """Get list of exclude terms."""
        text = self.exclude_input.text().strip()
        return self._parse_terms(text)
    
    def get_orientation_filters(self) -> dict:
        """Get orientation filter settings."""
        return {
            'portrait': self.portrait_checkbox.isChecked(),
            'landscape': self.landscape_checkbox.isChecked(),
            'square': self.square_checkbox.isChecked()
        }
    
    def clear_filters(self):
        """Clear all filter inputs."""
        self.include_input.clear()
        self.exclude_input.clear()
        self.portrait_checkbox.setChecked(True)
        self.landscape_checkbox.setChecked(True)
        self.square_checkbox.setChecked(True)
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
        Separate multiple terms with commas. Use quotes for phrases with commas.</p>
        <p><b>Exclude:</b> Hide images whose prompt contains ANY of these terms.<br>
        Separate multiple terms with commas. Use quotes for phrases with commas.</p>
        <p><b>Examples:</b></p>
        <ul>
            <li>Include: <code>blue sky, clouds</code> → Shows images with both "blue sky" AND "clouds"</li>
            <li>Include: <code>"blue sky", clouds</code> → Shows images with "blue sky" (as phrase) AND "clouds"</li>
            <li>Exclude: <code>nsfw, blurry</code> → Hides images with "nsfw" OR "blurry"</li>
        </ul>
        <p>Filtering is case-insensitive. Press Enter or click Search to apply filters.</p>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Filter Help")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(help_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
