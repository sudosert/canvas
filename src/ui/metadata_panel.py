"""Metadata panel for displaying image generation information."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame,
    QPushButton, QApplication, QTextEdit, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..models.image_data import ImageMetadata


class MetadataPanel(QWidget):
    """Panel for displaying image metadata."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_metadata: ImageMetadata = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Image Metadata")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # File info section
        self._add_section("File Information", [
            ("File Name:", "file_name"),
            ("Dimensions:", "dimensions"),
            ("File Size:", "file_size_str"),
            ("Source:", "source_str")
        ])
        
        # Generation params section
        self._add_section("Generation Parameters", [
            ("Model:", "model"),
            ("Model Hash:", "model_hash"),
            ("Sampler:", "sampler"),
            ("Steps:", "steps_str"),
            ("CFG Scale:", "cfg_str"),
            ("Seed:", "seed_str")
        ])
        
        # Prompt section
        prompt_label = QLabel("Prompt:")
        prompt_font = QFont()
        prompt_font.setBold(True)
        prompt_label.setFont(prompt_font)
        self.content_layout.addWidget(prompt_label)
        
        self.prompt_text = QTextEdit()
        self.prompt_text.setReadOnly(True)
        self.prompt_text.setMinimumHeight(80)
        self.prompt_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.prompt_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.content_layout.addWidget(self.prompt_text, 1)  # Add stretch factor
        
        # Copy prompt button
        self.copy_prompt_btn = QPushButton("Copy Prompt")
        self.copy_prompt_btn.clicked.connect(self._copy_prompt)
        self.content_layout.addWidget(self.copy_prompt_btn)
        
        # Negative prompt section
        neg_prompt_label = QLabel("Negative Prompt:")
        neg_prompt_label.setFont(prompt_font)
        self.content_layout.addWidget(neg_prompt_label)
        
        self.neg_prompt_text = QTextEdit()
        self.neg_prompt_text.setReadOnly(True)
        self.neg_prompt_text.setMinimumHeight(60)
        self.neg_prompt_text.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.neg_prompt_text.setStyleSheet("""
            QTextEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        self.content_layout.addWidget(self.neg_prompt_text, 1)  # Add stretch factor
        
        # Copy negative prompt button
        self.copy_neg_prompt_btn = QPushButton("Copy Negative Prompt")
        self.copy_neg_prompt_btn.clicked.connect(self._copy_negative_prompt)
        self.content_layout.addWidget(self.copy_neg_prompt_btn)
        
        # Raw metadata toggle
        self.raw_toggle_btn = QPushButton("Show Raw Metadata")
        self.raw_toggle_btn.setCheckable(True)
        self.raw_toggle_btn.clicked.connect(self._toggle_raw_metadata)
        self.content_layout.addWidget(self.raw_toggle_btn)
        
        self.raw_metadata_text = QTextEdit()
        self.raw_metadata_text.setReadOnly(True)
        self.raw_metadata_text.setMaximumHeight(200)
        self.raw_metadata_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #888;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px;
                font-family: monospace;
                font-size: 10px;
            }
        """)
        self.raw_metadata_text.hide()
        self.content_layout.addWidget(self.raw_metadata_text)
        
        scroll.setWidget(self.content_widget)
        layout.addWidget(scroll)
        
        # Set style
        self.setStyleSheet("""
            MetadataPanel {
                background-color: #252525;
                color: #eee;
            }
            QLabel {
                color: #eee;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #5a5a5a;
            }
        """)
    
    def _add_section(self, title: str, fields: list):
        """Add a section with labeled fields."""
        # Section frame
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-radius: 6px;
                padding: 5px;
            }
        """)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setSpacing(5)
        
        # Section title
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setBold(True)
        title_label.setFont(title_font)
        frame_layout.addWidget(title_label)
        
        # Fields
        for label_text, attr_name in fields:
            row = QWidget()
            row_layout = QVBoxLayout(row)
            row_layout.setSpacing(2)
            row_layout.setContentsMargins(5, 0, 0, 0)
            
            label = QLabel(f"<b>{label_text}</b>")
            label.setStyleSheet("color: #aaa;")
            row_layout.addWidget(label)
            
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            value_label.setObjectName(f"value_{attr_name}")
            row_layout.addWidget(value_label)
            
            frame_layout.addWidget(row)
        
        self.content_layout.addWidget(frame)
    
    def set_metadata(self, metadata: ImageMetadata):
        """
        Display metadata for an image.
        
        Args:
            metadata: ImageMetadata object to display
        """
        self.current_metadata = metadata
        
        if not metadata:
            self._clear_display()
            return
        
        # Update file info
        self._set_value("file_name", metadata.file_name)
        self._set_value("dimensions", metadata.dimensions)
        self._set_value("file_size_str", self._format_file_size(metadata.file_size))
        self._set_value("source_str", metadata.source.upper() if metadata.source else "Unknown")
        
        # Update generation params
        self._set_value("model", metadata.model or "-")
        self._set_value("model_hash", metadata.model_hash or "-")
        self._set_value("sampler", metadata.sampler or "-")
        self._set_value("steps_str", str(metadata.steps) if metadata.steps else "-")
        self._set_value("cfg_str", str(metadata.cfg_scale) if metadata.cfg_scale else "-")
        self._set_value("seed_str", str(metadata.seed) if metadata.seed else "-")
        
        # Update prompts
        self.prompt_text.setText(metadata.prompt or "No prompt data")
        self.neg_prompt_text.setText(metadata.negative_prompt or "No negative prompt")
        
        # Update raw metadata
        self.raw_metadata_text.setText(metadata.raw_metadata or "No raw metadata available")
    
    def _set_value(self, attr_name: str, value: str):
        """Set the value label for a field."""
        label = self.content_widget.findChild(QLabel, f"value_{attr_name}")
        if label:
            label.setText(str(value))
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def _toggle_raw_metadata(self):
        """Toggle raw metadata visibility."""
        if self.raw_toggle_btn.isChecked():
            self.raw_metadata_text.show()
            self.raw_toggle_btn.setText("Hide Raw Metadata")
        else:
            self.raw_metadata_text.hide()
            self.raw_toggle_btn.setText("Show Raw Metadata")
    
    def _copy_prompt(self):
        """Copy prompt to clipboard."""
        if self.current_metadata and self.current_metadata.prompt:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_metadata.prompt)
    
    def _copy_negative_prompt(self):
        """Copy negative prompt to clipboard."""
        if self.current_metadata and self.current_metadata.negative_prompt:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.current_metadata.negative_prompt)
    
    def _clear_display(self):
        """Clear all displayed information."""
        for label in self.content_widget.findChildren(QLabel):
            if label.objectName().startswith("value_"):
                label.setText("-")
        
        self.prompt_text.clear()
        self.neg_prompt_text.clear()
        self.raw_metadata_text.clear()
