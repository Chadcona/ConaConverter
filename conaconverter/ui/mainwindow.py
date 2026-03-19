"""Main application window for ConaConverter."""

from __future__ import annotations

import os
import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import QUrl

from conaconverter import __version__
from conaconverter.converters import FORMAT_LABELS, READERS, WRITERS
from conaconverter.detector import detect_format
from conaconverter.ui.widgets import DropZoneWidget


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class _WorkerSignals(QObject):
    finished = Signal(str)   # output path
    error    = Signal(str)   # error message


class _ConvertWorker(QRunnable):
    def __init__(self, input_path: str, source_fmt: str,
                 target_fmt: str, output_path: str):
        super().__init__()
        self._input_path  = input_path
        self._source_fmt  = source_fmt
        self._target_fmt  = target_fmt
        self._output_path = output_path
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            playlist = READERS[self._source_fmt].read(self._input_path)
            WRITERS[self._target_fmt].write(playlist, self._output_path)
            self.signals.finished.emit(self._output_path)
        except Exception:
            self.signals.error.emit(traceback.format_exc())


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

_APP_STYLE = """
QMainWindow, QWidget#central {
    background-color: #121212;
}
QLabel#status {
    color: #aaa;
    font-size: 12px;
}
QComboBox {
    background-color: #1e1e1e;
    color: #eee;
    border: 1px solid #444;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
    min-height: 28px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e1e;
    color: #eee;
    selection-background-color: #333;
}
QPushButton#convert_btn {
    background-color: #1565c0;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 14px;
    font-weight: bold;
    padding: 10px 20px;
    min-height: 40px;
}
QPushButton#convert_btn:disabled {
    background-color: #333;
    color: #666;
}
QPushButton#convert_btn:hover:!disabled {
    background-color: #1976d2;
}
QPushButton#convert_btn:pressed {
    background-color: #0d47a1;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"ConaConverter v{__version__}")
        self.setMinimumSize(480, 380)
        self.resize(520, 420)
        self.setStyleSheet(_APP_STYLE)

        self._input_path: str | None = None
        self._source_fmt: str | None = None

        # ---- Central widget ----
        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Drop zone
        self._drop_zone = DropZoneWidget()
        self._drop_zone.file_dropped.connect(self._on_file_dropped)
        layout.addWidget(self._drop_zone)

        # Target format label + combo
        target_label = QLabel("Convert to:")
        target_label.setStyleSheet("color: #ccc; font-size: 13px;")
        layout.addWidget(target_label)

        self._format_combo = QComboBox()
        for key, label in FORMAT_LABELS.items():
            self._format_combo.addItem(label, userData=key)
        layout.addWidget(self._format_combo)

        # Convert button
        self._convert_btn = QPushButton("Convert", objectName="convert_btn")
        self._convert_btn.setEnabled(False)
        self._convert_btn.clicked.connect(self._on_convert_clicked)
        layout.addWidget(self._convert_btn)

        # Status label
        self._status = QLabel("Ready", objectName="status")
        layout.addWidget(self._status)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_file_dropped(self, path: str) -> None:
        self._input_path = path
        try:
            self._source_fmt = detect_format(path)
            fmt_label = FORMAT_LABELS.get(self._source_fmt, self._source_fmt)
            if path.startswith("assetlist://") or path.startswith("serato-sqlite://"):
                display_name = "Serato crate (drag-and-drop)"
            else:
                display_name = os.path.basename(path)
            self._status.setText(f"Detected: {fmt_label}  —  {display_name}")
            self._convert_btn.setEnabled(True)
        except ValueError as exc:
            self._status.setText(f"Error: {exc}")
            self._convert_btn.setEnabled(False)

    @Slot()
    def _on_convert_clicked(self) -> None:
        if not self._input_path or not self._source_fmt:
            return

        target_fmt: str = self._format_combo.currentData()

        if target_fmt == self._source_fmt:
            QMessageBox.information(
                self, "Same format",
                "Source and target formats are the same. Nothing to convert."
            )
            return

        # Warn before writing Serato (modifies audio files)
        if target_fmt == "serato":
            reply = QMessageBox.warning(
                self,
                "Serato write warning",
                "Writing Serato format will embed cue/grid data directly into "
                "your audio files.\n\nMake sure you have a backup before proceeding.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
                return

        output_path = self._build_output_path(self._input_path, target_fmt)

        self._convert_btn.setEnabled(False)
        self._status.setText("Converting…")

        worker = _ConvertWorker(
            input_path=self._input_path,
            source_fmt=self._source_fmt,
            target_fmt=target_fmt,
            output_path=output_path,
        )
        worker.signals.finished.connect(self._on_conversion_finished)
        worker.signals.error.connect(self._on_conversion_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _on_conversion_finished(self, output_path: str) -> None:
        self._convert_btn.setEnabled(True)
        self._status.setText(f"Done: {os.path.basename(output_path)}")
        # Open the containing folder
        folder = output_path if os.path.isdir(output_path) else os.path.dirname(output_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    @Slot(str)
    def _on_conversion_error(self, message: str) -> None:
        self._convert_btn.setEnabled(True)
        self._status.setText("Conversion failed — see error dialog")
        QMessageBox.critical(self, "Conversion error", message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_output_path(self, input_path: str, target_fmt: str) -> str:
        """Derive the output path from the input path and target format."""
        _EXTENSIONS = {
            "rekordbox": ".xml",
            "virtualdj": ".xml",
            "serato":    ".crate",
            "engineos":  "",   # Engine OS is a folder
            "traktor":   ".nml",
        }

        # For Serato URIs, place output on the Desktop with a generic name
        if input_path.startswith("assetlist://") or input_path.startswith("serato-sqlite://"):
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            base = os.path.join(desktop, "serato_export")
        else:
            base = os.path.splitext(input_path)[0]

        ext  = _EXTENSIONS.get(target_fmt, "")
        suffix = f"_{target_fmt}"

        if target_fmt == "engineos":
            return base + suffix  # folder
        return base + suffix + ext
