"""
ui/image_editor.py
──────────────────
ImageEditorWindow — PyQt6 image editor.

Tools
─────
  ✂  Crop       — drag to select area, commit on release
  ↗  Arrow      — drag to draw a red filled arrow
  🖊  Highlight  — drag to paint a yellow semi-transparent rectangle
  T   Text       — click to place text; placed texts can be selected,
                   moved by dragging, and edited via right-click menu

Toolbar actions
───────────────
  ↩ Undo   — up to 50 steps
  📋 Copy   — copy current image to system clipboard
  💾 Save   — Save As dialog (PNG / JPG / BMP)
  ✕ Close  — close the editor window
"""

from __future__ import annotations

import io
import math
import logging
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Qt imports ────────────────────────────────────────────────────────────────
from PyQt6.QtCore import Qt, QPoint, QPointF, QRect, QRectF
from PyQt6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QToolBar,
    QToolButton,
    QWidget,
)

import utils.i18n as i18n
from utils.dialogs import message
from utils.qt_i18n import translate_labels

logger = logging.getLogger(__name__)

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = "#0F1117"
BG_PANEL = "#1A1D27"
BG_HOVER = "#22263A"
ACCENT   = "#6C63FF"
TEXT     = "#E8E8F0"
TEXT_DIM = "#7B7D8E"
BORDER   = "#2A2D3E"
RED      = "#FF4C4C"
RED_DIM  = "#4A1515"

_TOOL_STYLE = f"""
    QToolButton {{
        background: transparent;
        color: {TEXT};
        border: 1px solid {BORDER};
        border-radius: 7px;
        padding: 5px 12px;
        font-family: 'Segoe UI', sans-serif;
        font-size: 12px;
        font-weight: 600;
    }}
    QToolButton:hover   {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
    QToolButton:pressed {{ background: {ACCENT};   color: white; border-color: {ACCENT}; }}
    QToolButton:checked {{ background: {ACCENT};   color: white; border-color: {ACCENT}; }}
"""
_BTN_ACCENT = f"""
    QPushButton {{
        background: {ACCENT}; color: white; border: none; border-radius: 7px;
        padding: 5px 14px;
        font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 700;
    }}
    QPushButton:hover   {{ background: #7D75FF; }}
    QPushButton:pressed {{ background: #5A52D5; }}
"""
_BTN_DANGER = f"""
    QPushButton {{
        background: {RED_DIM}; color: #FFB3B3;
        border: 1px solid {RED}; border-radius: 7px; padding: 5px 14px;
        font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 700;
    }}
    QPushButton:hover   {{ background: {RED}; color: white; }}
    QPushButton:pressed {{ background: #AA0000; }}
"""
_BTN_NEUTRAL = f"""
    QPushButton {{
        background: transparent; color: {TEXT};
        border: 1px solid {BORDER}; border-radius: 7px; padding: 5px 14px;
        font-family: 'Segoe UI', sans-serif; font-size: 12px; font-weight: 600;
    }}
    QPushButton:hover   {{ background: {BG_HOVER}; border-color: {ACCENT}; }}
    QPushButton:pressed {{ background: {ACCENT};   color: white; }}
"""

# ── Tool IDs ──────────────────────────────────────────────────────────────────
TOOL_CROP      = "crop"
TOOL_ARROW     = "arrow"
TOOL_HIGHLIGHT = "highlight"
TOOL_TEXT      = "text"

MAX_UNDO = 50

# ── Text item ─────────────────────────────────────────────────────────────────

class TextItem:
    """A movable, editable text overlay on the canvas."""
    _next_id = 0

    def __init__(self, text: str, pos: QPoint, color: QColor, size: int) -> None:
        TextItem._next_id += 1
        self.id    = TextItem._next_id
        self.text  = text
        self.pos   = QPoint(pos)   # top-left anchor of the text
        self.color = QColor(color)
        self.size  = size

    def bounding_rect(self) -> QRect:
        font = QFont("Segoe UI", self.size, QFont.Weight.Bold)
        fm   = QFontMetrics(font)
        r    = fm.boundingRect(self.text)
        pad  = 6
        return QRect(
            self.pos.x() + r.x() - pad,
            self.pos.y() + r.y() - pad,
            r.width()  + pad * 2,
            r.height()  + pad * 2,
        )

    def draw(self, painter: QPainter, selected: bool = False) -> None:
        font = QFont("Segoe UI", self.size, QFont.Weight.Bold)
        painter.setFont(font)

        pos = QPointF(float(self.pos.x()), float(self.pos.y()))

        # Outline
        outline_pen = QPen(
            QColor(0, 0, 0, 200), 3,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        painter.setPen(outline_pen)
        painter.drawText(pos, self.text)

        # Fill
        painter.setPen(QPen(self.color))
        painter.drawText(pos, self.text)

        # Selection indicator
        if selected:
            br = self.bounding_rect()
            sel_pen = QPen(QColor(ACCENT), 1, Qt.PenStyle.DashLine)
            painter.setPen(sel_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(br)

            # Drag handle corners
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(ACCENT)))
            for cx, cy in [
                (br.left(),  br.top()),
                (br.right(), br.top()),
                (br.left(),  br.bottom()),
                (br.right(), br.bottom()),
            ]:
                painter.drawEllipse(cx - 4, cy - 4, 8, 8)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _qpoint_to_f(p: QPoint) -> QPointF:
    """Safe QPoint → QPointF conversion (required by QPainterPath)."""
    return QPointF(float(p.x()), float(p.y()))


def _draw_filled_arrow(painter: QPainter, p1: QPointF, p2: QPointF) -> None:
    """Draw shaft + filled triangular arrowhead from p1 to p2."""
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    length = math.hypot(dx, dy)
    if length < 2.0:
        return

    # Unit vectors
    ux, uy = dx / length, dy / length   # along arrow
    px, py = -uy, ux                    # perpendicular

    head_len  = min(24.0, length * 0.40)
    head_half = head_len * 0.42

    base1 = QPointF(
        p2.x() - ux * head_len + px * head_half,
        p2.y() - uy * head_len + py * head_half,
    )
    base2 = QPointF(
        p2.x() - ux * head_len - px * head_half,
        p2.y() - uy * head_len - py * head_half,
    )

    path = QPainterPath()
    path.moveTo(p2)
    path.lineTo(base1)
    path.lineTo(base2)
    path.closeSubpath()
    painter.drawPath(path)


# ── Canvas ────────────────────────────────────────────────────────────────────

class _Canvas(QWidget):
    """
    Widget that displays the current image and handles all drawing.

    Raster operations (crop, arrow, highlight) are committed onto a QImage
    history stack for undo support.

    Text items are stored as live TextItem objects so they can be moved,
    recoloured, and resized after placement.  They are flattened onto the
    image only when copying/saving.
    """

    def __init__(self, image: QImage, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._tool = TOOL_CROP
        self._history: list[QImage] = [image.copy()]

        # Live drag state (reset after each commit)
        self._dragging   = False
        self._drag_start = QPoint()
        self._drag_end   = QPoint()

        # Text-tool options (controlled by the parent window)
        self._text_color = QColor("#FFFF00")
        self._text_size  = 18

        # Live text items (overlay, not yet baked into image)
        self._text_items: list[TextItem] = []
        self._selected_text: TextItem | None = None

        # Text drag state
        self._text_dragging  = False
        self._text_drag_off  = QPoint()

        self.setMouseTracking(True)
        self._sync_size()

    # ── Tool ──────────────────────────────────────────────────────────────────

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        self._drag_start = QPoint()
        self._drag_end   = QPoint()
        if tool != TOOL_TEXT:
            self._selected_text = None
        cursor_map = {
            TOOL_CROP:      Qt.CursorShape.CrossCursor,
            TOOL_ARROW:     Qt.CursorShape.CrossCursor,
            TOOL_HIGHLIGHT: Qt.CursorShape.CrossCursor,
            TOOL_TEXT:      Qt.CursorShape.IBeamCursor,
        }
        self.setCursor(QCursor(cursor_map.get(tool, Qt.CursorShape.ArrowCursor)))
        self.update()

    def set_text_color(self, color: QColor) -> None:
        self._text_color = color
        # Also update selected text item if any
        if self._selected_text is not None:
            self._selected_text.color = QColor(color)
            self.update()

    def set_text_size(self, size: int) -> None:
        self._text_size = max(6, min(int(size), 120))
        # Also update selected text item if any
        if self._selected_text is not None:
            self._selected_text.size = self._text_size
            self.update()

    # ── History ───────────────────────────────────────────────────────────────

    @property
    def current_image(self) -> QImage:
        return self._history[-1]

    def _push(self, img: QImage) -> None:
        self._history.append(img.copy())
        if len(self._history) > MAX_UNDO:
            self._history.pop(0)
        self._sync_size()
        self.update()

    def undo(self) -> str:
        # First try removing the last text item if any
        if self._text_items:
            removed = self._text_items.pop()
            if self._selected_text is removed:
                self._selected_text = None
            self._sync_size()
            self.update()
            return i18n.get(
                "image_editor.status.text_item_removed",
                count=len(self._history) - 1,
            )

        if len(self._history) < 2:
            return i18n.get("image_editor.status.nothing_to_undo")
        self._history.pop()
        self._drag_start = QPoint()
        self._drag_end   = QPoint()
        self._sync_size()
        self.update()
        n = len(self._history) - 1
        return i18n.get("image_editor.status.undo_done", count=n)

    def undo_steps(self) -> int:
        return len(self._history) - 1 + len(self._text_items)

    def _sync_size(self) -> None:
        img = self.current_image
        self.setFixedSize(img.width(), img.height())

    def flattened_image(self) -> QImage:
        """Return a copy of the current image with all text items baked in."""
        result = self.current_image.copy()
        if self._text_items:
            painter = QPainter(result)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for ti in self._text_items:
                ti.draw(painter, selected=False)
            painter.end()
        return result

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.pos()

            if self._tool == TOOL_TEXT:
                # Check if clicking on an existing text item
                hit = self._hit_text(pos)
                if hit is not None:
                    self._selected_text   = hit
                    self._text_dragging   = True
                    self._text_drag_off   = pos - hit.pos
                    self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                    self.update()
                else:
                    # Deselect + place new text
                    self._selected_text = None
                    self._commit_text(pos)
            else:
                self._dragging   = True
                self._drag_start = pos
                self._drag_end   = pos

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._text_dragging and self._selected_text is not None:
            new_pos = event.pos() - self._text_drag_off
            self._selected_text.pos = new_pos
            self.update()
        elif self._dragging:
            self._drag_end = event.pos()
            self.update()

        # Update cursor in text tool based on hover
        if self._tool == TOOL_TEXT and not self._text_dragging:
            hit = self._hit_text(event.pos())
            self.setCursor(QCursor(
                Qt.CursorShape.SizeAllCursor if hit else Qt.CursorShape.IBeamCursor
            ))

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._text_dragging:
                self._text_dragging = False
                self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor
                               if self._hit_text(event.pos())
                               else Qt.CursorShape.IBeamCursor))
                win = self.window()
                if hasattr(win, "_set_status"):
                    win._set_status("Text moved.")
            elif self._dragging:
                self._dragging = False
                self._drag_end = event.pos()
                self._commit_drag()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        """Right-click on a text item → edit / change color / change size / delete."""
        if self._tool != TOOL_TEXT:
            return
        hit = self._hit_text(event.pos())
        if hit is None:
            return

        self._selected_text = hit
        self.update()

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {BG_PANEL}; border: 1px solid {BORDER};
                border-radius: 8px; padding: 4px;
                color: {TEXT}; font-family: 'Segoe UI', sans-serif; font-size: 12px;
            }}
            QMenu::item {{ padding: 6px 14px; border-radius: 5px; }}
            QMenu::item:selected {{ background: {ACCENT}; color: white; }}
            QMenu::separator {{ height: 1px; background: {BORDER}; margin: 3px 8px; }}
        """)

        act_edit   = menu.addAction("✏  Edit text")
        act_color  = menu.addAction("🎨  Change color")
        act_size   = menu.addAction("🔡  Change size")
        menu.addSeparator()
        act_delete = menu.addAction("🗑  Delete")

        chosen = menu.exec(event.globalPos())
        if chosen == act_edit:
            self._edit_text_item(hit)
        elif chosen == act_color:
            self._change_text_color(hit)
        elif chosen == act_size:
            self._change_text_size(hit)
        elif chosen == act_delete:
            self._delete_text_item(hit)

    # ── Text item helpers ──────────────────────────────────────────────────────

    def _hit_text(self, pos: QPoint) -> TextItem | None:
        """Return the topmost text item whose bounding rect contains pos."""
        for ti in reversed(self._text_items):
            if ti.bounding_rect().contains(pos):
                return ti
        return None

    def _edit_text_item(self, ti: TextItem) -> None:
        new_text, ok = QInputDialog.getText(self, "Edit Text", "Edit:", text=ti.text)
        if ok and new_text.strip():
            ti.text = new_text.strip()
            self.update()
            win = self.window()
            if hasattr(win, "_set_status"):
                win._set_status(i18n.get("image_editor.status.text_updated", text=new_text[:30]))

    def _change_text_color(self, ti: TextItem) -> None:
        color = QColorDialog.getColor(ti.color, self, i18n.literal("Pick Text Colour"))
        if color.isValid():
            ti.color = color
            self._text_color = color     # sync toolbar picker
            win = self.window()
            if hasattr(win, "_on_canvas_color_changed"):
                win._on_canvas_color_changed(color)
            self.update()

    def _change_text_size(self, ti: TextItem) -> None:
        size, ok = QInputDialog.getInt(
            self, "Text Size", "Font size (6–120):",
            value=ti.size, min=6, max=120,
        )
        if ok:
            ti.size = size
            self._text_size = size
            win = self.window()
            if hasattr(win, "_on_canvas_size_changed"):
                win._on_canvas_size_changed(size)
            self.update()

    def _delete_text_item(self, ti: TextItem) -> None:
        if ti in self._text_items:
            self._text_items.remove(ti)
        if self._selected_text is ti:
            self._selected_text = None
        self.update()
        win = self.window()
        if hasattr(win, "_set_status"):
            win._set_status(i18n.get("image_editor.status.text_deleted"))

    # ── Geometry helpers ──────────────────────────────────────────────────────

    def _sel_rect(self) -> QRect:
        return QRect(self._drag_start, self._drag_end).normalized()

    def _img_rect(self) -> QRect:
        return QRect(0, 0, self.current_image.width(), self.current_image.height())

    # ── Commit ────────────────────────────────────────────────────────────────

    def _commit_drag(self) -> None:
        if self._drag_start == self._drag_end:
            return

        handlers = {
            TOOL_CROP:      self._do_crop,
            TOOL_ARROW:     self._do_arrow,
            TOOL_HIGHLIGHT: self._do_highlight,
        }
        fn = handlers.get(self._tool)
        msg = fn() if fn else ""

        self._drag_start = QPoint()
        self._drag_end   = QPoint()
        self.update()

        win = self.window()
        if msg and hasattr(win, "_set_status"):
            win._set_status(msg)

    def _commit_text(self, click_pos: QPoint) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Add Text",
            "Enter text:",
        )
        if not ok or not text.strip():
            return

        ti = TextItem(text.strip(), click_pos, QColor(self._text_color), self._text_size)
        self._text_items.append(ti)
        self._selected_text = ti
        self.update()

        win = self.window()
        if hasattr(win, "_set_status"):
            preview = text[:30] + ("…" if len(text) > 30 else "")
            win._set_status(i18n.get("image_editor.status.text_placed", text=preview))

    # ── Drawing operations ────────────────────────────────────────────────────

    def _do_crop(self) -> str:
        # Flatten text onto image before cropping
        if self._text_items:
            self._bake_text()
        rect = self._sel_rect().intersected(self._img_rect())
        if rect.width() < 2 or rect.height() < 2:
            return i18n.get("image_editor.status.crop_too_small")
        self._push(self.current_image.copy(rect))
        return i18n.get("image_editor.status.cropped", width=rect.width(), height=rect.height())

    def _do_arrow(self) -> str:
        result  = self.current_image.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor("#FF3333")
        pen   = QPen(color, 3, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap,
                     Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))

        p1 = _qpoint_to_f(self._drag_start)
        p2 = _qpoint_to_f(self._drag_end)

        painter.drawLine(p1, p2)
        _draw_filled_arrow(painter, p1, p2)

        painter.end()
        self._push(result)
        return i18n.get("image_editor.status.arrow_drawn")

    def _do_highlight(self) -> str:
        rect = self._sel_rect()
        if rect.width() < 2 or rect.height() < 2:
            return i18n.get("image_editor.status.selection_too_small")
        result  = self.current_image.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(255, 255, 0, 100)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        painter.end()
        self._push(result)
        return i18n.get("image_editor.status.highlighted", width=rect.width(), height=rect.height())

    def _bake_text(self) -> None:
        """Flatten all live text items onto the current raster image."""
        result  = self.current_image.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for ti in self._text_items:
            ti.draw(painter, selected=False)
        painter.end()
        self._push(result)
        self._text_items.clear()
        self._selected_text = None

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.drawImage(0, 0, self.current_image)

        # Draw live text items
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for ti in self._text_items:
            ti.draw(painter, selected=(ti is self._selected_text))

        if self._dragging and self._drag_start != self._drag_end:
            if self._tool == TOOL_CROP:
                self._paint_crop_overlay(painter)
            elif self._tool == TOOL_ARROW:
                self._paint_arrow_preview(painter)
            elif self._tool == TOOL_HIGHLIGHT:
                self._paint_highlight_preview(painter)

        painter.end()

    def _paint_crop_overlay(self, p: QPainter) -> None:
        rect = self._sel_rect()
        full = self.rect()

        p.setBrush(QBrush(QColor(0, 0, 0, 120)))
        p.setPen(Qt.PenStyle.NoPen)
        for r in [
            QRect(full.left(),  full.top(),            full.width(),                   rect.top()),
            QRect(full.left(),  rect.bottom(),         full.width(),                   full.bottom() - rect.bottom()),
            QRect(full.left(),  rect.top(),            rect.left(),                    rect.height()),
            QRect(rect.right(), rect.top(),            full.right() - rect.right(),    rect.height()),
        ]:
            if r.isValid():
                p.drawRect(r)

        p.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(ACCENT)))
        for cx, cy in [
            (rect.left(),  rect.top()),
            (rect.right(), rect.top()),
            (rect.left(),  rect.bottom()),
            (rect.right(), rect.bottom()),
        ]:
            p.drawEllipse(cx - 3, cy - 3, 6, 6)

    def _paint_arrow_preview(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor("#FF3333")
        p.setPen(QPen(color, 3, Qt.PenStyle.SolidLine,
                      Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(QBrush(color))
        p1 = _qpoint_to_f(self._drag_start)
        p2 = _qpoint_to_f(self._drag_end)
        p.drawLine(p1, p2)
        _draw_filled_arrow(p, p1, p2)

    def _paint_highlight_preview(self, p: QPainter) -> None:
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(255, 255, 0, 100)))
        p.setPen(QPen(QColor(255, 220, 0, 180), 1))
        p.drawRect(self._sel_rect())


# ── ImageEditorWindow ─────────────────────────────────────────────────────────

class ImageEditorWindow(QMainWindow):
    """
    Standalone image editor window.

    Parameters
    ----------
    image_source : QImage | QPixmap | bytes | bytearray | str | Path
    """

    def __init__(
        self,
        image_source,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._orig = self._load_image(image_source)
        if self._orig is None or self._orig.isNull():
            raise ValueError("ImageEditorWindow: could not load image from source.")

        self._text_color = QColor("#FFFF00")

        self.setWindowTitle(i18n.literal("Image Editor"))
        self.setMinimumSize(820, 620)   # Fix 9: bigger minimum so toolbar is always visible

        # Fix 10: apply app window icon
        try:
            from utils.config import ICON_APP
            icon_path = Path(ICON_APP)
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

        self._apply_style()
        self._build_toolbar()
        self._build_canvas()
        self._build_statusbar()
        self._bind_shortcuts()
        self._fit_window()
        translate_labels(self)

    # ── Image loading ─────────────────────────────────────────────────────────

    @staticmethod
    def _load_image(src) -> QImage | None:
        if isinstance(src, QImage):
            return src.copy()
        if isinstance(src, QPixmap):
            return src.toImage()
        if isinstance(src, (bytes, bytearray)):
            img = QImage()
            img.loadFromData(bytes(src))
            return img if not img.isNull() else None
        if isinstance(src, (str, Path)):
            img = QImage(str(src))
            return img if not img.isNull() else None
        return None

    # ── Styling ───────────────────────────────────────────────────────────────

    def _apply_style(self) -> None:
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background: {BG};
                color: {TEXT};
                font-family: 'Segoe UI', sans-serif;
            }}
            QScrollArea  {{ background: {BG}; border: none; }}
            QStatusBar   {{
                background: {BG_PANEL};
                color: {TEXT_DIM};
                font-size: 11px;
                border-top: 1px solid {BORDER};
            }}
            QToolBar {{
                background: {BG_PANEL};
                border-bottom: 1px solid {BORDER};
                spacing: 6px;
                padding: 6px 10px;
            }}
            QToolBar::separator {{ background: {BORDER}; width: 1px; margin: 4px 6px; }}
            QSpinBox {{
                background: {BG_HOVER};
                color: {TEXT};
                border: 1px solid {BORDER};
                border-radius: 5px;
                padding: 2px 4px;
                font-size: 12px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; }}
        """)

    # ── Toolbar ───────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> None:
        tb = QToolBar("Tools")
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(tb)

        # ── Tool buttons ──────────────────────────────────────────────────────
        def _tool_btn(label: str, tip: str) -> QToolButton:
            b = QToolButton()
            b.setText(label)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setStyleSheet(_TOOL_STYLE)
            return b

        self._btn_crop  = _tool_btn("✂  Crop",      "Crop to selection (drag)")
        self._btn_arrow = _tool_btn("↗  Arrow",     "Draw red arrow (drag)")
        self._btn_hl    = _tool_btn("🖊  Highlight", "Yellow highlight (drag)")
        self._btn_text  = _tool_btn("T  Text",      "Add text (click); drag to move; right-click to edit")

        for btn in (self._btn_crop, self._btn_arrow, self._btn_hl, self._btn_text):
            tb.addWidget(btn)

        self._btn_crop.setChecked(True)

        self._btn_crop.toggled.connect( lambda on: self._select_tool(TOOL_CROP,      on))
        self._btn_arrow.toggled.connect(lambda on: self._select_tool(TOOL_ARROW,     on))
        self._btn_hl.toggled.connect(   lambda on: self._select_tool(TOOL_HIGHLIGHT, on))
        self._btn_text.toggled.connect( lambda on: self._select_tool(TOOL_TEXT,      on))

        tb.addSeparator()

        # ── Text options ──────────────────────────────────────────────────────
        self._text_opts = QWidget()
        to_lay = QHBoxLayout(self._text_opts)
        to_lay.setContentsMargins(0, 0, 0, 0)
        to_lay.setSpacing(6)

        size_lbl = QLabel("Size:")
        size_lbl.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        to_lay.addWidget(size_lbl)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 120)
        self._size_spin.setValue(18)
        self._size_spin.setFixedWidth(60)
        self._size_spin.setToolTip("Font size (also applies to selected text)")
        self._size_spin.valueChanged.connect(self._on_font_size_changed)
        to_lay.addWidget(self._size_spin)

        self._color_btn = QPushButton("● Color")
        self._color_btn.setFixedHeight(30)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.setToolTip("Pick text colour (also applies to selected text)")
        self._color_btn.clicked.connect(self._pick_text_color)
        self._update_color_btn()
        to_lay.addWidget(self._color_btn)

        self._text_opts.setVisible(False)
        tb.addWidget(self._text_opts)

        tb.addSeparator()

        # ── Action buttons ────────────────────────────────────────────────────
        def _action_btn(label: str, tip: str, style: str) -> QPushButton:
            b = QPushButton(label)
            b.setFixedHeight(32)
            b.setToolTip(tip)
            b.setStyleSheet(style)
            return b

        self._btn_undo = _action_btn("↩  Undo",  "Undo last action  (Ctrl+Z)", _BTN_NEUTRAL)
        self._btn_undo.clicked.connect(self._undo)
        tb.addWidget(self._btn_undo)

        tb.addSeparator()

        btn_copy  = _action_btn("📋  Copy",  "Copy to clipboard  (Ctrl+C)", _BTN_NEUTRAL)
        btn_copy.clicked.connect(self._copy_to_clipboard)
        tb.addWidget(btn_copy)

        btn_save  = _action_btn("💾  Save",  "Save As…  (Ctrl+S)", _BTN_ACCENT)
        btn_save.clicked.connect(self._save_as)
        tb.addWidget(btn_save)

        btn_close = _action_btn("✕  Close", "Close editor", _BTN_DANGER)
        btn_close.clicked.connect(self.close)
        tb.addWidget(btn_close)

    # ── Canvas + scroll area ──────────────────────────────────────────────────

    def _build_canvas(self) -> None:
        self._canvas = _Canvas(self._orig, parent=self)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._canvas)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setStyleSheet(f"background: {BG}; border: none;")
        self.setCentralWidget(self._scroll)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._set_status(
            i18n.get("image_editor.status.ready", width=self._orig.width(), height=self._orig.height())
        )

    # ── Keyboard shortcuts ────────────────────────────────────────────────────

    def _bind_shortcuts(self) -> None:
        shortcuts = [
            ("Ctrl+Z", self._undo),
            ("Ctrl+S", self._save_as),
            ("Ctrl+C", self._copy_to_clipboard),
        ]
        for seq, slot in shortcuts:
            action = QAction(self)
            action.setShortcut(seq)
            action.triggered.connect(slot)
            self.addAction(action)

    # ── Tool selection ────────────────────────────────────────────────────────

    def _select_tool(self, tool: str, on: bool) -> None:
        if not on:
            return

        btn_map = {
            TOOL_CROP:      self._btn_crop,
            TOOL_ARROW:     self._btn_arrow,
            TOOL_HIGHLIGHT: self._btn_hl,
            TOOL_TEXT:      self._btn_text,
        }
        for t, btn in btn_map.items():
            if t != tool:
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)

        self._canvas.set_tool(tool)
        self._text_opts.setVisible(tool == TOOL_TEXT)

        hints = {
            TOOL_CROP:      i18n.get("image_editor.hints.crop"),
            TOOL_ARROW:     i18n.get("image_editor.hints.arrow"),
            TOOL_HIGHLIGHT: i18n.get("image_editor.hints.highlight"),
            TOOL_TEXT:      i18n.get("image_editor.hints.text"),
        }
        labels = {
            TOOL_CROP: i18n.get("image_editor.tools.crop"),
            TOOL_ARROW: i18n.get("image_editor.tools.arrow"),
            TOOL_HIGHLIGHT: i18n.get("image_editor.tools.highlight"),
            TOOL_TEXT: i18n.get("image_editor.tools.text"),
        }
        self._set_status(i18n.get("image_editor.status.tool_selected", tool=labels[tool], hint=hints[tool]))

    # ── Text colour ───────────────────────────────────────────────────────────

    def _pick_text_color(self) -> None:
        color = QColorDialog.getColor(self._text_color, self, i18n.literal("Pick Text Colour"))
        if color.isValid():
            self._text_color = color
            self._canvas.set_text_color(color)
            self._update_color_btn()

    def _update_color_btn(self) -> None:
        hex_c = self._text_color.name()
        luma  = (
            self._text_color.red()   * 299 +
            self._text_color.green() * 587 +
            self._text_color.blue()  * 114
        ) / 1000
        fg = "#000000" if luma > 128 else "#FFFFFF"
        self._color_btn.setStyleSheet(f"""
            QPushButton {{
                background: {hex_c}; color: {fg};
                border: 1px solid {BORDER}; border-radius: 7px;
                padding: 4px 12px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ border-color: {ACCENT}; }}
        """)

    def _on_font_size_changed(self, value: int) -> None:
        self._canvas.set_text_size(value)

    # Called by canvas when a text item's color is changed via context menu
    def _on_canvas_color_changed(self, color: QColor) -> None:
        self._text_color = color
        self._update_color_btn()

    # Called by canvas when a text item's size is changed via context menu
    def _on_canvas_size_changed(self, size: int) -> None:
        self._size_spin.blockSignals(True)
        self._size_spin.setValue(size)
        self._size_spin.blockSignals(False)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _undo(self) -> None:
        msg = self._canvas.undo()
        self._set_status(msg)
        self._btn_undo.setEnabled(self._canvas.undo_steps() > 0)

    def _copy_to_clipboard(self) -> None:
        pixmap = QPixmap.fromImage(self._canvas.flattened_image())
        QApplication.clipboard().setPixmap(pixmap)
        msg = i18n.get("notifications.image_copied")
        self._set_status(msg)
        self._flash_status(msg)

    def _flash_status(self, msg: str) -> None:
        """Briefly show a highlighted overlay label confirming the action."""
        lbl = QLabel(msg, self)
        lbl.setStyleSheet(
            "background:#6C63FF; color:white; border-radius:8px;"
            "font-family:'Segoe UI',sans-serif; font-size:12px; font-weight:700;"
            "padding:7px 20px;"
        )
        lbl.adjustSize()
        lbl.move((self.width() - lbl.width()) // 2, 60)
        lbl.show()
        lbl.raise_()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1200, lbl.deleteLater)

    def _save_as(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            i18n.get("image_editor.save_as"),
            "image.png",
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;BMP (*.bmp)",
        )
        if not path:
            return
        if self._canvas.flattened_image().save(path):
            self._set_status(i18n.get("image_editor.status.saved", path=path))
        else:
            message(self, i18n.get("image_editor.save_failed_title"), i18n.get("image_editor.save_failed_body", path=path))

    # ── Status bar helper ─────────────────────────────────────────────────────

    def _set_status(self, msg: str) -> None:
        steps = self._canvas.undo_steps()
        info = i18n.get("image_editor.status.undo_remaining", count=steps) if steps else ""
        self._status_bar.showMessage(f"  {msg}{info}")

    # ── Window sizing ─────────────────────────────────────────────────────────

    def _fit_window(self) -> None:
        screen = QApplication.primaryScreen().availableGeometry()
        w = min(self._orig.width()  + 24,  int(screen.width()  * 0.85))
        h = min(self._orig.height() + 120, int(screen.height() * 0.85))
        self.resize(max(w, 820), max(h, 620))


# ── Self-test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    test_img = QImage(680, 420, QImage.Format.Format_ARGB32)
    test_img.fill(QColor("#1A1D27"))

    p = QPainter(test_img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(ACCENT), 2))
    p.drawText(
        QRect(0, 0, 680, 420),
        Qt.AlignmentFlag.AlignCenter,
        "VeilClip Image Editor — Test Image (680 × 420)\n\n"
        "✂  Crop    ↗  Arrow    🖊  Highlight    T  Text\n\n"
        "Text tool: click to add, drag to move, right-click to edit/recolor.",
    )
    p.setPen(QPen(QColor("#FF3333"), 2))
    p.drawRect(40, 40, 220, 130)
    p.setPen(QPen(QColor("#33FF99"), 2))
    p.drawEllipse(420, 220, 190, 130)
    p.end()

    win = ImageEditorWindow(test_img)
    win.show()
    sys.exit(app.exec())
