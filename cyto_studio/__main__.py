import sys
import os

# Handle launcher creation BEFORE any GUI code
if "--create-launcher" in sys.argv:
    try:
        home = os.path.expanduser("~")
        venv_activate_path = os.path.join(home, "Python", "cyto-studio", "bin", "activate")
        script_path = os.path.join(home, ".local", "bin", "launch_cyto_studio.sh")
        desktop_path = os.path.join(home, "Desktop", "CytoStudio.desktop")

        print("[cyto-studio] Creating launcher...")

        if not os.path.exists(venv_activate_path):
            print(f"[cyto-studio] Virtualenv not found at: {venv_activate_path}")
            sys.exit(1)

        os.makedirs(os.path.dirname(script_path), exist_ok=True)
        os.makedirs(os.path.dirname(desktop_path), exist_ok=True)

        # Write the shell script
        with open(script_path, "w") as f:
            f.write(f"""#!/bin/bash
source "{venv_activate_path}"
PYSIDE_LIB_PATH=$(python -c "import site; import os; print(os.path.join(site.getsitepackages()[0], 'PySide2', 'Qt', 'lib'))")
export LD_LIBRARY_PATH="$PYSIDE_LIB_PATH:$LD_LIBRARY_PATH"
vglrun cyto-studio
""")
        os.chmod(script_path, 0o755)

        # Try to find logo.png in the installed package
        try:
            import cyto_studio
            icon_path = os.path.join(os.path.dirname(cyto_studio.__file__), "icon.png")
            if not os.path.exists(icon_path):
                raise FileNotFoundError
        except Exception:
            icon_path = "utilities-terminal"  # fallback if logo not found

        # Write the .desktop file
        with open(desktop_path, "w") as f:
            f.write(f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Cyto Studio
Comment=Launch Cyto Studio Viewer
Exec=x-terminal-emulator -e bash -c "{script_path}; exec bash"
Icon={icon_path}
Terminal=true
""")
        os.chmod(desktop_path, 0o755)

        print(f"[cyto-studio] Launcher created at: {desktop_path}")
        sys.exit(0)

    except Exception as e:
        print(f"[cyto-studio] ❌ Failed to create launcher: {e}")
        sys.exit(1)

# Only runs if not creating launcher
import pkg_resources

try:
    pkg_resources.get_distribution("opencv-python")
    print(
        "\n[cyto-studio] Detected 'opencv-python', which is incompatible with napari and PySide2.\n"
        "This can cause Qt-related crashes or weird behavior.\n"
        "\n To fix this, run:\n"
        "    pip uninstall opencv-python\n"
        "    pip install numpy==1.23.5 opencv-python-headless==4.10.0.82\n"
    )
    sys.exit(1)
except pkg_resources.DistributionNotFound:
    pass

# GUI code goes here AFTER --create-launcher check
try:
    # Works after pip install
    from cyto_studio.cyto_studio import CYTOSTUDIO
except ImportError:
    # Works when running __main__.py directly in local dev
    from cyto_studio import CYTOSTUDIO

print("Using PySide2")
napari = CYTOSTUDIO()
napari.main()
