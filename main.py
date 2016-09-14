# !/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


if __name__ == '__main__':
    import os

    if 'QT_API' not in os.environ:
        os.environ['QT_API'] = 'pyqt4'

    import sys
    from qtpy.QtWidgets import QApplication
    from mainwindow import MainWindow

    app = QApplication(sys.argv)

    mw = MainWindow()
    mw.resize(380, 580)
    mw.read_settings()
    mw.show()
    mw.load_game()

    sys.exit(app.exec_())
