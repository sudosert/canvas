"""Settings dialog for application configuration."""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QListWidget, QListWidgetItem, QMessageBox,
    QCheckBox
)
from PyQt6.QtCore import Qt, QSettings

try:
    import psycopg2
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False


class SettingsDialog(QDialog):
    """Dialog for application settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(600, 400)
        
        self.settings = QSettings("SDImageViewer", "Settings")
        self._setup_ui()
        self._load_settings()
    
    def _setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # ComfyUI Prompt Node Configuration
        comfy_group = QGroupBox("ComfyUI Prompt Extraction")
        comfy_layout = QVBoxLayout(comfy_group)
        
        info_label = QLabel(
            "Specify node ID or title to search for prompts in ComfyUI workflows.\n"
            "Node ID takes precedence over title. If ID is set, title is ignored."
        )
        info_label.setWordWrap(True)
        comfy_layout.addWidget(info_label)
        
        # Primary node ID
        primary_id_layout = QHBoxLayout()
        primary_id_layout.addWidget(QLabel("Primary Node ID:"))
        self.primary_node_id_input = QLineEdit()
        self.primary_node_id_input.setPlaceholderText("e.g., 15 (optional, supersedes title)")
        primary_id_layout.addWidget(self.primary_node_id_input)
        comfy_layout.addLayout(primary_id_layout)
        
        # Primary node title
        primary_layout = QHBoxLayout()
        primary_layout.addWidget(QLabel("Primary Node Title:"))
        self.primary_node_input = QLineEdit()
        self.primary_node_input.setPlaceholderText("e.g., Full Prompt")
        primary_layout.addWidget(self.primary_node_input)
        comfy_layout.addLayout(primary_layout)
        
        # Alternative nodes list
        comfy_layout.addWidget(QLabel("Alternative Node Titles (fallback):"))
        
        self.alt_nodes_list = QListWidget()
        self.alt_nodes_list.setMaximumHeight(150)
        comfy_layout.addWidget(self.alt_nodes_list)
        
        # Add/Remove buttons for alternatives
        alt_btn_layout = QHBoxLayout()
        self.alt_node_input = QLineEdit()
        self.alt_node_input.setPlaceholderText("Enter alternative node title...")
        alt_btn_layout.addWidget(self.alt_node_input)
        
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_alt_node)
        alt_btn_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_alt_node)
        alt_btn_layout.addWidget(remove_btn)
        
        comfy_layout.addLayout(alt_btn_layout)
        
        layout.addWidget(comfy_group)
        
        # PostgreSQL Configuration
        postgres_group = QGroupBox("PostgreSQL Database")
        postgres_layout = QVBoxLayout(postgres_group)
        
        if not POSTGRES_AVAILABLE:
            warning_label = QLabel(
                "⚠️ psycopg2 is not installed. Install with: pip install psycopg2-binary"
            )
            warning_label.setStyleSheet("color: #ff6b6b;")
            postgres_layout.addWidget(warning_label)
        
        # Enable PostgreSQL checkbox
        self.postgres_enabled = QCheckBox("Enable PostgreSQL Storage")
        self.postgres_enabled.setChecked(False)
        self.postgres_enabled.stateChanged.connect(self._on_postgres_enabled_changed)
        postgres_layout.addWidget(self.postgres_enabled)
        
        # Connection details layout
        conn_details_layout = QVBoxLayout()
        
        # Host (from env var POSTGRES_IP)
        host_layout = QHBoxLayout()
        host_layout.addWidget(QLabel("Host:"))
        self.postgres_host = QLineEdit()
        self.postgres_host.setPlaceholderText("e.g., 192.168.1.100 (or $POSTGRES_IP)")
        host_layout.addWidget(self.postgres_host)
        postgres_layout.addLayout(host_layout)
        
        # Port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.postgres_port = QLineEdit()
        self.postgres_port.setText("5432")
        port_layout.addWidget(self.postgres_port)
        postgres_layout.addLayout(port_layout)
        
        # Database
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database:"))
        self.postgres_db = QLineEdit()
        self.postgres_db.setPlaceholderText("e.g., sd_images")
        db_layout.addWidget(self.postgres_db)
        postgres_layout.addLayout(db_layout)
        
        # Username (from env var POSTGRES_USER)
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("Username:"))
        self.postgres_user = QLineEdit()
        self.postgres_user.setPlaceholderText("or $POSTGRES_USER")
        user_layout.addWidget(self.postgres_user)
        postgres_layout.addLayout(user_layout)
        
        # Password (from env var POSTGRES_PASS)
        pass_layout = QHBoxLayout()
        pass_layout.addWidget(QLabel("Password:"))
        self.postgres_pass = QLineEdit()
        self.postgres_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.postgres_pass.setPlaceholderText("or $POSTGRES_PASS")
        pass_layout.addWidget(self.postgres_pass)
        postgres_layout.addLayout(pass_layout)
        
        # Test connection button
        test_btn_layout = QHBoxLayout()
        test_btn_layout.addStretch()
        self.test_conn_btn = QPushButton("Test Connection")
        self.test_conn_btn.clicked.connect(self._test_postgres_connection)
        self.test_conn_btn.setEnabled(False)
        test_btn_layout.addWidget(self.test_conn_btn)
        postgres_layout.addLayout(test_btn_layout)
        
        # Connection info label
        info_label = QLabel(
            "Environment variables POSTGRES_IP, POSTGRES_USER, and POSTGRES_PASS "
            "will be used if fields are left empty."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        postgres_layout.addWidget(info_label)
        
        # Connection status
        self.postgres_status = QLabel("Status: Not configured")
        self.postgres_status.setStyleSheet("color: #888;")
        postgres_layout.addWidget(self.postgres_status)
        
        layout.addWidget(postgres_group)
        
        layout.addStretch()
        
        # Dialog buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save_settings)
        save_btn.setDefault(True)
        btn_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # Style
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #eee;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QLineEdit {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget {
                background-color: #2a2a2a;
                color: #eee;
                border: 1px solid #444;
            }
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
            QPushButton:default {
                background-color: #4a9eff;
                border: 1px solid #4a9eff;
            }
            QPushButton:default:hover {
                background-color: #5aa9ff;
            }
        """)
    
    def _load_settings(self):
        """Load settings from QSettings."""
        # Load primary node ID (optional, supersedes title)
        primary_id = self.settings.value("comfyui_primary_node_id", "")
        self.primary_node_id_input.setText(primary_id)
        
        # Load primary node title
        primary = self.settings.value("comfyui_primary_node", "Full Prompt")
        self.primary_node_input.setText(primary)
        
        # Load alternative nodes
        alt_nodes = self.settings.value("comfyui_alt_nodes", [])
        if alt_nodes is None:
            alt_nodes = []
        if isinstance(alt_nodes, str):
            alt_nodes = [alt_nodes] if alt_nodes else []
        
        for node in alt_nodes:
            self.alt_nodes_list.addItem(node)
        
        # Load PostgreSQL settings
        postgres_enabled = self.settings.value("postgres_enabled", False)
        if isinstance(postgres_enabled, str):
            postgres_enabled = postgres_enabled.lower() == "true"
        self.postgres_enabled.setChecked(postgres_enabled)
        
        # Load connection details (use env vars as defaults)
        self.postgres_host.setText(self.settings.value("postgres_host", os.environ.get("POSTGRES_IP", "")))
        self.postgres_port.setText(self.settings.value("postgres_port", "5432"))
        self.postgres_db.setText(self.settings.value("postgres_db", "sd_images"))
        self.postgres_user.setText(self.settings.value("postgres_user", os.environ.get("POSTGRES_USER", "")))
        # Password not loaded - use env var
        
        self._update_postgres_status()
    
    def _add_alt_node(self):
        """Add an alternative node to the list."""
        node_title = self.alt_node_input.text().strip()
        if node_title:
            self.alt_nodes_list.addItem(node_title)
            self.alt_node_input.clear()
    
    def _remove_alt_node(self):
        """Remove selected alternative node from the list."""
        current_item = self.alt_nodes_list.currentItem()
        if current_item:
            self.alt_nodes_list.takeItem(self.alt_nodes_list.row(current_item))
    
    def _on_postgres_enabled_changed(self, state):
        """Handle PostgreSQL enabled checkbox change."""
        enabled = state == Qt.CheckState.Checked.value
        self.postgres_host.setEnabled(enabled)
        self.postgres_port.setEnabled(enabled)
        self.postgres_db.setEnabled(enabled)
        self.postgres_user.setEnabled(enabled)
        self.postgres_pass.setEnabled(enabled)
        self.test_conn_btn.setEnabled(enabled and POSTGRES_AVAILABLE)
    
    def _get_postgres_connection_string(self) -> str:
        """Build connection string from fields or environment variables."""
        # Get values from fields or environment variables
        host = self.postgres_host.text().strip() or os.environ.get("POSTGRES_IP", "")
        port = self.postgres_port.text().strip() or "5432"
        database = self.postgres_db.text().strip() or "sd_images"
        user = self.postgres_user.text().strip() or os.environ.get("POSTGRES_USER", "")
        password = self.postgres_pass.text().strip() or os.environ.get("POSTGRES_PASS", "")
        
        if not all([host, user, password]):
            return ""
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    def _test_postgres_connection(self):
        """Test the PostgreSQL connection."""
        if not POSTGRES_AVAILABLE:
            QMessageBox.warning(
                self,
                "PostgreSQL Not Available",
                "psycopg2 is not installed. Install with: pip install psycopg2-binary"
            )
            return
        
        conn_string = self._get_postgres_connection_string()
        if not conn_string:
            QMessageBox.warning(
                self,
                "Missing Connection Details",
                "Please enter PostgreSQL connection details or set environment variables."
            )
            return
        
        try:
            conn = psycopg2.connect(conn_string, connect_timeout=5)
            conn.close()
            self.postgres_status.setText("Status: ✅ Connected successfully")
            self.postgres_status.setStyleSheet("color: #4caf50;")
            QMessageBox.information(
                self,
                "Connection Successful",
                "Successfully connected to PostgreSQL database!"
            )
        except Exception as e:
            self.postgres_status.setText(f"Status: ❌ Connection failed")
            self.postgres_status.setStyleSheet("color: #ff6b6b;")
            QMessageBox.critical(
                self,
                "Connection Failed",
                f"Failed to connect to PostgreSQL:\n{str(e)}"
            )
    
    def _update_postgres_status(self):
        """Update the PostgreSQL status label."""
        if not POSTGRES_AVAILABLE:
            self.postgres_status.setText("Status: ⚠️ psycopg2 not installed")
            self.postgres_status.setStyleSheet("color: #ff9800;")
        elif not self.postgres_enabled.isChecked():
            self.postgres_status.setText("Status: Disabled")
            self.postgres_status.setStyleSheet("color: #888;")
        else:
            # Check if we have enough info to connect
            conn_string = self._get_postgres_connection_string()
            if not conn_string:
                self.postgres_status.setText("Status: Not configured (need host, user, password)")
                self.postgres_status.setStyleSheet("color: #888;")
            else:
                self.postgres_status.setText("Status: Configured (not tested)")
                self.postgres_status.setStyleSheet("color: #2196f3;")
    
    def _save_settings(self):
        """Save settings to QSettings."""
        # Save primary node ID (optional)
        primary_id = self.primary_node_id_input.text().strip()
        self.settings.setValue("comfyui_primary_node_id", primary_id)
        
        # Save primary node title
        primary = self.primary_node_input.text().strip()
        if not primary:
            QMessageBox.warning(
                self,
                "Invalid Settings",
                "Primary node title cannot be empty."
            )
            return
        
        self.settings.setValue("comfyui_primary_node", primary)
        
        # Save alternative nodes
        alt_nodes = []
        for i in range(self.alt_nodes_list.count()):
            alt_nodes.append(self.alt_nodes_list.item(i).text())
        
        self.settings.setValue("comfyui_alt_nodes", alt_nodes)
        
        # Save PostgreSQL settings
        self.settings.setValue("postgres_enabled", self.postgres_enabled.isChecked())
        self.settings.setValue("postgres_host", self.postgres_host.text().strip())
        self.settings.setValue("postgres_port", self.postgres_port.text().strip())
        self.settings.setValue("postgres_db", self.postgres_db.text().strip())
        self.settings.setValue("postgres_user", self.postgres_user.text().strip())
        # Don't save password for security - rely on env var
        
        self.accept()
