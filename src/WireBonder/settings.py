# -*- coding: utf-8 -*-
"""Persistent panel settings.

The task panel remembers the values used last time so that repeated wire bonds
do not require re-entering the same numbers on every run.

Storage uses FreeCAD's user parameters
(``User parameter:BaseApp/Preferences/Mod/WireBonder``), which means

* the values survive a FreeCAD restart,
* they are per user, not per document,
* nothing is written into the .FCStd drawings, and they can be reset from
  **Tools ▸ Edit parameters ▸ BaseApp ▸ Preferences ▸ Mod ▸ WireBonder**.

Only the *panel defaults* are stored here.  Objects already created keep their
own properties - changing a stored default never modifies existing geometry.
"""

import FreeCAD as App

from . import core

__all__ = ["Settings", "load_defaults", "save_defaults", "PARAM_PATH"]

#: FreeCAD parameter group used by this addon
PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/WireBonder"

#: panel key -> (parameter name, fallback value)
#: lengths are stored in millimetres (FreeCAD's native unit), the panel converts
#: to/from micrometres where needed
_SPEC = {
    "wire_diameter": ("WireDiameter", core.DEFAULT_WIRE_DIAMETER),
    "clearance": ("Clearance", core.DEFAULT_CLEARANCE),
    "ball_diameter": ("BallDiameter", core.DEFAULT_BALL_DIAMETER),
    "plane_rotation": ("PlaneRotation", core.DEFAULT_PLANE_ROTATION),
    "peak_ratio": ("PeakRatio", core.DEFAULT_PEAK_RATIO),
    "rise_ratio": ("RiseRatio", core.DEFAULT_RISE_RATIO),
    "fall_ratio": ("FallRatio", core.DEFAULT_FALL_RATIO),
    "make_solid": ("MakeSolid", False),
    "show_centreline": ("ShowCentreline", True),
    "make_balls": ("MakeBalls", True),
    "ball_mode": ("BallMode", core.BUMP_SPHERE),
    "start_ball_mode": ("StartBallMode", core.BUMP_SPHERE),
    "end_ball_mode": ("EndBallMode", core.BUMP_SPHERE),
    "ball_top_diameter": ("BallTopDiameter", core.DEFAULT_BALL_DIAMETER),
    "ball_bottom_diameter": ("BallBottomDiameter", core.DEFAULT_BALL_DIAMETER),
    "lead_distance": ("LeadDistance", core.DEFAULT_LEAD_DISTANCE),
    "top_length": ("TopLength", core.DEFAULT_TOP_LENGTH),
    "create_plane": ("CreatePlane", False),
    # UI state: which panel sections are expanded (not a geometry parameter)
    "ui_show_faces": ("UiShowFaces", True),
    "ui_show_params": ("UiShowParams", True),
    "ui_show_options": ("UiShowOptions", True),
}

#: keys whose values are booleans
_BOOLEAN_KEYS = (
    "make_solid",
    "show_centreline",
    "make_balls",
    "create_plane",
    "ui_show_faces",
    "ui_show_params",
    "ui_show_options",
)

#: keys stored as strings (enumerations, free text)
_STRING_KEYS = ("ball_mode", "start_ball_mode", "end_ball_mode")

#: enumeration keys that must hold one of :data:`core.BUMP_MODES`
_MODE_KEYS = ("ball_mode", "start_ball_mode", "end_ball_mode")


def _open_params():
    """Return the parameter group, or ``None`` when unavailable."""
    try:
        return App.ParamGet(PARAM_PATH)
    except Exception:
        return None


class Settings(dict):
    """Dictionary of panel defaults with load/save helpers."""

    # ------------------------------------------------------------------
    # construction
    # ------------------------------------------------------------------
    @classmethod
    def defaults(cls):
        """Built-in defaults (no stored values involved)."""
        settings = cls()
        for key, (_name, fallback) in _SPEC.items():
            settings[key] = fallback
        return settings

    @classmethod
    def load(cls):
        """Return the stored settings, falling back to the built-in defaults."""
        settings = cls.defaults()
        params = _open_params()
        if params is None:
            return settings

        for key, (name, fallback) in _SPEC.items():
            try:
                if key in _BOOLEAN_KEYS:
                    settings[key] = params.GetBool(name, bool(fallback))
                elif key in _STRING_KEYS:
                    value = params.GetString(name, str(fallback))
                    if key in _MODE_KEYS and value not in core.BUMP_MODES:
                        value = core.BUMP_SPHERE
                    settings[key] = value
                else:
                    settings[key] = params.GetFloat(name, float(fallback))
            except Exception:
                # keep the built-in default when a stored value is unreadable
                settings[key] = fallback
        return settings

    @classmethod
    def load_checked(cls):
        """Like :meth:`load` but clamps stored values to sane ranges.

        A hand-edited parameter file could contain out-of-range values; the panel
        widgets clamp them anyway, but clamping here keeps the returned values
        consistent with what the user will actually see.
        """
        settings = cls.load()
        limits = {
            "wire_diameter": (0.0001, 0.5),        # 0.1 um ... 500 um
            "clearance": (0.0, 100.0),             # 0 ... 100000 um
            "ball_diameter": (0.001, 20.0),        # 1 um ... 20000 um
            "lead_distance": (0.0, 5.0),           # 0 ... 5000 um
            "top_length": (0.0, 20.0),             # 0 ... 20000 um
            "plane_rotation": (-180.0, 180.0),
            "peak_ratio": (0.05, 0.95),
            "rise_ratio": (0.0, 1.0),
            "fall_ratio": (0.0, 0.60),
        }
        for key, (low, high) in limits.items():
            try:
                value = float(settings.get(key, low))
            except Exception:
                continue
            settings[key] = min(max(value, low), high)
        return settings

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def save(self):
        """Write the current values to the FreeCAD user parameters."""
        params = _open_params()
        if params is None:
            return False

        try:
            from . import __version__ as addon_version

            params.SetString("Version", addon_version)
        except Exception:
            pass

        for key, (name, fallback) in _SPEC.items():
            if key not in self:
                continue
            try:
                if key in _BOOLEAN_KEYS:
                    params.SetBool(name, bool(self[key]))
                else:
                    params.SetFloat(name, float(self[key]))
            except Exception:
                continue
        return True


def load_defaults():
    """Convenience wrapper returning a validated :class:`Settings`."""
    return Settings.load_checked()


def save_defaults(**values):
    """Store the given ``key=value`` pairs (see :data:`_SPEC` for valid keys).

    Keys not given are left untouched, so callers can persist incrementally.
    """
    return _store(values)


def save_ui_state(**values):
    """Persist the panel layout state (which sections are expanded).

    Kept separate from :func:`save_defaults` so that the *built-in defaults*
    button does not silently reset the user's panel layout.
    """
    return _store({k: v for k, v in values.items() if k.startswith("ui_")})


def _store(values):
    params = _open_params()
    if params is None:
        return False
    for key, value in values.items():
        entry = _SPEC.get(key)
        if entry is None:
            continue
        name = entry[0]
        try:
            if key in _BOOLEAN_KEYS:
                params.SetBool(name, bool(value))
            elif key in _STRING_KEYS:
                params.SetString(name, str(value))
            else:
                params.SetFloat(name, float(value))
        except Exception:
            continue
    return True


def clear():
    """Remove all stored settings (used by tests and a manual reset).

    Note: ``ParamGet`` stores numbers and booleans as separate types, so the
    matching remover must be used - ``RemString`` silently fails on a value that
    was written with ``SetFloat``.
    """
    params = _open_params()
    if params is None:
        return False

    removed = False
    for key, (name, _fallback) in _SPEC.items():
        try:
            if key in _BOOLEAN_KEYS:
                params.RemBool(name)
            elif key in _STRING_KEYS:
                params.RemString(name)
            else:
                params.RemFloat(name)
            removed = True
        except Exception:
            pass

    try:
        params.RemString("Version")
    except Exception:
        pass
    return removed
