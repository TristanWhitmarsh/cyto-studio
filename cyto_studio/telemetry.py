"""Record rendering activity and resource usage for crash diagnosis."""

from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import time

import psutil


MIB = 1024 ** 2
MEMORY_INTERVAL = 5
GPU_INTERVAL = 10


def log_event(message, *, stream=None):
    print(f"[{datetime.now().astimezone().isoformat(timespec='milliseconds')}] {message}",
          file=stream or sys.stderr, flush=True)


def cgroup_memory_events(pid):
    """Read Linux cgroup v2 counters when the viewer's cgroup is visible."""
    try:
        for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                path = Path("/sys/fs/cgroup") / line[3:].lstrip("/") / "memory.events"
                counters = dict(row.split() for row in path.read_text().splitlines())
                return path, {key: int(counters[key]) for key in ("oom", "oom_kill")
                              if key in counters}
    except (OSError, ValueError):
        pass
    return None, {}


def nvidia_memory(executable):
    try:
        result = subprocess.run(
            [executable, "--query-gpu=index,name,memory.used,memory.free,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2, check=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return (), f"NVIDIA GPU memory unavailable: {error}"
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    free = []
    for row in rows:
        columns = row.rsplit(",", 2)
        if len(columns) == 3 and columns[1].strip().isdigit():
            free.append((row.split(",", 1)[0], int(columns[1])))
    return free, f"NVIDIA memory (index, GPU, used, free, total MiB; all users): " + (
        " | ".join(rows) or "unavailable")


def gpu_memory_changed(previous, current):
    before, old_message = previous
    after, message = current
    if not before or not after:
        return message != old_message
    return (len(before) != len(after) or
            any(old_id != new_id or abs(new - old) >= 256 or (old < 512) != (new < 512)
                for (old_id, old), (new_id, new) in zip(before, after)))


def wait_for_viewer(child, log):
    """Sample outside Qt so a viewer failure cannot erase earlier readings."""
    gpu_tool = shutil.which("nvidia-smi")
    if not gpu_tool:
        log_event("NVIDIA adapter memory unavailable (nvidia-smi not found)", stream=log)
    cgroup_path, initial = cgroup_memory_events(child.pid)
    if cgroup_path:
        log_event(f"Initial shared cgroup memory counters: {initial}", stream=log)

    next_gpu = 0.0
    peak = 0
    last_ram = last_gpu = None
    ram_message = gpu_message = None
    logged_ram = logged_gpu = None
    ram_error_logged = False
    while child.poll() is None:
        try:
            rss = psutil.Process(child.pid).memory_info().rss // MIB
            peak = max(peak, rss)
            host = psutil.virtual_memory()
            swap = psutil.swap_memory()
            available, swapped = host.available // MIB, swap.used // MIB
            ram = (rss, available, swapped, peak)
            ram_message = (f"Memory: viewer PID {child.pid} RSS {rss} MiB "
                           f"(sampled peak {peak} MiB); host RAM free {available} MiB; "
                           f"swap used {swapped} MiB")
            if last_ram is None or any(
                abs(new - old) >= limit
                for old, new, limit in zip(last_ram, ram, (256, 1024, 256, 256))
            ):
                log_event(ram_message, stream=log)
                last_ram, logged_ram = ram, ram_message
        except (OSError, psutil.Error) as error:
            if not ram_error_logged:
                log_event(f"RAM sample unavailable: {error}", stream=log)
                ram_error_logged = True

        if gpu_tool and time.monotonic() >= next_gpu:
            gpu = nvidia_memory(gpu_tool)
            gpu_message = gpu[1]
            if last_gpu is None or gpu_memory_changed(last_gpu, gpu):
                log_event(gpu_message, stream=log)
                last_gpu, logged_gpu = gpu, gpu_message
            next_gpu = time.monotonic() + GPU_INTERVAL
        try:
            child.wait(timeout=MEMORY_INTERVAL)
        except subprocess.TimeoutExpired:
            continue

    if child.returncode:
        for latest, logged in ((ram_message, logged_ram), (gpu_message, logged_gpu)):
            if latest and latest != logged:
                log_event(f"Last sample before exit: {latest}", stream=log)
    if cgroup_path:
        try:
            counters = dict(row.split() for row in cgroup_path.read_text().splitlines())
            delta = {key: int(counters[key]) - count for key, count in initial.items()
                     if key in counters}
            log_event(f"Shared cgroup memory counter changes: {delta}", stream=log)
        except (OSError, ValueError):
            pass
    return child.returncode


def connect_viewer_activity(viewer):
    """Capture state changes without logging every frame of a drag gesture."""
    from PySide6.QtCore import QTimer

    pending = {}
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(3000)

    def flush_motion():
        if pending:
            log_event("Navigation: " + "; ".join(f"{action}={value}" for action, value in pending.items()))
        pending.clear()

    timer.timeout.connect(flush_motion)

    def track(emitter, action, state, *, coalesce=False):
        def changed(event):
            if not coalesce:
                flush_motion()
                log_event(f"{action}: {state()}")
            else:
                if timer.isActive():
                    pending[action] = state()
                else:
                    log_event(f"Navigation: {action}={state()}")
                    timer.start()
        emitter.connect(changed)
        return changed

    camera = viewer.camera
    for field, action in (("angles", "rotation"), ("zoom", "zoom"),
                          ("center", "pan"), ("perspective", "perspective")):
        def camera_value(field=field):
            value = getattr(camera, field)
            if isinstance(value, tuple):
                return tuple(round(float(axis), 2) for axis in value)
            return round(float(value), 2)

        track(getattr(camera.events, field), action, camera_value,
              coalesce=True)
    dims = viewer.dims
    track(dims.events.ndisplay, "Display mode", lambda: f"{dims.ndisplay}D")
    track(dims.events.order, "Axis order", lambda: dims.order)
    track(dims.events.point, "slice", lambda: dims.current_step, coalesce=True)

    layer_callbacks = {}

    def layer_added(event):
        layer = event.value
        data = layer.data[0] if getattr(layer, "multiscale", False) else layer.data
        log_event(f"Layer added: {layer.name!r} ({type(layer).__name__}), "
                  f"shape={getattr(data, 'shape', None)}, dtype={getattr(data, 'dtype', None)}, "
                  f"visible={layer.visible}, scale={tuple(layer.scale)}, "
                  f"rendering={getattr(layer, 'rendering', None)}")
        callbacks = []
        for field in ("visible", "rendering", "interpolation2d", "interpolation3d"):
            emitter = getattr(layer.events, field, None)
            if emitter is not None:
                action = f"Layer {layer.name!r} {field}"
                callback = track(emitter, action, lambda field=field: getattr(layer, field))
                callbacks.append((emitter, callback))
        layer_callbacks[layer] = callbacks

    def layer_removed(event):
        layer = event.value
        for emitter, callback in layer_callbacks.pop(layer, []):
            emitter.disconnect(callback)
        log_event(f"Layer removed: {layer.name!r}")

    viewer.layers.events.inserted.connect(layer_added)
    viewer.layers.events.removed.connect(layer_removed)

    canvas = viewer.window._qt_viewer.canvas._scene_canvas

    def describe_renderer(event):
        canvas.events.draw.disconnect(describe_renderer)
        try:
            from OpenGL import GL
            details = [GL.glGetString(key) for key in (GL.GL_VENDOR, GL.GL_RENDERER, GL.GL_VERSION)]
            log_event(f"OpenGL vendor / renderer / version: {details}")
        except Exception as error:
            log_event(f"OpenGL renderer details unavailable: {error}")

    canvas.events.draw.connect(describe_renderer)
    log_event(f"Viewer ready: {dims.ndisplay}D, slices={dims.current_step}, "
              f"zoom={camera.zoom}, angles={camera.angles}, center={camera.center}")
    return timer
