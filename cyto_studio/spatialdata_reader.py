"""Minimal reader for SpatialData (OME-NGFF, zarr v3) stores.

cyto-studio historically reads the legacy STPT ``mos``/``mos.zarr`` datasets
(zarr v2) via xarray. SpatialData stores are laid out differently: each serial
section is a separate multiscale OME image (``images/S001`` ... ``images/S0NN``)
with dims ``(c, y, x)`` and pyramid levels ``scale0/scale1/...``.

This module provides just enough to feed the existing ``data.Load3D`` pipeline:
detection, channel names, physical pixel size, pyramid-level selection and a
single 2D plane read per (section, channel). Everything downstream (SimpleITK
resampling, stacking, napari layer creation) is unchanged and format-agnostic.
"""
import os
import json


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_spatialdata(path):
    """True if ``path`` is a SpatialData (zarr v3) store."""
    zj = os.path.join(path, "zarr.json")
    if not os.path.isfile(zj):
        return False
    try:
        meta = _load_json(zj)
    except Exception:
        return False
    attrs = meta.get("attributes", {}) or {}
    return "spatialdata_attrs" in attrs or "spatialdata_attrs" in meta


def _read_raw_meta(path):
    """Return the ``raw_meta`` dict (xres/yres/zres/...) or {} if unavailable."""
    # Preferred: consolidated metadata in the root zarr.json.
    try:
        meta = _load_json(os.path.join(path, "zarr.json"))
        rm = (meta.get("consolidated_metadata", {})
                  .get("metadata", {})
                  .get("raw", {})
                  .get("attributes", {})
                  .get("raw_meta"))
        if rm:
            return rm
    except Exception:
        pass
    # Fallback: the raw group's own zarr.json.
    try:
        meta = _load_json(os.path.join(path, "raw", "zarr.json"))
        rm = meta.get("attributes", {}).get("raw_meta")
        if rm:
            return rm
    except Exception:
        pass
    return {}


def spatialdata_channel_names(path):
    """Lightweight (json-only) channel names, for populating the UI list."""
    images_dir = os.path.join(path, "images")
    try:
        secs = sorted(d for d in os.listdir(images_dir)
                      if os.path.isdir(os.path.join(images_dir, d)))
    except Exception:
        secs = []
    if secs:
        try:
            meta = _load_json(os.path.join(images_dir, secs[0], "zarr.json"))
            chans = meta["attributes"]["ome"]["omero"]["channels"]
            return [str(c.get("label", i)) for i, c in enumerate(chans)]
        except Exception:
            pass
    rm = _read_raw_meta(path)
    nch = int(rm.get("channels", 0) or 0)
    return [str(i) for i in range(nch)]


class SpatialDataReader:
    """Lazy accessor over a SpatialData store for the 3D loader."""

    def __init__(self, path):
        import spatialdata as sd  # imported lazily; heavy dependency

        self.path = path
        self.sdata = sd.read_zarr(path)
        self.sections = sorted(self.sdata.images.keys())
        self.number_of_sections = len(self.sections)

        # Pyramid levels (scale0, scale1, ...) and their downsample factors,
        # derived from the actual shapes so this is robust to level count.
        first = self.sdata.images[self.sections[0]]
        self.scale_keys = [k for k in first.children if str(k).startswith("scale")]
        self.scale_keys.sort(key=lambda k: int(str(k).replace("scale", "")))
        base_y = self._level_da(self.sections[0], self.scale_keys[0]).sizes["y"]
        self.scale_factors = []
        for k in self.scale_keys:
            ny = self._level_da(self.sections[0], k).sizes["y"]
            self.scale_factors.append(max(1, round(base_y / ny)))

        # Channel names from the c coordinate (fallback to positional index).
        da0 = self._level_da(self.sections[0], self.scale_keys[0])
        if "c" in da0.coords:
            self.channel_names = [str(v) for v in da0.coords["c"].values.tolist()]
        else:
            self.channel_names = [str(i) for i in range(da0.sizes["c"])]

        # Physical pixel size (microns) from raw_meta; spacing = [x, y].
        rm = _read_raw_meta(path)
        try:
            xres = float(rm.get("xres") or rm.get("xRes_um") or 1.0)
            yres = float(rm.get("yres") or rm.get("yRes_um") or 1.0)
        except (TypeError, ValueError):
            xres = yres = 1.0
        self.spacing = [xres, yres]

    def _level_da(self, section, scale_key):
        node = self.sdata.images[section][scale_key]
        if "image" in node:
            return node["image"]
        # Fallback: first data variable of the node.
        return list(node.data_vars.values())[0]

    def level_for(self, output_resolution):
        """Pick the coarsest pyramid level whose pixel size <= output_resolution.

        Returns ``(scale_key, factor)`` where factor is the downsample factor of
        the chosen level relative to scale0 (used by the resample math, exactly
        like the STPT ``resolution`` variable).
        """
        base = float(self.spacing[0]) or 1.0
        try:
            out = float(output_resolution)
        except (TypeError, ValueError):
            out = base
        choose = 0
        for i, f in enumerate(self.scale_factors):
            if f * base <= out:
                choose = i
        return self.scale_keys[choose], self.scale_factors[choose]

    def plane_shape(self, scale_key):
        da = self._level_da(self.sections[0], scale_key)
        return int(da.sizes["y"]), int(da.sizes["x"])

    def get_plane(self, section, channel_index, scale_key):
        """Return the 2D ``(y, x)`` plane for one section/channel as numpy."""
        import numpy as np

        da = self._level_da(section, scale_key)
        plane = da.isel(c=channel_index)
        return np.asarray(plane.data)

    def multiscale_planes(self, section, channel_index):
        """Return the pyramid of 2D ``(y, x)`` planes as lazy (dask) arrays,
        coarsest-last, for napari ``add_image(..., multiscale=True)``."""
        return [self._level_da(section, k).isel(c=channel_index).data
                for k in self.scale_keys]
