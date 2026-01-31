"""Filesystem browser widget for navigating directories and files."""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeView,
    QLineEdit, QPushButton, QHBoxLayout, QLabel, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QDir, QModelIndex
from PyQt6.QtGui import QFileSystemModel, QIcon


class FilesystemBrowser(QWidget):
    """Filesystem browser with tree view."""
    
    folder_selected = pyqtSignal(str, bool)  # Emits (folder_path, include_subfolders) when selected
    file_selected = pyqtSignal(str)  # Emits file path when selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Path navigation bar
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(5)
        
        # Home button
        self.home_btn = QPushButton("🏠")
        self.home_btn.setToolTip("Go to home directory")
        self.home_btn.setFixedWidth(40)
        self.home_btn.clicked.connect(self._go_home)
        self.home_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        nav_layout.addWidget(self.home_btn)
        
        # Up directory button
        self.up_btn = QPushButton("⬆")
        self.up_btn.setToolTip("Go up one directory")
        self.up_btn.setFixedWidth(40)
        self.up_btn.clicked.connect(self._go_up)
        self.up_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        nav_layout.addWidget(self.up_btn)
        
        # Path input
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter path...")
        self.path_input.returnPressed.connect(self._navigate_to_path)
        nav_layout.addWidget(self.path_input)
        
        # Go button
        self.go_btn = QPushButton("Go")
        self.go_btn.clicked.connect(self._navigate_to_path)
        self.go_btn.setFixedWidth(50)
        self.go_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        nav_layout.addWidget(self.go_btn)
        
        layout.addLayout(nav_layout)
        
        # Subfolder toggle
        toggle_layout = QHBoxLayout()
        toggle_layout.setSpacing(5)
        
        self.include_subfolders_checkbox = QCheckBox("Include subfolders")
        self.include_subfolders_checkbox.setChecked(True)
        self.include_subfolders_checkbox.setToolTip("When checked, loads images from all subdirectories")
        self.include_subfolders_checkbox.setStyleSheet("""
            QCheckBox {
                color: #eee;
                spacing: 5px;
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
        toggle_layout.addWidget(self.include_subfolders_checkbox)
        
        # Load button
        self.load_btn = QPushButton("📂 Load Folder")
        self.load_btn.setToolTip("Load images from the currently selected folder")
        self.load_btn.clicked.connect(self._load_current_folder)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
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
        toggle_layout.addWidget(self.load_btn)
        
        toggle_layout.addStretch()
        layout.addLayout(toggle_layout)
        
        # File system model and tree view
        self.model = QFileSystemModel()
        self.model.setRootPath("")
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        
        # Set name filters for image files
        self.model.setNameFilters(["*.png", "*.jpg", "*.jpeg", "*.PNG", "*.JPG", "*.JPEG"])
        self.model.setNameFilterDisables(False)  # Hide non-matching files
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.model)
        self.tree_view.setAnimated(True)
        self.tree_view.setIndentation(20)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        
        # Hide size, type, and date columns - only show name
        self.tree_view.setColumnWidth(0, 250)
        for i in range(1, self.model.columnCount()):
            self.tree_view.hideColumn(i)
        
        # Connect signals
        self.tree_view.clicked.connect(self._on_item_clicked)
        self.tree_view.doubleClicked.connect(self._on_item_double_clicked)
        
        layout.addWidget(self.tree_view)
        
        # Info label
        self.info_label = QLabel("Click folder to load, double-click to expand")
        self.info_label.setStyleSheet("color: #888; font-size: 10px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        
        # Set initial path to home directory
        home_path = str(Path.home())
        self.set_root_path(home_path)
        
        # Style
        self.setStyleSheet("""
            QTreeView {
                background-color: #1a1a1a;
                color: #eee;
                border: 1px solid #333;
                selection-background-color: #4a9eff;
            }
            QTreeView::item:hover {
                background-color: #2a2a2a;
            }
            QLineEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
        """)
    
    def set_root_path(self, path: str):
        """Set the root path for the tree view."""
        if os.path.exists(path):
            index = self.model.index(path)
            self.tree_view.setRootIndex(index)
            self.path_input.setText(path)
    
    def _go_home(self):
        """Navigate to home directory."""
        home_path = str(Path.home())
        self.set_root_path(home_path)
    
    def _go_up(self):
        """Navigate up one directory."""
        current_path = self.path_input.text().strip()
        if current_path:
            parent_path = str(Path(current_path).parent)
            if parent_path != current_path:  # Not at root
                self.set_root_path(parent_path)
    
    def _navigate_to_path(self):
        """Navigate to the path entered in the input."""
        path = self.path_input.text().strip()
        if path and os.path.exists(path):
            self.set_root_path(path)
        else:
            self.info_label.setText("Invalid path")
            self.info_label.setStyleSheet("color: #ff6b6b; font-size: 10px;")
    
    def _on_item_clicked(self, index: QModelIndex):
        """Handle single click on item."""
        file_path = self.model.filePath(index)
        
        if os.path.isdir(file_path):
            # Update path input
            self.path_input.setText(file_path)
            # Just update the path, don't emit folder_selected yet
            # User needs to click "Load Folder" button
            self.info_label.setText(f"Selected: {os.path.basename(file_path)} (click Load Folder to view)")
            self.info_label.setStyleSheet("color: #4a9eff; font-size: 10px;")
        elif os.path.isfile(file_path):
            # Emit file selected signal
            self.file_selected.emit(file_path)
            self.info_label.setText(f"Selected: {os.path.basename(file_path)}")
            self.info_label.setStyleSheet("color: #4a9eff; font-size: 10px;")
    
    def _load_current_folder(self):
        """Load the currently selected folder."""
        folder_path = self.path_input.text().strip()
        if folder_path and os.path.isdir(folder_path):
            include_subfolders = self.include_subfolders_checkbox.isChecked()
            self.folder_selected.emit(folder_path, include_subfolders)
            self.info_label.setText(f"Loading: {os.path.basename(folder_path)} {'(with subfolders)' if include_subfolders else '(current folder only)'}")
            self.info_label.setStyleSheet("color: #4caf50; font-size: 10px;")
    
    def _on_item_double_clicked(self, index: QModelIndex):
        """Handle double click on item."""
        file_path = self.model.filePath(index)
        
        if os.path.isdir(file_path):
            # Navigate into directory
            self.set_root_path(file_path)
            # Also emit folder selected with current subfolder setting
            include_subfolders = self.include_subfolders_checkbox.isChecked()
            self.folder_selected.emit(file_path, include_subfolders)
