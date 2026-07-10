import sys
import os
import platform
import shutil
import subprocess
from importlib.metadata import distribution, PackageNotFoundError


LINUX_CONDA_SH = "/opt/conda/etc/profile.d/conda.sh"
LINUX_CONDA_ENV = "/storage/scratch.space/envs/cyto-studio-env"


def _linux_xcb_cursor_available() -> bool:
    prefix = os.environ.get("CONDA_PREFIX", LINUX_CONDA_ENV)
    for lib_name in ("libxcb-cursor.so.0", "libxcb-cursor.so"):
        if os.path.exists(os.path.join(prefix, "lib", lib_name)):
            return True

    try:
        import ctypes
        ctypes.CDLL("libxcb-cursor.so.0")
        return True
    except OSError:
        return False


def _ensure_linux_qt_runtime() -> bool:
    if _linux_xcb_cursor_available():
        return True

    conda = shutil.which("conda")
    if not conda:
        print("[cyto-studio] Missing Qt runtime library: libxcb-cursor.so.0")
        print("[cyto-studio] Install it with:")
        print("    conda install -y -c conda-forge xcb-util-cursor")
        return False

    print("[cyto-studio] Installing missing Qt runtime package: xcb-util-cursor")
    try:
        subprocess.check_call([
            conda,
            "install",
            "-y",
            "-p",
            LINUX_CONDA_ENV,
            "-c",
            "conda-forge",
            "xcb-util-cursor",
        ])
    except subprocess.CalledProcessError:
        print("[cyto-studio] Failed to install xcb-util-cursor.")
        print("[cyto-studio] Install it manually with:")
        print("    conda install -y -c conda-forge xcb-util-cursor")
        return False

    return _linux_xcb_cursor_available()


def create_launcher() -> int:
    try:
        if platform.system() == "Windows":
            print("[cyto-studio] Windows launcher creation is not supported here yet.")
            print("[cyto-studio] Run Cyto Studio from an activated environment with:")
            print("    python -m cyto_studio")
            return 1

        if platform.system() != "Linux":
            print(f"[cyto-studio] Launcher creation is not supported on {platform.system()} yet.")
            return 1

        home = os.path.expanduser("~")
        script_path = os.path.join(home, ".local", "bin", "launch_cyto_studio.sh")
        desktop_path = os.path.join(home, "Desktop", "CytoStudio.desktop")

        print("[cyto-studio] Creating launcher...")

        if not os.path.exists(LINUX_CONDA_SH):
            print(f"[cyto-studio] Conda setup script not found at: {LINUX_CONDA_SH}")
            return 1

        _ensure_linux_qt_runtime()

        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        os.makedirs(os.path.dirname(desktop_path), exist_ok=True)

        # Write the shell script
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(f"""#!/bin/bash
set -u

pause_on_error() {{
    status="$1"

    if [ "$status" -ne 0 ]; then
        echo
        echo "[cyto-studio] Cyto Studio exited with error code: $status"
        echo "[cyto-studio] The terminal will stay open for debugging."
        echo
        read -r -p "Press Enter to close this terminal..."
    fi

    exit "$status"
}}

source "{LINUX_CONDA_SH}"
conda activate "{LINUX_CONDA_ENV}"

# Avoid Qt/C++ ABI conflicts from the host environment
unset LD_LIBRARY_PATH
unset QT_PLUGIN_PATH
unset QML2_IMPORT_PATH
unset QT_QPA_PLATFORM_PLUGIN_PATH
export QT_API=pyside6
if [ "${{QT_DEBUG_PLUGINS:-}}" != "1" ]; then
    export QT_LOGGING_RULES="${{QT_LOGGING_RULES:-*.debug=false}}"
fi

# Keep conda's Qt/XCB runtime libraries available, then add NVIDIA libs for vglrun.
export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64"

# Ensure PySide6's Qt libs are found first
PYSIDE_LIB_PATH=$(python - <<'PY'
import os
import site
for site_dir in site.getsitepackages():
    candidate = os.path.join(site_dir, "PySide6", "Qt", "lib")
    if os.path.isdir(candidate):
        print(candidate)
        break
PY
)

if [ -n "$PYSIDE_LIB_PATH" ]; then
    export LD_LIBRARY_PATH="$PYSIDE_LIB_PATH:$LD_LIBRARY_PATH"
fi

python - <<'PY'
import ctypes
import sys
try:
    ctypes.CDLL("libxcb-cursor.so.0")
except OSError:
    sys.exit(1)
PY

if [ "$?" -ne 0 ]; then
    echo "[cyto-studio] Installing missing Qt runtime package: xcb-util-cursor"
    conda install -y -p "{LINUX_CONDA_ENV}" -c conda-forge xcb-util-cursor
    install_status=$?
    if [ "$install_status" -ne 0 ]; then
        echo "[cyto-studio] Could not install xcb-util-cursor automatically."
        echo "[cyto-studio] Run this command in the cyto-studio environment:"
        echo "    conda install -y -c conda-forge xcb-util-cursor"
        pause_on_error "$install_status"
    fi
fi

echo "[cyto-studio] Python: $(command -v python)"
echo "[cyto-studio] Environment: $CONDA_PREFIX"

if command -v vglrun >/dev/null 2>&1; then
    echo "[cyto-studio] Trying VirtualGL launch: vglrun python -m cyto_studio"
    vglrun python -m cyto_studio "$@"
    vgl_status=$?

    if [ "$vgl_status" -eq 0 ]; then
        exit 0
    fi

    echo
    echo "[cyto-studio] VirtualGL launch failed with code: $vgl_status"
    echo "[cyto-studio] Falling back to normal launch: python -m cyto_studio"
    echo
else
    echo "[cyto-studio] vglrun not found; launching without VirtualGL"
fi

python -m cyto_studio "$@"
cyto_status=$?

pause_on_error "$cyto_status"
""")
        os.chmod(script_path, 0o755)

        # Try to find icon.png in the installed package
        try:
            import cyto_studio
            icon_path = os.path.join(os.path.dirname(cyto_studio.__file__), "icon.png")
            if not os.path.exists(icon_path):
                raise FileNotFoundError
        except Exception:
            icon_path = "utilities-terminal"

        # Write the .desktop file
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Cyto Studio
Comment=Launch Cyto Studio Viewer
Exec=bash -lc "{script_path}"
Icon={icon_path}
Terminal=true
""")
        os.chmod(desktop_path, 0o755)

        print(f"[cyto-studio] Launcher created at: {desktop_path}")
        return 0

    except Exception as e:
        print(f"[cyto-studio] Failed to create launcher: {e}")
        return 1


def main() -> int:
    # Handle launcher creation BEFORE any GUI code
    if "--create-launcher" in sys.argv:
        return create_launcher()

    # Ensure Qt bindings resolve to PySide6 (Qt6) before napari/qtpy import.
    os.environ.setdefault("QT_API", "pyside6")

    # On Windows, set an explicit AppUserModelID before the GUI is created so the
    # taskbar/title-bar shows the app's own icon instead of the generic Python icon.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "TristanWhitmarsh.cyto-studio"
            )
        except Exception:
            pass

    # Runtime guard against opencv-python (Qt conflicts)
    try:
        distribution("opencv-python")
        print(
            "\n[cyto-studio] Detected 'opencv-python', which is incompatible with napari and PySide6.\n"
            "This can cause Qt-related crashes or weird behavior.\n"
            "\nTo fix this, run:\n"
            "    pip uninstall opencv-python\n"
            "    pip install opencv-python-headless\n"
        )
        return 1
    except PackageNotFoundError:
        pass

    # GUI code
    from cyto_studio.cyto_studio import CYTOSTUDIO

    print("Using PySide6")
    napari = CYTOSTUDIO()
    napari.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
