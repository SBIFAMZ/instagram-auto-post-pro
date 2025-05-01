import sys
import os
import time
import random
import json
import logging
from datetime import datetime
from threading import Event
import pandas as pd
from instagrapi import Client
from instagrapi.exceptions import (
    TwoFactorRequired, 
    ChallengeRequired, 
    LoginRequired,
    ClientError,
    ClientConnectionError,
    ClientForbiddenError,
    ClientThrottledError
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QFileDialog, QTextEdit, QFormLayout,
    QMessageBox, QGroupBox, QStackedWidget, QDialog, QTabWidget, QCheckBox,
    QProgressBar, QComboBox, QToolButton, QSplitter, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QGridLayout, QDoubleSpinBox, QDateTimeEdit,
    QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer, QSize, QSettings, QDateTime
from PyQt5.QtGui import QPixmap, QIcon, QFont, QColor, QPalette, QTextCursor, QDesktopServices


class InstagramWorker(QThread):
    update_log = pyqtSignal(str)
    update_status = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal()
    require_2fa = pyqtSignal()
    require_challenge = pyqtSignal(str)
    update_preview = pyqtSignal(str, str)  # image path, caption

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.client = Client()

        # Set proxy if provided
        if self.config.get('proxy'):
            self.client.set_proxy(self.config['proxy'])

        self.client.set_device(self.client.device_settings)
        self.awaiting_2fa = Event()
        self.running = True
        self.paused = False
        self.total_posts = 0
        self.current_post = 0
        
        
        # Setup logging
        log_file = os.path.join(
            self.config.get('log_dir', 'logs'), 
            f"instagram_posting_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("InstagramAutoPost")

    def log(self, message, level="info"):
        """Log message to both UI and file"""
        self.update_log.emit(message)
        
        if level == "info":
            self.logger.info(message)
        elif level == "error":
            self.logger.error(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "debug":
            self.logger.debug(message)

    def log_suspicious_activity(self, activity):
        with open("suspicious_activity.log", "a") as log_file:
            log_file.write(f"{datetime.now()}: {activity}\n")
        self.log(f"Suspicious activity logged: {activity}", "warning")

    def rotate_proxy(self):
        proxies = self.config.get('proxies', [])
    def run(self):
        try:
            self.client.delay_range = (
                self.config['api_delay_min'], self.config['api_delay_max']
            )
            self.update_status.emit("Logging in...")
            self.login()
            
            if not self.running:
                return
                
            self.update_status.emit("Processing posts...")
            self.process_posts()
            
        except Exception as e:
            self.log(f"Unhandled error: {str(e)}", "error")
        finally:
            if self.running:
                self.update_status.emit("Finished")
            else:
                self.update_status.emit("Stopped")
            self.finished.emit()

    def login(self):
        session_file = self.config['session_file']
        
        # Create session directory if it doesn't exist
        os.makedirs(os.path.dirname(session_file), exist_ok=True)
        
        try:
            if os.path.exists(session_file):
                self.log("Attempting to use saved session...")
                time.sleep(random.uniform(1.5, 3.0))  # Mimic human delay
                self.client.load_settings(session_file)
                time.sleep(random.uniform(1.0, 2.0))  # Mimic human delay
                self.client.get_timeline_feed()  # Test if session is valid
                user_info = self.client.account_info()
                self.log(f"Logged in as {user_info.username} using session")
                return
        except Exception as e:
            self.log(f"Session error: {str(e)}", "warning")
            self.log("Will attempt fresh login", "info")

        try:
            self.log(f"Logging in as {self.config['username']}...")
            time.sleep(random.uniform(2.0, 4.0))  # Mimic human delay
            self.client.login(self.config['username'], self.config['password'])
            time.sleep(random.uniform(1.0, 2.5))  # Mimic human delay
            self.client.dump_settings(session_file)
            user_info = self.client.account_info()
            self.log(f"Login successful - Welcome {user_info.full_name} (@{user_info.username})")
        except TwoFactorRequired:
            self.log("Two-factor authentication required", "warning")
            self.require_2fa.emit()
            self.awaiting_2fa.wait()
        except ChallengeRequired:
            self.log("Challenge required - Instagram needs verification", "warning")
            self.require_challenge.emit(self.config['username'])
        except ClientConnectionError:
            self.log("Network error - Check your internet connection", "error")
            raise
        except ClientThrottledError:
            self.log("Instagram is limiting requests - Try again later", "error")
            raise
        except Exception as e:
            self.log(f"Login failed: {str(e)}", "error")
            raise

    def complete_2fa(self, code):
        try:
            self.log("Submitting 2FA code...")
            self.client.two_factor_login(code.strip())
            self.client.dump_settings(self.config['session_file'])
            user_info = self.client.account_info()
            self.log(f"2FA successful - Welcome {user_info.full_name} (@{user_info.username})")
        except Exception as e:
            self.log(f"2FA failed: {str(e)}", "error")
        finally:
            self.awaiting_2fa.set()  # unblock login thread

    def complete_challenge(self, code):
        try:
            self.log("Submitting verification code...")
            self.client.challenge_code(code.strip())
            self.client.dump_settings(self.config['session_file'])
            user_info = self.client.account_info()
            self.log(f"Verification successful - Welcome {user_info.full_name} (@{user_info.username})")
        except Exception as e:
            self.log(f"Verification failed: {str(e)}", "error")

    def process_posts(self):
        try:
            self.log("Sleeping for 60 seconds after login to appear human...")
            time.sleep(60)
            self.log(f"Loading posts from {self.config['csv_path']}...")
            
            df = pd.read_csv(self.config['csv_path'])
            
            if 'filename' not in df.columns or 'caption' not in df.columns:
                self.log("CSV must have 'filename' and 'caption' columns", "error")
                return
                
            # Add posted column if it doesn't exist
            if 'posted' not in df.columns:
                df['posted'] = False
                
            # Add timestamp column if it doesn't exist
            if 'timestamp' not in df.columns:
                df['timestamp'] = ""
                
            # Filter out already posted if configured
            if not self.config.get('repost_existing', False):
                pending_posts = df[df['posted'] == False]
                self.log(f"CSV loaded: {len(df)} total rows, {len(pending_posts)} pending posts")
                if len(pending_posts) == 0:
                    self.log("No pending posts to process")
                    return
            else:
                pending_posts = df
                self.log(f"CSV loaded: {len(df)} posts (including already posted)")
                
            # Shuffle pending posts
            pending_posts = pending_posts.sample(frac=1).reset_index(drop=True)
            
            # Update progress bar max
            self.total_posts = len(pending_posts)
            self.current_post = 0
            self.progress_update.emit(0, self.total_posts)
            
        except pd.errors.EmptyDataError:
            self.log("CSV file is empty", "error")
            return
        except FileNotFoundError:
            self.log(f"CSV file not found: {self.config['csv_path']}", "error")
            return
        except Exception as e:
            self.log(f"CSV load error: {str(e)}", "error")
            return

        error_count = 0
        MAX_ERRORS = 5

        for idx, row in pending_posts.iterrows():
            if not self.running:
                self.log("Process stopped by user")
                break
                
            while self.paused:
                time.sleep(1)
                if not self.running:
                    break
                    
            if not self.config.get('repost_existing', False) and row['posted']:
                continue

            img_path = os.path.join(self.config['images_dir'], row['filename'])
            if not os.path.exists(img_path):
                self.log(f"Image not found: {img_path}", "error")
                continue
                
            # Validate image file
            valid_extensions = ['.jpg', '.jpeg', '.png']
            if not any(img_path.lower().endswith(ext) for ext in valid_extensions):
                self.log(f"Unsupported image format: {img_path}", "error")
                continue

            # Show preview of what we're about to post
            self.update_preview.emit(img_path, row['caption'])
            self.log(f"Preparing to post {row['filename']}...")
            
            # Sleep random time before posting if not the first post
            if self.current_post > 0:
                wait_time = random.randint(
                    self.config['post_delay_min'], 
                    self.config['post_delay_max']
                )
                self.log(f"Waiting {wait_time} seconds before next post...")
                
                # Wait with 1-second granularity to allow stop/pause checks
                for _ in range(wait_time):
                    if not self.running or self.paused:
                        break
                    time.sleep(1)

            try:
                self.log(f"Posting image: {row['filename']}")
                
                # Handle hashtags specially if configured
                caption = row['caption']
                if self.config.get('hashtags_in_first_comment', False) and '#' in caption:
                    parts = caption.split('#', 1)
                    main_caption = parts[0].strip()
                    hashtags = '#' + parts[1].strip()
                    
                    self.log("Moving hashtags to first comment...")
                    media = self.client.photo_upload(img_path, main_caption)
                    self.client.media_comment(media.id, hashtags)
                    self.log("Comment with hashtags added")
                else:
                    self.client.photo_upload(img_path, caption)
                
                self.log("Post successful!")
                
                # Update CSV
                df.at[idx, 'posted'] = True
                df.at[idx, 'timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                df.to_csv(self.config['csv_path'], index=False)
                
                # Update progress
                self.current_post += 1
                self.progress_update.emit(self.current_post, self.total_posts)

                if self.current_post % 5 == 0:  # Rotate proxy every 5 posts
                    self.rotate_proxy()

                if self.current_post % 3 == 0:  # View stories every 3 posts
                    self.view_stories()
                
            except ClientThrottledError:
                self.log("Instagram is rate limiting. Waiting longer before next attempt...", "warning")
                time.sleep(random.randint(self.config['post_delay_max'], self.config['post_delay_max'] * 2))
                
            except ClientConnectionError:
                self.log("Network error during posting. Will retry next post...", "error")
                
            except Exception as e:
                error_count += 1
                self.log(f"Error occurred: {str(e)}", "error")
                if error_count >= MAX_ERRORS:
                    self.log("Too many errors. Stopping to avoid account flags.", "warning")
                    break
                
                # Try to check if we've been logged out
                try:
                    self.client.account_info()
                except LoginRequired:
                    self.log("Session expired, attempting to login again...", "warning")
                    self.login()
                except Exception:
                    pass  # Other error, continue with next post

    def view_stories(self):
        try:
            stories = self.client.user_stories(self.client.user_id)
            for story in stories[:5]:  # View up to 5 stories
                self.client.story_view(story.pk)
                self.log(f"Viewed story: {story.pk}")
                time.sleep(random.uniform(2, 5))  # Random delay
        except Exception as e:
            self.log(f"Error viewing stories: {str(e)}", "error")

    def pause(self):
        self.paused = True
        self.update_status.emit("Paused")
        
    def resume(self):
        self.paused = False
        self.update_status.emit("Running")

    def stop(self):
        self.running = False
        self.update_status.emit("Stopping...")


class AuthDialog(QDialog):
    def __init__(self, title="Authentication Required", message="Enter verification code:", parent=None):
        super().__init__(parent=parent or QApplication.activeWindow())
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowModality(Qt.ApplicationModal)
        
        layout = QVBoxLayout()
        # Force dialog to front
        self.activateWindow()  # Bring to front
        self.raise_()  # Ensure visibility
        
        # Add icon and message
        icon_layout = QHBoxLayout()
        icon_label = QLabel()
        icon_label.setPixmap(QApplication.style().standardIcon(
            QApplication.style().SP_MessageBoxWarning).pixmap(32, 32))
        icon_layout.addWidget(icon_label)
        icon_layout.addWidget(QLabel(message))
        icon_layout.addStretch()
        layout.addLayout(icon_layout)
        
        # Add input field
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("Enter code")
        layout.addWidget(self.code_input)
        
        # Help text
        help_text = QLabel(
            "Check your phone or email for a verification code sent by Instagram."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        
        # Add buttons
        button_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.accept)
        self.submit_btn.setDefault(True)
        
        button_layout.addWidget(self.cancel_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.submit_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Connect enter key to submit
        self.code_input.returnPressed.connect(self.submit_btn.click)

    def get_code(self):
        return self.code_input.text().strip()


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
        
        # Proxy group
        proxy_group = QGroupBox("Proxy Settings")
        proxy_layout = QFormLayout()

        self.proxy_input = QLineEdit(self.settings.value("proxy", ""))
        proxy_layout.addRow("Proxy (IP:Port):", self.proxy_input)

        self.proxies_input = QTextEdit(self.settings.value("proxies", ""))
        self.proxies_input.setPlaceholderText("Enter proxies (one per line)")
        proxy_layout.addRow("Proxies:", self.proxies_input)

        proxy_group.setLayout(proxy_layout)

        general_layout.addWidget(paths_group)
        general_layout.addWidget(behavior_group)
        general_layout.addWidget(proxy_group)
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
        self.post_min.setRange(0, 3600)
        self.post_min.setValue(int(self.settings.value("post_delay_min", 10)))
        self.post_min.setSuffix(" sec")
        
        self.post_max = QSpinBox()
        self.post_max.setRange(0, 3600)
        self.post_max.setValue(int(self.settings.value("post_delay_max", 30)))
        self.post_max.setSuffix(" sec")
        
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
        
        # Save proxy settings
        self.settings.setValue("proxy", self.proxy_input.text())
        self.settings.setValue("proxies", self.proxies_input.toPlainText().splitlines())
        
        # Save delay settings
        self.settings.setValue("api_delay_min", self.api_min.value())
        self.settings.setValue("api_delay_max", self.api_max.value())
        self.settings.setValue("post_delay_min", self.post_min.value())
        self.settings.setValue("post_delay_max", self.post_max.value())
        
        self.settings.sync()
        
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved.")


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
        self.post_min.setRange(0, 3600)
        self.post_min.setSuffix(" sec")
        
        self.post_max = QSpinBox()
        self.post_max.setRange(0, 3600)
        self.post_max.setSuffix(" sec")
        
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
        self.post_min.setValue(int(self.settings.value("post_delay_min", 10)))
        self.post_max.setValue(int(self.settings.value("post_delay_max", 30)))
        
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
        self.settings.setValue("post_delay_min", self.post_min.value())
        self.settings.setValue("post_delay_max", self.post_max.value())
        
        # Save proxy settings from the SettingsWidget
        self.settings.setValue("proxy", self.settings_widget.proxy_input.text())
        self.settings.setValue("proxies", self.settings_widget.proxies_input.toPlainText().splitlines())
        
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
            'repost_existing': self.settings.value("repost_existing", "false") == "true",
            'proxy': self.settings.value("proxy", ""),
            'proxies': self.settings.value("proxies", "").splitlines()
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
                <li>CSV-driven content scheduling</li>
                <li>Image posting with captions</li>
                <li>Configurable delays between posts</li>
                <li>Hashtag management</li>
                <li>Session persistence</li>
            </ul>
            <p>Use responsibly and in accordance with Instagram's terms of service.</p>"""
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern style
    
    # Set application icon
    app_icon = QApplication.style().standardIcon(QApplication.style().SP_DialogApplyButton)
    app.setWindowIcon(app_icon)
    
    # Create and show the main window
    window = InstagramAutoPostApp()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec_())


