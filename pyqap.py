#! /usr/bin/env python3

import sys

from PyQt6.QtWidgets import QApplication, QWidget

def main():
    app = QApplication(sys.argv)

    w = QWidget()
    w.setWindowTitle('pyqap')
    w.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
