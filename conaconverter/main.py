"""ConaConverter entry point."""

import sys

from PySide6.QtWidgets import QApplication

from conaconverter.ui.mainwindow import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ConaConverter")
    app.setOrganizationName("ConaConverter")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
