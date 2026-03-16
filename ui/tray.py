import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from typing import Callable

from PyQt6.QtCore import QObject
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

import utils.i18n as i18n
from utils.config import APP_NAME, ICON_APP
from utils.dialogs import confirm

logger = logging.getLogger(__name__)


class VeilClipTray(QObject):
    def __init__(
        self,
        on_open: Callable | None = None,
        on_settings: Callable | None = None,
        on_clear: Callable | None = None,
        on_donate: Callable | None = None,
        on_help: Callable | None = None,
        on_exit: Callable | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._on_open = on_open
        self._on_settings = on_settings
        self._on_clear = on_clear
        self._on_donate = on_donate
        self._on_help = on_help
        self._on_exit = on_exit

        self._tray = QSystemTrayIcon(self)
        self._setup_icon()
        self._setup_menu()
        self._setup_signals()

    def _setup_icon(self) -> None:
        icon_path = Path(ICON_APP)
        if icon_path.exists():
            self._tray.setIcon(QIcon(str(icon_path)))
        else:
            self._tray.setIcon(
                QApplication.style().standardIcon(
                    QApplication.style().StandardPixmap.SP_ComputerIcon
                )
            )
            logger.warning("Icon not found at %s - using fallback.", icon_path)

        self._tray.setToolTip(i18n.get("tray.tooltip"))

    def _setup_menu(self) -> None:
        menu = QMenu()

        title_action = menu.addAction(i18n.get("app.tagline"))
        title_action.setEnabled(False)
        menu.addSeparator()

        open_action = menu.addAction(i18n.get("tray.open"))
        open_action.triggered.connect(self._handle_open)

        settings_action = menu.addAction(i18n.get("tray.settings"))
        settings_action.triggered.connect(self._handle_settings)

        clear_action = menu.addAction(i18n.get("tray.clear_history"))
        clear_action.triggered.connect(self._handle_clear)

        menu.addSeparator()

        donate_action = menu.addAction(i18n.get("tray.donate"))
        donate_action.triggered.connect(self._handle_donate)

        help_action = menu.addAction(i18n.get("tray.help"))
        help_action.triggered.connect(self._handle_help)

        menu.addSeparator()

        exit_action = menu.addAction(i18n.get("tray.exit"))
        exit_action.triggered.connect(self._handle_exit)

        self._tray.setContextMenu(menu)
        self._menu = menu

    def _setup_signals(self) -> None:
        self._tray.activated.connect(self._on_tray_activated)

    def show(self) -> None:
        self._tray.show()
        logger.debug("Tray icon shown.")

    def hide(self) -> None:
        self._tray.hide()

    def show_message(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        ms: int = 3000,
    ) -> None:
        self._tray.showMessage(title, message, icon, ms)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self._handle_open()

    def _handle_open(self) -> None:
        if self._on_open:
            self._on_open()
        else:
            logger.debug("on_open callback not set.")

    def _handle_settings(self) -> None:
        if self._on_settings:
            self._on_settings()
        else:
            logger.debug("on_settings callback not set.")

    def _handle_clear(self) -> None:
        if confirm(
            None,
            i18n.get("dialogs.confirm_clear_title"),
            i18n.get("dialogs.confirm_clear_body"),
            confirm_key="common.yes",
            cancel_key="common.no",
            danger=True,
        ):
            if self._on_clear:
                removed = self._on_clear()
                self.show_message(APP_NAME, i18n.get("notifications.history_cleared"))
                logger.info("History cleared - %s item(s) removed.", removed)
            else:
                logger.debug("on_clear callback not set.")

    def _handle_donate(self) -> None:
        if self._on_donate:
            self._on_donate()
        else:
            logger.debug("on_donate callback not set.")

    def _handle_help(self) -> None:
        if self._on_help:
            self._on_help()
        else:
            logger.debug("on_help callback not set.")

    def _handle_exit(self) -> None:
        self._tray.hide()
        if self._on_exit:
            self._on_exit()
        else:
            QApplication.quit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    from utils.config import LOCALE_DIR

    i18n.init(locale_dir=LOCALE_DIR)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    def on_open():
        print("Open triggered")

    def on_settings():
        print("Settings triggered")

    def on_clear():
        print("Clear History triggered")
        return 0

    tray = VeilClipTray(
        on_open=on_open,
        on_settings=on_settings,
        on_clear=on_clear,
        on_exit=app.quit,
    )
    tray.show()
    sys.exit(app.exec())
