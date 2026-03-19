"""DropZoneWidget — a drag-and-drop area that also supports click-to-browse."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QLabel, QListWidget,
    QListWidgetItem, QMenu, QSizePolicy, QVBoxLayout,
)


def _serato_crates_dir() -> str | None:
    """Return the Serato SubCrates folder if it exists."""
    if sys.platform == "win32":
        music = os.path.join(os.path.expanduser("~"), "Music")
    else:
        music = os.path.join(os.path.expanduser("~"), "Music")
    crates = os.path.join(music, "_Serato_", "SubCrates")
    return crates if os.path.isdir(crates) else None


def _rekordbox_xml_dir() -> str | None:
    """Return a likely Rekordbox XML export folder if it exists."""
    if sys.platform == "win32":
        base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming",
                            "Pioneer", "rekordbox")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library",
                            "Pioneer", "rekordbox")
    else:
        base = os.path.join(os.path.expanduser("~"), ".pioneer", "rekordbox")
    return base if os.path.isdir(base) else None


def _traktor_dir() -> str | None:
    """Return the Traktor collection folder if it exists."""
    if sys.platform == "win32":
        base = os.path.join(os.path.expanduser("~"), "Documents",
                            "Native Instruments", "Traktor")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Documents",
                            "Native Instruments", "Traktor")
    else:
        base = os.path.join(os.path.expanduser("~"), "Documents",
                            "Native Instruments", "Traktor")
    # Find the versioned subfolder (e.g. "Traktor 3.x.x")
    if os.path.isdir(base):
        for entry in sorted(os.listdir(base), reverse=True):
            full = os.path.join(base, entry)
            if os.path.isdir(full) and entry.lower().startswith("traktor"):
                return full
        return base
    return None


def _try_resolve_serato_text(text: str) -> str | None:
    """If *text* looks like a Serato crate name, return the .crate file path."""
    crates_dir = _serato_crates_dir()
    if not crates_dir:
        return None
    # Serato uses %% for nested crate separators in filenames
    name = text.strip().replace("/", "%%").replace("\\", "%%")
    candidate = os.path.join(crates_dir, name + ".crate")
    if os.path.isfile(candidate):
        return candidate
    # Try as-is (user might have dropped the actual filename)
    candidate = os.path.join(crates_dir, text.strip())
    if os.path.isfile(candidate):
        return candidate
    return None


class _SeratoCratePicker(QDialog):
    """Dialog that lists Serato crates and lets the user pick one."""

    def __init__(self, crates: list[tuple[int, str, str]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Serato Crate")
        self.setMinimumSize(340, 300)
        self.selected_db: str | None = None
        self.selected_id: int | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Which crate did you want to convert?"))

        self._list = QListWidget()
        for container_id, name, db_path in crates:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, (container_id, db_path))
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._list)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        item = self._list.currentItem()
        if item:
            self.selected_id, self.selected_db = item.data(Qt.ItemDataRole.UserRole)
            self.accept()

    def _on_double_click(self, item: QListWidgetItem) -> None:
        self.selected_id, self.selected_db = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


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
        # Accept URLs, text, and Serato's proprietary MIME types
        event.acceptProposedAction()
        self.setStyleSheet(self._STYLE_HOVER)

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._STYLE_IDLE)

    def dropEvent(self, event: QDropEvent) -> None:
        self.setStyleSheet(self._STYLE_IDLE)
        md = event.mimeData()

        # Serato drag-and-drop: sends text/vnd.serato.library.crate_uri
        # with value like "assetlist://container/779"
        # The ID is a session-internal ID that doesn't match the SQLite row ID,
        # so we show a crate picker dialog instead.
        _SERATO_CRATE_MIME = "text/vnd.serato.library.crate_uri"
        if _SERATO_CRATE_MIME in md.formats():
            self._show_serato_crate_picker()
            return

        # Try file URLs first (e.g. dragged from File Explorer)
        if md.hasUrls():
            urls = md.urls()
            if urls:
                path = urls[0].toLocalFile()
                if path:
                    self.file_dropped.emit(path)
                    return

        # Try text — might be a file path or a Serato crate name
        if md.hasText():
            text = md.text().strip()
            if os.path.exists(text):
                self.file_dropped.emit(text)
                return
            resolved = _try_resolve_serato_text(text)
            if resolved:
                self.file_dropped.emit(resolved)

    # ------------------------------------------------------------------
    # Click to browse
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            menu = QMenu(self)

            # Smart shortcuts for detected DJ software
            serato_dir = _serato_crates_dir()
            if serato_dir:
                menu.addAction("Serato Crates…",
                               lambda d=serato_dir: self._open_browse_dialog(d or "", "Serato Crate (*.crate)"))

            rb_dir = _rekordbox_xml_dir()
            if rb_dir:
                menu.addAction("Rekordbox XML…",
                               lambda d=rb_dir: self._open_browse_dialog(d or "", "Rekordbox XML (*.xml)"))

            traktor_dir = _traktor_dir()
            if traktor_dir:
                menu.addAction("Traktor Collection…",
                               lambda d=traktor_dir: self._open_browse_dialog(d or "", "Traktor NML (*.nml)"))

            if serato_dir or rb_dir or traktor_dir:
                menu.addSeparator()

            menu.addAction("Browse for file…", self._open_browse_dialog)
            menu.addAction("Browse for folder (Engine OS)…", self._open_folder_dialog)
            menu.exec(event.globalPosition().toPoint())

    def _open_browse_dialog(self, start_dir: str = "", file_filter: str = "") -> None:
        if not file_filter:
            file_filter = (
                "DJ Playlist Files (*.crate *.xml *.db *.nml);;"
                "Serato Crate (*.crate);;"
                "Rekordbox / VirtualDJ XML (*.xml);;"
                "Traktor NML (*.nml);;"
                "Engine OS Database (*.db);;"
                "All Files (*)"
            )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open playlist file",
            start_dir,
            file_filter,
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

    def _show_serato_crate_picker(self) -> None:
        """Show a dialog listing all Serato crates from SQLite databases."""
        from conaconverter.converters.serato import (
            _find_serato_sqlite,
            _list_containers_from_sqlite,
        )

        all_crates: list[tuple[int, str, str]] = []
        for db_path in _find_serato_sqlite():
            for cid, name, parent_id in _list_containers_from_sqlite(db_path):
                all_crates.append((cid, name, db_path))

        if not all_crates:
            return

        picker = _SeratoCratePicker(all_crates, parent=self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.selected_id is not None:
            # Build a serato-sqlite:// URI that the reader can resolve
            uri = f"serato-sqlite://{picker.selected_db}?container={picker.selected_id}"
            self.file_dropped.emit(uri)
