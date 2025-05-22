import os
import time
import random
import logging
from datetime import datetime
from threading import Event
import pandas as pd
from instagrapi import Client
from instagrapi.exceptions import (
    TwoFactorRequired, ChallengeRequired, LoginRequired,
    ClientConnectionError, ClientThrottledError
)
from PyQt5.QtCore import QThread, pyqtSignal

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
                # Convert hours to seconds for the actual delay
                wait_time = random.uniform(
                    self.config['post_delay_min'], 
                    self.config['post_delay_max']
                )
                wait_time = int(wait_time * 3600)
                
                self.log(f"Waiting {wait_time / 3600:.1f} hours before next post...")
                
                # Wait with 1-second granularity so we can check for stop/pause
                for _ in range(wait_time):
                    if not self.running or self.paused:
                        break
                    time.sleep(1)
                
                if not self.running:
                    self.log("Process stopped by user during waiting period")
                    break
                elif self.paused:
                    continue

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
                
            except ClientThrottledError:
                self.log("Instagram is rate limiting. Waiting longer before next attempt...", "warning")
                time.sleep(random.randint(self.config['post_delay_max'], self.config['post_delay_max'] * 2))
                
            except ClientConnectionError:
                self.log("Network error during posting. Will retry next post...", "error")
                
            except Exception as e:
                self.log(f"Post failed: {str(e)}", "error")
                
                # Try to check if we've been logged out
                try:
                    self.client.account_info()
                except LoginRequired:
                    self.log("Session expired, attempting to login again...", "warning")
                    self.login()
                except Exception:
                    pass  # Other error, continue with next post

    def pause(self):
        self.paused = True
        self.update_status.emit("Paused")
        
    def resume(self):
        self.paused = False
        self.update_status.emit("Running")

    def stop(self):
        self.running = False
        self.update_status.emit("Stopping...")
