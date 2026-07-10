import sys
import os
from importlib.metadata import distribution, PackageNotFoundError


def create_launcher() -> int:
    try:
        home = os.path.expanduser("~")
        venv_activate_path = os.path.join(home, "Python", "cyto-studio", "bin", "activate")
        script_path = os.path.join(home, ".local", "bin", "launch_cyto_studio.sh")
        desktop_path = os.path.join(home, "Desktop", "CytoStudio.desktop")

        print("[cyto-studio] Creating launcher...")

        if not os.path.exists(venv_activate_path):
            print(f"[cyto-studio] Virtualenv not found at: {venv_activate_path}")
            return 1

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

source "{venv_activate_path}"

# Avoid Qt/C++ ABI conflicts from the host environment
unset LD_LIBRARY_PATH
unset QT_PLUGIN_PATH
unset QML2_IMPORT_PATH
export QT_API=pyside6

# If you need NVIDIA libs for vglrun, add them back explicitly:
export LD_LIBRARY_PATH="/usr/local/nvidia/lib:/usr/local/nvidia/lib64"

# Ensure PySide6's Qt libs are found first
PYSIDE_LIB_PATH=$(python -c "import site, os; print(os.path.join(site.getsitepackages()[0], 'PySide6', 'Qt', 'lib'))")
export LD_LIBRARY_PATH="$PYSIDE_LIB_PATH:$LD_LIBRARY_PATH"

echo "[cyto-studio] Trying VirtualGL launch: vglrun cyto-studio"

vglrun cyto-studio "$@"
vgl_status=$?

if [ "$vgl_status" -eq 0 ]; then
    exit 0
fi

echo
echo "[cyto-studio] VirtualGL launch failed with code: $vgl_status"
echo "[cyto-studio] Falling back to normal launch: cyto-studio"
echo

cyto-studio "$@"
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
Exec=x-terminal-emulator -e bash -c "{script_path}"
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
