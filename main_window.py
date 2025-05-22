import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QFileDialog, QTextEdit,
    QFormLayout, QMessageBox, QGroupBox, QTabWidget, QProgressBar, QToolButton, QSystemTrayIcon,
    QMenu, QAction, QApplication
)
from PyQt5.QtCore import (
    QSettings
)
from PyQt5.QtGui import (
    QTextCursor
)
from worker import InstagramWorker
from dialogs import AuthDialog
from widgets import PostPreviewWidget, PostsTableWidget, SettingsWidget

class InstagramAutoPostApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Instagram Auto Poster Pro")
        self.setGeometry(100, 100, 1000, 700)
        self.worker = None
        
        # Load QSettings
        self.settings = QSettings("InstagramAutoPoster", "ProApp")
        
        # Set up system tray icon
        self.setup_tray_icon()
        
        # Initialize UI
        self.init_ui()
        
        # Initialize with default values
        self.load_settings()
        
        # Ensure directories exist
        self.ensure_directories()

    def setup_tray_icon(self):
        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QApplication.style().standardIcon(
            QApplication.style().SP_DialogApplyButton))
        
        # Create tray menu
        tray_menu = QMenu()
        show_action = QAction("Show", self)
        quit_action = QAction("Exit", self)
        pause_action = QAction("Pause/Resume", self)
        
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(self.quit_app)
        pause_action.triggered.connect(self.toggle_pause)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(pause_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Show the tray icon
        self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()
    
    def quit_app(self):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Confirm Exit", 
                "A posting task is currently running. Quitting will stop the task. Continue?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                if self.worker:
                    self.worker.stop()
                QApplication.quit()
        else:
            QApplication.quit()
    
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self, "Minimize to Tray", 
                "A posting task is running. Do you want to minimize to system tray?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                event.ignore()
                self.hide()
                self.tray_icon.showMessage(
                    "Instagram Auto Poster", 
                    "Application is still running in the background",
                    QSystemTrayIcon.Information, 
                    2000
                )
            elif reply == QMessageBox.Cancel:
                event.ignore()
            else:
                if self.worker:
                    self.worker.stop()
                event.accept()
        else:
            event.accept()
    
    def toggle_pause(self):
        if not self.worker or not self.worker.isRunning():
            return
            
        if self.worker.paused:
            self.worker.resume()
            self.pause_btn.setText("Pause")
            self.tray_icon.showMessage(
                "Instagram Auto Poster", 
                "Posting task resumed",
                QSystemTrayIcon.Information, 
                2000
            )
        else:
            self.worker.pause()
            self.pause_btn.setText("Resume")
            self.tray_icon.showMessage(
                "Instagram Auto Poster", 
                "Posting task paused",
                QSystemTrayIcon.Information, 
                2000
            )

    def ensure_directories(self):
        # Create necessary directories
        for directory in [
            self.settings.value("session_dir", "sessions"),
            self.settings.value("log_dir", "logs")
        ]:
            os.makedirs(directory, exist_ok=True)

    def init_ui(self):
        self.create_menu_bar()
        
        main = QWidget()
        layout = QVBoxLayout()
        
        # Tabs for different sections
        self.tabs = QTabWidget()
        
        # Post Setup Tab
        post_tab = QWidget()
        post_layout = QVBoxLayout()
        
        # Instagram credentials
        credentials_group = QGroupBox("Instagram Account")
        cred_layout = QFormLayout()
        
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        
        cred_layout.addRow("Username:", self.username)
        cred_layout.addRow("Password:", self.password)
        credentials_group.setLayout(cred_layout)
        
        # Files and folders
        files_group = QGroupBox("Post Content")
        files_layout = QFormLayout()
        
        # CSV file selection
        csv_layout = QHBoxLayout()
        self.csv_path = QLineEdit()
        self.browse_csv_btn = QToolButton()
        self.browse_csv_btn.setText("...")
        self.browse_csv_btn.clicked.connect(self.browse_csv)
        csv_layout.addWidget(self.csv_path)
        csv_layout.addWidget(self.browse_csv_btn)
        
        # Images directory selection
        img_layout = QHBoxLayout()
        self.img_dir = QLineEdit()
        self.browse_img_btn = QToolButton()
        self.browse_img_btn.setText("...")
        self.browse_img_btn.clicked.connect(self.browse_img_dir)
        img_layout.addWidget(self.img_dir)
        img_layout.addWidget(self.browse_img_btn)
        
        # Session file
        session_layout = QHBoxLayout()
        self.session_file = QLineEdit()
        self.browse_session_file_btn = QToolButton()
        self.browse_session_file_btn.setText("...")
        self.browse_session_file_btn.clicked.connect(self.browse_session_file)
        session_layout.addWidget(self.session_file)
        session_layout.addWidget(self.browse_session_file_btn)
        
        files_layout.addRow("CSV File:", csv_layout)
        files_layout.addRow("Image Folder:", img_layout)
        files_layout.addRow("Session File:", session_layout)
        
        # Add a refresh button for CSV
        self.refresh_csv_btn = QPushButton("Refresh CSV Preview")
        self.refresh_csv_btn.clicked.connect(self.refresh_posts_table)
        files_layout.addRow("", self.refresh_csv_btn)
        
        files_group.setLayout(files_layout)
        
        # Timing configuration
        timing_group = QGroupBox("Posting Schedule")
        timing_layout = QFormLayout()
        
        self.api_min = QSpinBox()
        self.api_min.setRange(1, 60)
        self.api_min.setSuffix(" sec")
        
        self.api_max = QSpinBox()
        self.api_max.setRange(1, 60) 
        self.api_max.setSuffix(" sec")
        
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
        
        timing_layout.addRow("API Delay Min:", self.api_min)
        timing_layout.addRow("API Delay Max:", self.api_max)
        timing_layout.addRow("Post Delay Min:", self.post_min)
        timing_layout.addRow("Post Delay Max:", self.post_max)
        timing_group.setLayout(timing_layout)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("Start Posting")
        self.stop_btn = QPushButton("Stop")
        self.pause_btn = QPushButton("Pause")
        
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_btn)
        control_layout.addWidget(self.pause_btn)
        control_layout.addWidget(self.stop_btn)
        
        self.start_btn.clicked.connect(self.start_worker)
        self.stop_btn.clicked.connect(self.stop_worker)
        self.pause_btn.clicked.connect(self.toggle_pause)
        
        # Add a progress section
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.status_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_group.setLayout(progress_layout)
        
        # Combine all elements in the post tab
        left_column = QVBoxLayout()
        left_column.addWidget(credentials_group)
        left_column.addWidget(files_group)
        left_column.addWidget(timing_group)
        left_column.addLayout(control_layout)
        left_column.addWidget(progress_group)
        left_column.addStretch()
        
        # Create the posts table for preview
        right_column = QVBoxLayout()
        self.posts_table = PostsTableWidget()
        right_column.addWidget(QLabel("<b>Posts from CSV:</b>"))
        right_column.addWidget(self.posts_table)
        
        # Add post preview
        self.preview_widget = PostPreviewWidget()
        right_column.addWidget(self.preview_widget)
        
        # Split the layout
        post_split = QHBoxLayout()
        post_split.addLayout(left_column, 40)
        post_split.addLayout(right_column, 60)
        
        post_layout.addLayout(post_split)
        post_tab.setLayout(post_layout)
        
        # Logs Tab
        logs_tab = QWidget()
        logs_layout = QVBoxLayout()
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setLineWrapMode(QTextEdit.NoWrap)
        self.log_output.setStyleSheet("font-family: monospace;")
        
        log_controls = QHBoxLayout()
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.save_log_btn = QPushButton("Save Log")
        self.save_log_btn.clicked.connect(self.save_log)
        
        log_controls.addWidget(self.clear_log_btn)
        log_controls.addWidget(self.save_log_btn)
        log_controls.addStretch()
        
        logs_layout.addWidget(QLabel("<b>Activity Log:</b>"))
        logs_layout.addWidget(self.log_output)
        logs_layout.addLayout(log_controls)
        logs_tab.setLayout(logs_layout)
        
        # Settings Tab
        self.settings_widget = SettingsWidget(self.settings)
        
        # Add all tabs
        self.tabs.addTab(post_tab, "Post Setup")
        self.tabs.addTab(logs_tab, "Logs")
        self.tabs.addTab(self.settings_widget, "Settings")
        
        layout.addWidget(self.tabs)
        main.setLayout(layout)
        self.setCentralWidget(main)
        
    def create_menu_bar(self):
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu("File")
        
        new_csv_action = QAction("Create New CSV", self)
        new_csv_action.triggered.connect(self.create_new_csv)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.quit_app)
        
        file_menu.addAction(new_csv_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        
        help_menu.addAction(about_action)
        
    def load_settings(self):

        # Clear username and password fields
        self.username.clear()
        self.password.clear()
        # Load saved values
        self.csv_path.setText(self.settings.value("csv_path", "posts.csv"))
        self.img_dir.setText(self.settings.value("images_dir", "images"))
        
        # Set default session filename
        default_session = os.path.join(
            self.settings.value("session_dir", "sessions"),
            "instagram_session.json"
        )
        self.session_file.setText(self.settings.value("session_file", default_session))
        
        # Set timing values
        self.api_min.setValue(int(self.settings.value("api_delay_min", 1)))
        self.api_max.setValue(int(self.settings.value("api_delay_max", 3)))
        post_delay_min = int(self.settings.value("post_delay_min", 0)) // 3600
        self.post_min.setValue(post_delay_min)

        post_delay_max = int(self.settings.value("post_delay_max", 0)) // 3600
        self.post_max.setValue(post_delay_max)
        
        # Load CSV preview if possible
        self.refresh_posts_table()
        
    def save_current_settings(self):
        # Save current values
        self.settings.setValue("username", self.username.text())
        self.settings.setValue("password", self.password.text())
        self.settings.setValue("csv_path", self.csv_path.text())
        self.settings.setValue("images_dir", self.img_dir.text())
        self.settings.setValue("session_file", self.session_file.text())
        
        # Save timing values
        self.settings.setValue("api_delay_min", self.api_min.value())
        self.settings.setValue("api_delay_max", self.api_max.value())
        self.settings.setValue("post_delay_min", self.post_min.value() * 3600)
        self.settings.setValue("post_delay_max", self.post_max.value() * 3600)
        
        self.settings.sync()
        
    def browse_csv(self):
        current = self.csv_path.text()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", os.path.dirname(current) or os.getcwd(),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            self.csv_path.setText(file_path)
            self.refresh_posts_table()
            
    def browse_img_dir(self):
        current = self.img_dir.text()
        folder = QFileDialog.getExistingDirectory(
            self, "Select Images Folder", current or os.getcwd()
        )
        
        if folder:
            self.img_dir.setText(folder)
            self.refresh_posts_table()
            
    def browse_session_file(self):
        current = self.session_file.text()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Session File", os.path.dirname(current) or os.getcwd(),
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self.session_file.setText(file_path)
            
    def refresh_posts_table(self):
        csv_path = self.csv_path.text()
        img_dir = self.img_dir.text()
        
        if os.path.exists(csv_path):
            self.posts_table.load_data(csv_path, img_dir)
        
    def create_new_csv(self):
        # Ask for file location
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Create New CSV File", os.getcwd(),
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            # Create a template CSV
            df = pd.DataFrame({
                'filename': ['image1.jpg', 'image2.jpg'],
                'caption': ['Your caption for post 1 #hashtag1 #hashtag2', 
                           'Your caption for post 2 #awesome #instagram'],
                'posted': [False, False],
                'timestamp': ['', '']
            })
            
            df.to_csv(file_path, index=False)
            
            # Ask if user wants to use this CSV
            reply = QMessageBox.question(
                self, "New CSV Created", 
                f"CSV template created at {file_path}. Would you like to use this file now?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.csv_path.setText(file_path)
                self.refresh_posts_table()
                
            self.log(f"Created new CSV template: {file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create CSV file: {str(e)}")
            
    def get_config(self):
        # Create configuration dictionary for the worker
        config = {
            'username': self.username.text(),
            'password': self.password.text(),
            'session_file': self.session_file.text(),
            'csv_path': self.csv_path.text(),
            'images_dir': self.img_dir.text(),
            'api_delay_min': self.api_min.value(),
            'api_delay_max': self.api_max.value(),
            'post_delay_min': self.post_min.value(),
            'post_delay_max': self.post_max.value(),
            'log_dir': self.settings.value("log_dir", "logs"),
            'hashtags_in_first_comment': self.settings.value("hashtags_in_comment", "false") == "true",
            'repost_existing': self.settings.value("repost_existing", "false") == "true"
        }
        return config
        
    def start_worker(self):
        # Validate inputs
        if not self.username.text() or not self.password.text():
            QMessageBox.critical(self, "Invalid Input", "Username and password are required")
            return
            
        config = self.get_config()
        
        # Check CSV and images directory
        if not os.path.exists(config['csv_path']):
            QMessageBox.critical(self, "Invalid Input", "CSV file not found")
            return
            
        if not os.path.exists(config['images_dir']) or not os.path.isdir(config['images_dir']):
            # Ask if we should create the directory
            reply = QMessageBox.question(
                self, "Create Directory", 
                f"Images directory does not exist. Create {config['images_dir']}?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                try:
                    os.makedirs(config['images_dir'], exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not create directory: {str(e)}")
                    return
            else:
                return
        
        # Save current settings
        self.save_current_settings()
        
        # Create and start worker
        self.worker = InstagramWorker(config)
        self.worker.update_log.connect(self.log)
        self.worker.update_status.connect(self.update_status)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.worker_done)
        self.worker.require_2fa.connect(self.show_2fa)
        self.worker.require_challenge.connect(self.show_challenge)
        self.worker.update_preview.connect(self.update_preview)
        
        # Update UI state
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        
        # Start the worker
        self.worker.start()
        
        # Show notification
        self.tray_icon.showMessage(
            "Instagram Auto Poster", 
            "Posting task started",
            QSystemTrayIcon.Information, 
            2000
        )
        
    def stop_worker(self):
        if self.worker:
            self.worker.stop()
            
    def worker_done(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("Pause")
        
        # Refresh the posts table
        self.refresh_posts_table()
        
    def show_2fa(self):
        dialog = AuthDialog(
            "Two-Factor Authentication Required",
            "Enter the code sent to your phone or authentication app:"
        )
        if dialog.exec_():
            self.worker.complete_2fa(dialog.get_code())
        
    def show_challenge(self, username):
        dialog = AuthDialog(
            f"Verification Required for {username}",
            "Enter the verification code sent by Instagram:"
        )
        if dialog.exec_():
            self.worker.complete_challenge(dialog.get_code())
            
    def log(self, message):
        now = datetime.now().strftime('%H:%M:%S')
        self.log_output.append(f"[{now}] {message}")
        
        # Auto-scroll to bottom
        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_output.setTextCursor(cursor)
        
    def clear_log(self):
        self.log_output.clear()
        
    def save_log(self):
        log_text = self.log_output.toPlainText()
        if not log_text:
            QMessageBox.information(self, "Empty Log", "There is no log content to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Log File", 
            os.path.join(self.settings.value("log_dir", "logs"), f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"),
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_text)
                QMessageBox.information(self, "Log Saved", f"Log has been saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save log: {str(e)}")
                
    def update_status(self, status):
        self.status_label.setText(status)
        
    def update_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        
    def update_preview(self, image_path, caption):
        self.preview_widget.set_preview(image_path, caption)
        
    def show_about(self):
        QMessageBox.about(
            self, 
            "About Instagram Auto Poster Pro",
            """<h3>Instagram Auto Poster Pro</h3>
            <p>A professional tool for automated Instagram posting.</p>
            <p>Version 1.0.1</p>
            <p>Supports:</p>
            <ul>
                <li>Developer: Mr Saad Bin Ismail</li>
                <li>Multiple account management</li>
                <li>2-Step Verification</li>
                <li>CSV-driven content scheduling</li>
                <li>Image posting with captions</li>
                <li>Configurable delays between posts</li>
                <li>Hashtag management</li>
                <li>Session persistence</li>
            </ul>
            <p>Use responsibly and in accordance with Instagram's terms of service.</p>"""
        )
