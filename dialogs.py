from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QApplication
)
from PyQt5.QtCore import Qt

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
