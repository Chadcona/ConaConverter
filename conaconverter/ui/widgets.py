"""DropZoneWidget — a drag-and-drop area that also supports click-to-browse."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import QFileDialog, QLabel, QMenu, QSizePolicy


class DropZoneWidget(QLabel):
    """A label that accepts file drops and emits file_dropped(path: str)."""

    file_dropped = Signal(str)

    _STYLE_IDLE = """
        DropZoneWidget {
            border: 2px dashed #555;
            border-radius: 8px;
            color: #888;
            background-color: #1a1a1a;
            font-size: 14px;
        }
    """

    _STYLE_HOVER = """
        DropZoneWidget {
            border: 2px dashed #4fc3f7;
            border-radius: 8px;
            color: #4fc3f7;
            background-color: #1e2a30;
            font-size: 14px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setText("Drop playlist file here\nor click to browse")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True)
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(self._STYLE_IDLE)

    # ------------------------------------------------------------------
    # Drag-and-drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._STYLE_HOVER)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._STYLE_IDLE)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self._STYLE_IDLE)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.file_dropped.emit(path)

    # ------------------------------------------------------------------
    # Click to browse
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            menu = QMenu(self)
            menu.addAction("Browse for file…", self._open_browse_dialog)
            menu.addAction("Browse for folder (Engine OS)…", self._open_folder_dialog)
            menu.exec(event.globalPosition().toPoint())

    def _open_browse_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open playlist file",
            "",
            "DJ Playlist Files (*.crate *.xml *.db *.nml);;"
            "Serato Crate (*.crate);;"
            "Rekordbox / VirtualDJ XML (*.xml);;"
            "Traktor NML (*.nml);;"
            "Engine OS Database (*.db);;"
            "All Files (*)",
        )
        if path:
            self.file_dropped.emit(path)

    def _open_folder_dialog(self) -> None:
        """Browse for an Engine OS library folder."""
        path = QFileDialog.getExistingDirectory(
            self,
            "Open Engine OS library folder",
            "",
        )
        if path:
            self.file_dropped.emit(path)
