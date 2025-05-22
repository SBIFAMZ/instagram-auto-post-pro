import sys
from PyQt5.QtWidgets import QApplication
from main_window import InstagramAutoPostApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app_icon = QApplication.style().standardIcon(QApplication.style().SP_DialogApplyButton)
    app.setWindowIcon(app_icon)
    window = InstagramAutoPostApp()
    window.show()
    sys.exit(app.exec_())
