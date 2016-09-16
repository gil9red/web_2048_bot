#!/usr/bin/env python
# -*- coding: utf-8 -*-

__author__ = 'ipetrash'


import os

if 'QT_API' not in os.environ:
    os.environ['QT_API'] = 'pyqt4'


from qtpy.QtWidgets import QApplication, QMainWindow, QMessageBox
from qtpy.QtGui import QKeyEvent, QMouseEvent, QDesktopServices
from qtpy.QtCore import Qt, QEventLoop, QTimer, QSettings, QObject, QUrl, QEvent
from qtpy.QtNetwork import QNetworkProxyFactory

from qtpy.QtWebEngineWidgets import QWebEngineView as QWebView
from qtpy.QtWebEngineWidgets import QWebEngineSettings as QWebSettings


from common import *

logger = get_logger('web_2048_bot')


import traceback


def log_uncaught_exceptions(ex_cls, ex, tb):
    text = '{}: {}:\n'.format(ex_cls.__name__, ex)
    text += ''.join(traceback.format_tb(tb))

    logger.critical(text)
    QMessageBox.critical(None, 'Error', text)

    QApplication.instance().quit()

sys.excepthook = log_uncaught_exceptions


def key_press_release(widget, key, modifier=Qt.NoModifier):
    """
    Функция для отправления события нажатия кнопки.

    # Имитация нажатия на пробел:
    key_press_release(widget, Qt.Key_Space)
    """

    key_press = QKeyEvent(QKeyEvent.KeyPress, key, modifier, None, False, 0)
    QApplication.sendEvent(widget, key_press)

    key_release = QKeyEvent(QKeyEvent.KeyRelease, key, modifier, None, False, 0)
    QApplication.sendEvent(widget, key_release)


def mouse_click(widget, pos, mouse=Qt.LeftButton, modifier=Qt.NoModifier):
    """
    Функция для отправления события нажатия кнопки мыши.
    """

    mouse_press = QMouseEvent(QEvent.MouseButtonPress, pos, mouse, mouse, modifier)
    QApplication.sendEvent(widget, mouse_press)

    mouse_release = QMouseEvent(QEvent.MouseButtonRelease, pos, mouse, mouse, modifier)
    QApplication.sendEvent(widget, mouse_release)


URL = QUrl('http://gabrielecirulli.github.io/2048/')

# Чтобы не было проблем запуска компов с прокси:
QNetworkProxyFactory.setUseSystemConfiguration(True)

try:
    # Если в setAttribute положить, то при отсутствии атрибута DeveloperExtrasEnabled (в Qt 5)
    # приложение падает в dll и это не получается остановить, однако, если попытаться заранее
    # обратиться к атрибуту, то при его отсутствии будет выброшено AttributeError
    QWebSettings.DeveloperExtrasEnabled

    # Чтобы можно было для страницы открывать инспектор
    QWebSettings.globalSettings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
except AttributeError:
    pass

# Регулярка для вытаскивания индексов ячеек
import re
TILE_INDEX_RE = re.compile(r"tile-position-(\d)-(\d)")

from simple_2048_bot.board import Board
from simple_2048_bot.board_score_heuristics import perfect_heuristic
from simple_2048_bot.board_score_strategy import ExpectimaxStrategy
from simple_2048_bot.config import WIN_VALUE, NEVER_STOP, BOARD_SIZE
import simple_2048_bot.moves as move


STRATEGY = ExpectimaxStrategy(perfect_heuristic)
BOT_MOVE_BY_KEY_DICT = {
    move.UP: Qt.Key_W,
    move.DOWN: Qt.Key_S,
    move.LEFT: Qt.Key_A,
    move.RIGHT: Qt.Key_D,
}


class MainWindow(QMainWindow, QObject):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle('web_2048_bot')

        self.view = QWebView()
        self.setCentralWidget(self.view)

        # Таймер для кликов бота
        self.timer = QTimer()
        self.timer.timeout.connect(self.bot_click)
        self.timer.setInterval(600)

        self.tool_bar = self.addToolBar("General")
        self.tool_bar.setObjectName("General")

        self.action_run_bot = self.tool_bar.addAction('Run Bot')
        self.action_run_bot.setCheckable(True)
        self.action_run_bot.triggered.connect(lambda checked: self.timer.start() if checked else self.timer.stop())

        self.action_next_step_bot = self.tool_bar.addAction('Next Step Bot')
        self.action_next_step_bot.triggered.connect(lambda x=None: self.stop_bot() or self.bot_click())

        self.tool_bar.addSeparator()
        self.action_go_to_2048 = self.tool_bar.addAction('Go to 2048')
        self.action_go_to_2048.triggered.connect(lambda x=None: QDesktopServices.openUrl(URL))

        self._win = False
        

        # from qtpy.QtWidgets import QPlainTextEdit, QPushButton
        # self.pl = QPlainTextEdit("""\n\n\ndoc = self.view.page().mainFrame().documentElement()\nbutton = doc.findFirst('.restart-button')\nprint(button.toPlainText())\nprint(button.geometry())""")
        # self.pl.show()
        # self.pb = QPushButton(self.pl)
        # self.pb.show()
        # self.pb.clicked.connect(lambda x: exec(self.pl.toPlainText().strip()))

    def start_bot(self):
        logger.debug('start start_bot')

        self.action_run_bot.setChecked(True)
        self.timer.start()

        logger.debug('finish start_bot')

    def stop_bot(self):
        logger.debug('start stop_bot')

        self.action_run_bot.setChecked(False)
        self.timer.stop()

        logger.debug('finish stop_bot')

    def load_game(self):
        logger.debug('start load_game')

        # Загрузка url и ожидание ее
        self.view.load(URL)

        loop = QEventLoop()
        self.view.loadFinished.connect(loop.quit)
        loop.exec_()

        self.start_bot()

        logger.debug('finish load_game')

    def matrix_board(self):
        """Функция парсит страницу сайта с 2048 и возвращает список списков -- матрицу доски этой игры 2048.
        Размер матрицы BOARD_SIZE на BOARD_SIZE."""

        # Создание матрицы BOARD_SIZE на BOARD_SIZE
        board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]

        doc = self.view.page().mainFrame().documentElement()

        # Перебор ячеек таблицы, составление массива ячеек
        for inner in doc.findAll(".tile-inner"):
            attr_class = inner.parent().attribute("class")
            match = TILE_INDEX_RE.search(attr_class)
            if match:
                col, row = int(match.group(1)) - 1, int(match.group(2)) - 1
                value = int(inner.toPlainText())
                board[row][col] = value

        return board

    def bot_click(self):
        """Функция для случайного клика на WASD."""

        board = Board(self.matrix_board())

        try:
            next_move = STRATEGY.get_next_move(board)

            key = BOT_MOVE_BY_KEY_DICT[next_move]
            key_press_release(self.view, key)

            board.move(next_move)

        except Exception as e:
            logger.exception(e)

        if not board.has_legal_moves():
            logger.debug('Fail')
            logger.debug('board:\n%s', repr(board))
            # TODO: ...
            self.stop_bot()

        global WIN_VALUE
        success = board.get_max_tile() == WIN_VALUE
        if success:
            logger.debug('Win')
            self._win = True

        # TODO: автоматизировать. Добавить флаг, который определяет, должен ли бот автоматически
        # после достижения 2048 дальше играть
        # Если запустить после победы (достигли 2048), то снимаем ограничение
        if self._win:
            WIN_VALUE = NEVER_STOP

            # Делаем клик на продолжить игру
            doc = self.view.page().mainFrame().documentElement()
            button = doc.findFirst('.keep-playing-button')
            if button.isNull() or button.geometry().isNull():
                # Может, кнопка еще не появилась, нужно подождать
                return

            pos = button.geometry().center()
            mouse_click(self.view, pos)
            logger.debug('Button keep-playing-button click')

            # Игра продолжается
            self._win = False

    def read_settings(self):
        logger.debug('start read_settings')

        config = QSettings(CONFIG_FILE, QSettings.IniFormat)

        state = config.value('MainWindow_State')
        if state:
            self.restoreState(state)

        geometry = config.value('MainWindow_Geometry')
        if geometry:
            self.restoreGeometry(geometry)

        logger.debug('finish read_settings')

    def write_settings(self):
        logger.debug('start write_settings')

        config = QSettings(CONFIG_FILE, QSettings.IniFormat)
        config.setValue('MainWindow_State', self.saveState())
        config.setValue('MainWindow_Geometry', self.saveGeometry())

        logger.debug('finish write_settings')

    def closeEvent(self, event):
        logger.debug('close main window')

        self.write_settings()

        QApplication.instance().quit()
