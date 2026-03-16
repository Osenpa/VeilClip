from __future__ import annotations

from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QLabel, QLineEdit, QMenu, QPushButton, QToolButton, QWidget

import utils.i18n as i18n

_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    _patch_button(QPushButton)
    _patch_button(QToolButton)
    _patch_label()
    _patch_action()
    _patch_widget_titles()
    _patch_widget_tooltips()
    _patch_placeholders()
    _patch_menu()
    _patch_input_dialogs()
    _patch_file_dialogs()


def _translate(value):
    return i18n.literal(value) if isinstance(value, str) else value


def translate_labels(root: QWidget) -> None:
    for label in root.findChildren(QLabel):
        label.setText(_translate(label.text()))


def _patch_label() -> None:
    original_init = QLabel.__init__
    original_set_text = QLabel.setText

    def __init__(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = _translate(args[0])
        if isinstance(kwargs.get("text"), str):
            kwargs["text"] = _translate(kwargs["text"])
        original_init(self, *args, **kwargs)

    def setText(self, text):
        return original_set_text(self, _translate(text))

    QLabel.__init__ = __init__
    QLabel.setText = setText


def _patch_button(cls) -> None:
    original_init = cls.__init__
    original_set_text = cls.setText

    def __init__(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = _translate(args[0])
        if isinstance(kwargs.get("text"), str):
            kwargs["text"] = _translate(kwargs["text"])
        original_init(self, *args, **kwargs)

    def setText(self, text):
        return original_set_text(self, _translate(text))

    cls.__init__ = __init__
    cls.setText = setText


def _patch_action() -> None:
    original_init = QAction.__init__
    original_set_text = QAction.setText

    def __init__(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = _translate(args[0])
        if isinstance(kwargs.get("text"), str):
            kwargs["text"] = _translate(kwargs["text"])
        original_init(self, *args, **kwargs)

    def setText(self, text):
        return original_set_text(self, _translate(text))

    QAction.__init__ = __init__
    QAction.setText = setText


def _patch_widget_titles() -> None:
    original = QWidget.setWindowTitle

    def setWindowTitle(self, title):
        return original(self, _translate(title))

    QWidget.setWindowTitle = setWindowTitle


def _patch_widget_tooltips() -> None:
    original = QWidget.setToolTip

    def setToolTip(self, text):
        return original(self, _translate(text))

    QWidget.setToolTip = setToolTip


def _patch_placeholders() -> None:
    original = QLineEdit.setPlaceholderText

    def setPlaceholderText(self, text):
        return original(self, _translate(text))

    QLineEdit.setPlaceholderText = setPlaceholderText


def _patch_menu() -> None:
    original_add_action = QMenu.addAction
    original_add_menu = QMenu.addMenu

    def addAction(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = _translate(args[0])
        return original_add_action(self, *args, **kwargs)

    def addMenu(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], str):
            args[0] = _translate(args[0])
        return original_add_menu(self, *args, **kwargs)

    QMenu.addAction = addAction
    QMenu.addMenu = addMenu


def _patch_input_dialogs() -> None:
    original_get_text = QInputDialog.getText
    original_get_int = QInputDialog.getInt

    def getText(parent, title, label, *args, **kwargs):
        return original_get_text(parent, _translate(title), _translate(label), *args, **kwargs)

    def getInt(parent, title, label, *args, **kwargs):
        return original_get_int(parent, _translate(title), _translate(label), *args, **kwargs)

    QInputDialog.getText = staticmethod(getText)
    QInputDialog.getInt = staticmethod(getInt)


def _patch_file_dialogs() -> None:
    original_save = QFileDialog.getSaveFileName
    original_open = QFileDialog.getOpenFileName
    original_dir = QFileDialog.getExistingDirectory

    def getSaveFileName(parent=None, caption="", directory="", filter="", *args, **kwargs):
        return original_save(parent, _translate(caption), directory, _translate(filter), *args, **kwargs)

    def getOpenFileName(parent=None, caption="", directory="", filter="", *args, **kwargs):
        return original_open(parent, _translate(caption), directory, _translate(filter), *args, **kwargs)

    def getExistingDirectory(parent=None, caption="", directory="", *args, **kwargs):
        return original_dir(parent, _translate(caption), directory, *args, **kwargs)

    QFileDialog.getSaveFileName = staticmethod(getSaveFileName)
    QFileDialog.getOpenFileName = staticmethod(getOpenFileName)
    QFileDialog.getExistingDirectory = staticmethod(getExistingDirectory)
