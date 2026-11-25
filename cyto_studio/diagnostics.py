"""Session logs and user-facing reports for viewer failures."""

import datetime
from importlib.metadata import PackageNotFoundError, version
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
from tempfile import NamedTemporaryFile
import traceback

from cyto_studio.telemetry import log_event, wait_for_viewer

LOG_ENV = "CYTO_STUDIO_SESSION_LOG"
REPORT_HEADER_BYTES = 1500
REPORT_TAIL_BYTES = 4500


def run_viewer(args, virtualgl=False):
    """Keep the report process alive if Qt or the graphics driver aborts."""
    state = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
                 or Path.home() / ".local" / "state")
    logs = state / "cyto-studio" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=logs,
                            prefix=datetime.date.today().isoformat() + "-", suffix=".log",
                            delete=False) as log:
        log_path = Path(log.name)
        print(f"[cyto-studio] Session log: {log_path}", flush=True)
        print(f"Started {datetime.datetime.now().astimezone().isoformat()}", file=log)
        print(f"{platform.platform()} | Python {sys.version} | {sys.executable}", file=log)
        for package in ("cyto-studio", "napari", "vispy", "PySide6", "zarr"):
            try:
                print(f"{package} {version(package)}", file=log)
            except PackageNotFoundError:
                pass
        for key in ("DISPLAY", "XDG_SESSION_TYPE", "VGL_DISPLAY", "QT_API"):
            print(f"{key}={os.environ.get(key, '')}", file=log)
        runner = shutil.which("vglrun")
        if not runner and os.access("/opt/VirtualGL/bin/vglrun", os.X_OK):
            runner = "/opt/VirtualGL/bin/vglrun"
        command = [sys.executable, "-u", "-m", "cyto_studio", *args]
        if virtualgl and runner:
            command.insert(0, runner)
        print(f"Launch command: {command!r}", file=log, flush=True)

        if virtualgl and not runner:
            print("VirtualGL is required for the desktop launcher but vglrun was not found.", file=log)
            status = 1
        else:
            try:
                with subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                      env={**os.environ, LOG_ENV: str(log_path)}) as child:
                    status = wait_for_viewer(child, log)
            except OSError:
                traceback.print_exc(file=log)
                status = 1
        log_event(f"Viewer exit status: {status}", stream=log)
        if status < 0 and -status in signal.Signals._value2member_map_:
            log_event(f"Viewer termination signal: {signal.Signals(-status).name}", stream=log)
        if status == -getattr(signal, "SIGKILL", 9):
            log_event("SIGKILL does not identify its cause. Check the server kernel log "
                      "for an OOM kill matching the viewer PID and timestamp.", stream=log)
    if status:
        print(f"[cyto-studio] Viewer failed. Share this log: {log_path}", file=sys.stderr)
        if sys.platform == "win32" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            show_report_after_exit(log_path, status)
    return 128 - status if status < 0 else status


def show_report_after_exit(log_path, status):
    # Preload the conda runtime for reports launched directly from its Python,
    # where the desktop shell's library setup has not run.
    env = os.environ.copy()
    if sys.platform.startswith("linux"):
        lib = str(Path(sys.prefix) / "lib")
        inherited = env.get("LD_LIBRARY_PATH")
        env["LD_LIBRARY_PATH"] = f"{lib}:{inherited}" if inherited else lib
    result = subprocess.run([sys.executable, "-m", __name__, str(log_path), str(status)],
                            env=env, check=False)
    if result.returncode and (zenity := shutil.which("zenity")):
        # Use the host's GTK libraries, independent of Qt and conda.
        env = os.environ.copy()
        env.pop("LD_LIBRARY_PATH", None)
        subprocess.run([zenity, "--text-info", "--title=Cyto Studio error report",
                        f"--filename={log_path}", "--width=720", "--height=480"],
                       env=env, check=False)


def copyable_report(log_path):
    """Return a short excerpt with session context and the latest diagnostics."""
    with log_path.open("rb") as log:
        size = log.seek(0, os.SEEK_END)
        log.seek(0)
        if size <= REPORT_HEADER_BYTES + REPORT_TAIL_BYTES:
            return log.read().decode("utf-8", errors="replace")
        header = log.read(REPORT_HEADER_BYTES).rsplit(b"\n", 1)[0]
        log.seek(size - REPORT_TAIL_BYTES)
        tail = log.read().partition(b"\n")[2]
    notice = b"\n\n[Earlier log entries omitted. Attach the log file for the full report.]\n\n"
    return (header + notice + tail).decode("utf-8", errors="replace")


def report_dialog(log_path, message):
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtWidgets import QApplication, QMessageBox

    dialog = QMessageBox()
    dialog.setWindowTitle("Cyto Studio error report")
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setText(message)
    dialog.setInformativeText(f"Copy a short report or share the full log file:\n{log_path}")
    dialog.setStandardButtons(QMessageBox.StandardButton.Close)
    copy = dialog.addButton("Copy report", QMessageBox.ButtonRole.ActionRole)
    copy.clicked.connect(lambda: QApplication.clipboard().setText(copyable_report(log_path)))
    folder = dialog.addButton("Open log folder", QMessageBox.ButtonRole.ActionRole)
    folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path.parent))))
    return dialog


def show_crash_report(log_path, status):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    dialog = report_dialog(log_path, f"Cyto Studio stopped unexpectedly (exit status {status}).")
    dialog.exec()


def install_viewer_reporting():
    """Record errors handled inside Napari and offer a report on the GUI thread."""
    from napari.utils.notifications import ErrorNotification, notification_manager
    from PySide6.QtCore import QObject, Qt, Signal, Slot

    log_path = Path(os.environ[LOG_ENV])
    seen = set()

    class Reporter(QObject):
        error_found = Signal()

        def __init__(self):
            super().__init__()
            self.dialog = None
            self.error_found.connect(self.show, Qt.ConnectionType.QueuedConnection)

        @Slot()
        def show(self):
            if self.dialog is None:
                self.dialog = report_dialog(log_path, "Cyto Studio encountered an error.")
                self.dialog.show()

        def record(self, notification):
            if isinstance(notification, ErrorNotification):
                error = notification.exception
                # Qt can wrap the same underlying rendering error on every repaint.
                key = (type(error), str(error).rsplit("Error calling Python override of ", 1)[-1])
                if key not in seen and len(seen) < 30:
                    seen.add(key)
                    print(f"\n[{datetime.datetime.now().astimezone().isoformat()}] Viewer error",
                          file=sys.stderr, flush=True)
                    traceback.print_exception(error, file=sys.stderr)
                    self.error_found.emit()

    reporter = Reporter()
    notification_manager.notification_ready.connect(reporter.record)
    return reporter


if __name__ == "__main__":
    show_crash_report(Path(sys.argv[1]), int(sys.argv[2]))
