import os
import pandas as pd
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QFormLayout,
    QLineEdit, QToolButton, QHBoxLayout, QCheckBox, QSpinBox,
    QTabWidget, QPushButton, QFileDialog, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor

class PostPreviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        
        # Image preview
        self.image_label = QLabel("No image selected")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(300)
        self.image_label.setFrameShape(QFrame.StyledPanel)
        
        # Caption preview
        self.caption_preview = QTextEdit()
        self.caption_preview.setReadOnly(True)
        self.caption_preview.setMaximumHeight(150)
        
        layout.addWidget(QLabel("<b>Post Preview:</b>"))
        layout.addWidget(self.image_label)
        layout.addWidget(QLabel("Caption:"))
        layout.addWidget(self.caption_preview)
        
        self.setLayout(layout)
        
    def set_preview(self, image_path, caption):
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(pixmap)
                self.image_label.setText("")
            else:
                self.image_label.setText("Unable to load image")
                self.image_label.setPixmap(QPixmap())
        else:
            self.image_label.setText("Image not found")
            self.image_label.setPixmap(QPixmap())
            
        self.caption_preview.setText(caption)


class PostsTableWidget(QTableWidget):
    def __init__(self):
        super().__init__()
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Filename", "Caption", "Status", "Posted At"])
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        
    def load_data(self, csv_path, images_dir):
        self.clearContents()
        self.setRowCount(0)
        
        if not os.path.exists(csv_path):
            return False
            
        try:
            df = pd.read_csv(csv_path)
            if 'filename' not in df.columns or 'caption' not in df.columns:
                return False
                
            if 'posted' not in df.columns:
                df['posted'] = False
                
            if 'timestamp' not in df.columns:
                df['timestamp'] = ""
                
            self.setRowCount(len(df))
            
            for idx, row in df.iterrows():
                # Filename
                filename_item = QTableWidgetItem(row['filename'])
                
                # Check if image exists
                img_path = os.path.join(images_dir, row['filename'])
                if not os.path.exists(img_path):
                    filename_item.setForeground(QColor('red'))
                    filename_item.setToolTip("Image file not found")
                    
                self.setItem(idx, 0, filename_item)
                
                # Caption
                caption = row['caption']
                if len(caption) > 50:
                    display_caption = caption[:47] + "..."
                else:
                    display_caption = caption
                    
                caption_item = QTableWidgetItem(display_caption)
                caption_item.setToolTip(caption)
                self.setItem(idx, 1, caption_item)
                
                # Status
                status_item = QTableWidgetItem(
                    "Posted" if row.get('posted', False) else "Pending"
                )
                status_color = QColor('green') if row.get('posted', False) else QColor('blue')
                status_item.setForeground(status_color)
                self.setItem(idx, 2, status_item)
                
                # Timestamp
                self.setItem(idx, 3, QTableWidgetItem(str(row.get('timestamp', ''))))
                
            return True
            
        except Exception as e:
            print(f"Error loading CSV: {str(e)}")
            return False
            
    def refresh(self, csv_path, images_dir):
        self.load_data(csv_path, images_dir)


class SettingsWidget(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        
        layout = QVBoxLayout()
        
        # Create tabs for different settings categories
        tabs = QTabWidget()
        
        # General settings tab
        general_tab = QWidget()
        general_layout = QFormLayout()
        
        # Paths group
        paths_group = QGroupBox("File Paths")
        paths_layout = QFormLayout()
        
        self.session_dir = QLineEdit(self.settings.value("session_dir", "sessions"))
        self.browse_session_btn = QToolButton()
        self.browse_session_btn.setText("...")
        self.browse_session_btn.clicked.connect(lambda: self.browse_folder("session_dir"))
        
        self.log_dir = QLineEdit(self.settings.value("log_dir", "logs"))
        self.browse_log_btn = QToolButton()
        self.browse_log_btn.setText("...")
        self.browse_log_btn.clicked.connect(lambda: self.browse_folder("log_dir"))
        
        # Add path fields
        session_layout = QHBoxLayout()
        session_layout.addWidget(self.session_dir)
        session_layout.addWidget(self.browse_session_btn)
        
        log_layout = QHBoxLayout()
        log_layout.addWidget(self.log_dir)
        log_layout.addWidget(self.browse_log_btn)
        
        paths_layout.addRow("Session Directory:", session_layout)
        paths_layout.addRow("Log Directory:", log_layout)
        paths_group.setLayout(paths_layout)
        
        # Behavior group
        behavior_group = QGroupBox("Posting Behavior")
        behavior_layout = QFormLayout()
        
        self.hashtags_in_comment = QCheckBox("Put hashtags in first comment")
        self.hashtags_in_comment.setChecked(
            self.settings.value("hashtags_in_comment", "false") == "true"
        )
        
        self.repost_existing = QCheckBox("Allow reposting already posted images")
        self.repost_existing.setChecked(
            self.settings.value("repost_existing", "false") == "true"
        )
        
        behavior_layout.addRow(self.hashtags_in_comment)
        behavior_layout.addRow(self.repost_existing)
        behavior_group.setLayout(behavior_layout)
        
        # Layout for general tab
        general_layout.addWidget(paths_group)
        general_layout.addWidget(behavior_group)
        general_tab.setLayout(general_layout)
        
        # Delays tab
        delays_tab = QWidget()
        delays_layout = QFormLayout()
        
        # API delays
        api_group = QGroupBox("API Request Delays")
        api_layout = QFormLayout()
        
        self.api_min = QSpinBox()
        self.api_min.setRange(1, 60)
        self.api_min.setValue(int(self.settings.value("api_delay_min", 1)))
        self.api_min.setSuffix(" sec")
        
        self.api_max = QSpinBox()
        self.api_max.setRange(1, 60)
        self.api_max.setValue(int(self.settings.value("api_delay_max", 3)))
        self.api_max.setSuffix(" sec")
        
        api_layout.addRow("Minimum:", self.api_min)
        api_layout.addRow("Maximum:", self.api_max)
        api_group.setLayout(api_layout)
        
        # Post delays
        post_group = QGroupBox("Between Posts Delays")
        post_layout = QFormLayout()
        
        self.post_min = QSpinBox()
        self.post_min.setRange(0, 48)
        self.post_min.setSuffix(" hours")
        post_delay_min = int(self.settings.value("post_delay_min", 0)) // 3600
        self.post_min.setValue(post_delay_min)

        self.post_max = QSpinBox()
        self.post_max.setRange(0, 48)
        self.post_max.setSuffix(" hours")
        post_delay_max = int(self.settings.value("post_delay_max", 0)) // 3600
        self.post_max.setValue(post_delay_max)
        
        post_layout.addRow("Minimum:", self.post_min)
        post_layout.addRow("Maximum:", self.post_max)
        post_group.setLayout(post_layout)
        
        # Layout for delays tab
        delays_layout.addWidget(api_group)
        delays_layout.addWidget(post_group)
        delays_tab.setLayout(delays_layout)
        
        # Add tabs to tab widget
        tabs.addTab(general_tab, "General")
        tabs.addTab(delays_tab, "Delays")
        
        # Add tab widget to main layout
        layout.addWidget(tabs)
        
        # Add save button
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_settings)
        layout.addWidget(self.save_btn)
        
        self.setLayout(layout)
    
    def browse_folder(self, setting_name):
        sender = getattr(self, setting_name)
        current = sender.text()
        
        folder = QFileDialog.getExistingDirectory(
            self, f"Select {setting_name.replace('_', ' ').title()}", 
            current or os.path.expanduser("~")
        )
        
        if folder:
            sender.setText(folder)
    
    def save_settings(self):
        # Save path settings
        self.settings.setValue("session_dir", self.session_dir.text())
        self.settings.setValue("log_dir", self.log_dir.text())
        
        # Save behavior settings
        self.settings.setValue("hashtags_in_comment", 
                              "true" if self.hashtags_in_comment.isChecked() else "false")
        self.settings.setValue("repost_existing", 
                              "true" if self.repost_existing.isChecked() else "false")
        
        # Save delay settings
        self.settings.setValue("api_delay_min", self.api_min.value())
        self.settings.setValue("api_delay_max", self.api_max.value())
        self.settings.setValue("post_delay_min", self.post_min.value() * 3600)
        self.settings.setValue("post_delay_max", self.post_max.value() * 3600)
        
        self.settings.sync()
        
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved.")
