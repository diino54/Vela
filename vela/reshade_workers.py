"""Background ReShade I/O. Results are delivered to GUI slots via queued signals."""

from PySide6.QtCore import QThread, Signal

from . import reshade


class InstallWorker(QThread):
    progress = Signal(str)
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, plan, remove=False, parent=None, complete=False):
        super().__init__(parent)
        self.plan, self.remove = plan, remove
        self.complete = complete

    def run(self):
        try:
            result = (
                reshade.uninstall(self.plan.executable, complete=self.complete)
                if self.remove
                else reshade.install(self.plan, self.progress.emit)
            )
            self.result.emit(result)
        except Exception as error:
            self.failed.emit(str(error))


class LibraryWorker(QThread):
    result = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.result.emit(reshade.steam_games())
        except Exception as error:
            self.failed.emit(str(error))
