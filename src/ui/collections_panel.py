"""Collections panel for managing image collections."""
import os
from typing import List, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QMenu, QInputDialog,
    QAbstractItemView, QGridLayout, QScrollArea, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QIcon, QAction

from ..models.collection import CollectionsManager, Collection


class ClickableLabel(QLabel):
    """Label that emits clicked signal."""
    
    clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class CollectionGridItem(QFrame):
    """Custom widget for displaying a collection as a portrait thumbnail with name."""
    
    clicked = pyqtSignal(str)  # Emits collection name when clicked
    
    # Portrait thumbnail size (portrait aspect ratio)
    THUMBNAIL_WIDTH = 140
    THUMBNAIL_HEIGHT = 180
    
    def __init__(self, collection: Collection, parent=None):
        super().__init__(parent)
        self.collection = collection
        self._selected = False
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the item UI with portrait thumbnail and name underneath."""
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Thumbnail container (portrait shape)
        self.thumbnail_container = QLabel()
        self.thumbnail_container.setFixedSize(self.THUMBNAIL_WIDTH, self.THUMBNAIL_HEIGHT)
        self.thumbnail_container.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: 6px;
            }
        """)
        self.thumbnail_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_thumbnail()
        layout.addWidget(self.thumbnail_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Collection name (clickable for rename)
        self.name_label = ClickableLabel(self.collection.name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("""
            ClickableLabel {
                color: #eee;
                font-weight: bold;
                font-size: 12px;
                background-color: transparent;
            }
            ClickableLabel:hover {
                color: #4a9eff;
            }
        """)
        self.name_label.setFixedWidth(self.THUMBNAIL_WIDTH)
        self.name_label.setCursor(Qt.CursorShape.IBeamCursor)
        layout.addWidget(self.name_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.setStyleSheet("""
            CollectionGridItem {
                background-color: transparent;
                border-radius: 8px;
            }
            CollectionGridItem:hover {
                background-color: #2a2a2a;
            }
        """)
    
    def _load_thumbnail(self):
        """Load and display the collection thumbnail in portrait format, zoomed to fit."""
        if self.collection.thumbnail_path and os.path.exists(self.collection.thumbnail_path):
            pixmap = QPixmap(self.collection.thumbnail_path)
            if not pixmap.isNull():
                # Calculate scaling to fill the portrait container (zoom/crop to fit)
                target_width = self.THUMBNAIL_WIDTH - 8
                target_height = self.THUMBNAIL_HEIGHT - 8
                
                # Scale to fill the container, cropping if necessary
                scaled = pixmap.scaled(
                    target_width,
                    target_height,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # If the scaled image is larger than target, crop to center
                if scaled.width() > target_width or scaled.height() > target_height:
                    x = (scaled.width() - target_width) // 2
                    y = (scaled.height() - target_height) // 2
                    scaled = scaled.copy(x, y, target_width, target_height)
                
                self.thumbnail_container.setPixmap(scaled)
                self.thumbnail_container.setStyleSheet("""
                    QLabel {
                        background-color: #2a2a2a;
                        border: 2px solid #444;
                        border-radius: 6px;
                    }
                """)
            else:
                self._set_default_thumbnail()
        else:
            self._set_default_thumbnail()
    
    def _set_default_thumbnail(self):
        """Set the default folder icon thumbnail."""
        self.thumbnail_container.setText("📁")
        self.thumbnail_container.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border: 2px solid #444;
                border-radius: 6px;
                color: #666;
                font-size: 48px;
            }
        """)
    
    def set_selected(self, selected: bool):
        """Set the selected state of this item."""
        self._selected = selected
        if selected:
            self.setStyleSheet("""
                CollectionGridItem {
                    background-color: #3a3a3a;
                    border-radius: 8px;
                }
            """)
            self.thumbnail_container.setStyleSheet("""
                QLabel {
                    background-color: #2a2a2a;
                    border: 2px solid #4a9eff;
                    border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                CollectionGridItem {
                    background-color: transparent;
                    border-radius: 8px;
                }
                CollectionGridItem:hover {
                    background-color: #2a2a2a;
                }
            """)
            self._load_thumbnail()  # Reset thumbnail border
    
    def mousePressEvent(self, event):
        """Handle mouse press."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.collection.name)


class CollectionsPanel(QWidget):
    """Panel for managing image collections."""
    
    collection_selected = pyqtSignal(str, list, list)  # name, include_terms, exclude_terms
    apply_collection_filters = pyqtSignal(str, list, list, str, bool)  # name, include, exclude, sort_by, reverse
    set_thumbnail_requested = pyqtSignal(str)  # collection_name
    status_message = pyqtSignal(str)  # message for status bar
    switch_to_gallery = pyqtSignal()  # Request to switch to gallery tab
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.collections_manager = CollectionsManager()
        self.current_include_terms: List[str] = []
        self.current_exclude_terms: List[str] = []
        self.current_sort_by: str = 'date'
        self.current_reverse_sort: bool = False
        self._selected_collection_name: Optional[str] = None
        self._collection_items: dict = {}  # name -> CollectionGridItem
        self._setup_ui()
        self._refresh_collections_grid()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("📚 Collections")
        header.setStyleSheet("""
            QLabel {
                color: #eee;
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        layout.addWidget(header)
        
        # Description
        desc = QLabel("Click a collection to apply its filters. Right-click for more options.")
        desc.setWordWrap(True)
        desc.setStyleSheet("QLabel { color: #888; font-size: 11px; padding: 0 5px; }")
        layout.addWidget(desc)
        
        # Create from current filters button
        self.create_btn = QPushButton("➕ Save Current Filters")
        self.create_btn.setToolTip("Save the current filter settings as a collection")
        self.create_btn.clicked.connect(self._create_from_current_filters)
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #4a9eff;
                color: white;
                border: none;
                padding: 8px 15px;
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
        layout.addWidget(self.create_btn)
        
        # Scroll area for collections grid
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1a1a1a;
            }
        """)
        
        # Container widget for grid
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        scroll_area.setWidget(self.grid_container)
        layout.addWidget(scroll_area)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Rename button
        self.rename_btn = QPushButton("✏️ Rename")
        self.rename_btn.setToolTip("Rename the selected collection")
        self.rename_btn.clicked.connect(self._rename_selected_collection)
        self.rename_btn.setEnabled(False)
        self.rename_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4a9eff;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
        """)
        buttons_layout.addWidget(self.rename_btn)
        
        # Delete button
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.setToolTip("Delete the selected collection")
        self.delete_btn.clicked.connect(self._delete_selected_collection)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ff6b6b;
            }
            QPushButton:disabled {
                background-color: #2a2a2a;
                color: #666;
            }
        """)
        buttons_layout.addWidget(self.delete_btn)
        
        layout.addLayout(buttons_layout)
        
        # Set widget style
        self.setStyleSheet("""
            CollectionsPanel {
                background-color: #1a1a1a;
            }
        """)
    
    def update_current_filters(self, include_terms: List[str], exclude_terms: List[str], 
                               sort_by: str = 'date', reverse_sort: bool = False):
        """Update the current filter settings."""
        self.current_include_terms = include_terms
        self.current_exclude_terms = exclude_terms
        self.current_sort_by = sort_by
        self.current_reverse_sort = reverse_sort
    
    def _refresh_collections_grid(self):
        """Refresh the collections grid display."""
        # Clear existing items
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self._collection_items.clear()
        
        collections = self.collections_manager.get_all_collections()
        
        if not collections:
            # Show empty state
            empty_label = QLabel("No collections yet\n\nClick 'Save Current Filters' to create one")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("QLabel { color: #666; font-size: 14px; padding: 40px; }")
            self.grid_layout.addWidget(empty_label, 0, 0)
            return
        
        # Calculate number of columns based on width
        # Each item is ~156px wide (140 + margins), so we can fit multiple per row
        columns = 2  # Fixed 2 columns for consistent layout
        
        for i, collection in enumerate(collections):
            row = i // columns
            col = i % columns
            
            item_widget = CollectionGridItem(collection)
            item_widget.clicked.connect(self._on_collection_clicked)
            item_widget.name_label.clicked.connect(
                lambda name=collection.name: self._rename_collection_by_name(name)
            )
            item_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            item_widget.customContextMenuRequested.connect(
                lambda pos, name=collection.name: self._show_context_menu(pos, name)
            )
            
            self.grid_layout.addWidget(item_widget, row, col)
            self._collection_items[collection.name] = item_widget
    
    def _create_from_current_filters(self):
        """Create a new collection from current filter settings."""
        if not self.current_include_terms and not self.current_exclude_terms:
            self.status_message.emit("Set some filters first before creating a collection")
            return
        
        # Generate a default name based on filters
        if self.current_include_terms:
            default_name = self.current_include_terms[0][:20]
            if len(self.current_include_terms) > 1:
                default_name += f" +{len(self.current_include_terms)-1}"
        else:
            default_name = "Collection"
        
        # Find unique name
        base_name = default_name
        counter = 1
        while self.collections_manager.get_collection(default_name) is not None:
            default_name = f"{base_name} {counter}"
            counter += 1
        
        # Create collection directly without dialog
        collection = self.collections_manager.create_from_filters(
            name=default_name,
            include_terms=self.current_include_terms.copy(),
            exclude_terms=self.current_exclude_terms.copy(),
            sort_by=self.current_sort_by,
            reverse_sort=self.current_reverse_sort
        )
        
        if collection:
            self._refresh_collections_grid()
            self.status_message.emit(f"Collection '{default_name}' created")
        else:
            self.status_message.emit("Failed to create collection")
    
    def _on_collection_clicked(self, name: str):
        """Handle collection item click."""
        # Update selection visual
        for item_name, item_widget in self._collection_items.items():
            item_widget.set_selected(item_name == name)
        
        self._selected_collection_name = name
        self.delete_btn.setEnabled(True)
        self.rename_btn.setEnabled(True)
        
        # Get collection and apply filters immediately
        collection = self.collections_manager.get_collection(name)
        if collection:
            self.status_message.emit(f"Applied collection: {name}")
            self.apply_collection_filters.emit(
                collection.name,
                collection.include_terms,
                collection.exclude_terms,
                collection.sort_by,
                collection.reverse_sort
            )
            # Switch to gallery tab
            self.switch_to_gallery.emit()
    
    def _delete_selected_collection(self):
        """Delete the selected collection."""
        if not self._selected_collection_name:
            return
        
        name = self._selected_collection_name
        
        reply = QMessageBox.question(
            self,
            "Delete Collection",
            f"Are you sure you want to delete the collection '{name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.collections_manager.delete_collection(name):
                self._refresh_collections_grid()
                self._selected_collection_name = None
                self.delete_btn.setEnabled(False)
                self.rename_btn.setEnabled(False)
                self.status_message.emit(f"Collection '{name}' deleted")
    
    def _rename_selected_collection(self):
        """Rename the selected collection."""
        if not self._selected_collection_name:
            return
        
        old_name = self._selected_collection_name
        
        # Get new name from user
        new_name, ok = QInputDialog.getText(
            self,
            "Rename Collection",
            f"Enter new name for '{old_name}':",
            text=old_name
        )
        
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        
        new_name = new_name.strip()
        
        # Check if name already exists
        if self.collections_manager.get_collection(new_name) is not None:
            QMessageBox.warning(
                self,
                "Name Exists",
                f"A collection named '{new_name}' already exists.\n\nPlease choose a different name."
            )
            return
        
        # Rename collection
        if self.collections_manager.rename_collection(old_name, new_name):
            self._selected_collection_name = new_name
            self._refresh_collections_grid()
            # Reselect the renamed collection
            if new_name in self._collection_items:
                self._collection_items[new_name].set_selected(True)
            self.status_message.emit(f"Collection renamed to '{new_name}'")
        else:
            QMessageBox.warning(
                self,
                "Error",
                "Failed to rename collection. Please try again."
            )
    
    def _show_context_menu(self, position, collection_name: str):
        """Show context menu for collection item."""
        collection = self.collections_manager.get_collection(collection_name)
        if not collection:
            return
        
        menu = QMenu(self)
        
        # Apply action
        apply_action = QAction("Apply Filters", self)
        apply_action.triggered.connect(lambda: self._on_collection_clicked(collection_name))
        menu.addAction(apply_action)
        
        menu.addSeparator()
        
        # Set thumbnail action
        set_thumbnail_action = QAction("Set Thumbnail from Current Image", self)
        set_thumbnail_action.triggered.connect(lambda: self._set_thumbnail_from_current(collection_name))
        menu.addAction(set_thumbnail_action)
        
        menu.addSeparator()
        
        # Rename action
        rename_action = QAction("Rename Collection", self)
        rename_action.triggered.connect(lambda: self._rename_collection_by_name(collection_name))
        menu.addAction(rename_action)
        
        # Delete action
        delete_action = QAction("Delete Collection", self)
        delete_action.triggered.connect(lambda: self._delete_collection_by_name(collection_name))
        menu.addAction(delete_action)
        
        menu.exec(self._collection_items[collection_name].mapToGlobal(position))
    
    def _delete_collection_by_name(self, name: str):
        """Delete a collection by name."""
        reply = QMessageBox.question(
            self,
            "Delete Collection",
            f"Are you sure you want to delete the collection '{name}'?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.collections_manager.delete_collection(name):
                self._refresh_collections_grid()
                if self._selected_collection_name == name:
                    self._selected_collection_name = None
                    self.delete_btn.setEnabled(False)
                    self.rename_btn.setEnabled(False)
                self.status_message.emit(f"Collection '{name}' deleted")
    
    def _rename_collection_by_name(self, name: str):
        """Rename a collection by name (from context menu)."""
        # Set as selected first
        self._on_collection_clicked(name)
        # Then call rename
        self._rename_selected_collection()
    
    def _set_thumbnail_from_current(self, collection_name: str):
        """Set the collection thumbnail from the currently displayed image."""
        self.set_thumbnail_requested.emit(collection_name)
    
    def set_collection_thumbnail(self, collection_name: str, image_path: str):
        """Set the thumbnail for a collection."""
        if self.collections_manager.set_thumbnail(collection_name, image_path):
            self._refresh_collections_grid()
            self.status_message.emit(f"Thumbnail updated for '{collection_name}'")
