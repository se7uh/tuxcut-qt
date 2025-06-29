#!/usr/bin/env python3

import sys
from PySide6.QtWidgets import QApplication
from main_window import MainWindow
import os

def main():
    app = QApplication(sys.argv)
    
    # Load and apply stylesheet
    style_path = os.path.join(os.path.dirname(__file__), 'styles', 'main_style.qss')
    if os.path.exists(style_path):
        with open(style_path, 'r') as f:
            app.setStyleSheet(f.read())
    else:
        print(f"Warning: Stylesheet not found at {style_path}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 