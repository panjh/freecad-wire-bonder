# -*- coding: utf-8 -*-
"""Runtime language monitor.

FreeCAD caches the UI language at startup, so a plugin that resolves its
language once keeps the old strings until the next restart. This module watches
both places where the language can change and reacts immediately:

* the **``Language`` user parameter** - written by the Preferences dialog. Note
  that changing this parameter alone does *not* update
  ``FreeCADGui.getLocale()``: that call is driven by ``FreeCADGui.setLocale()``.
  The monitor therefore pushes the parameter value through ``setLocale()`` so
  FreeCAD's own UI and the addon stay consistent.
* the **GUI locale** - changed directly by ``FreeCADGui.setLocale()``, e.g. from
  a macro or another addon.

Two detection channels are used together, because neither is reliable alone:

* a **parameter observer** (``ParamAttach``) - fires immediately when the
  Preferences dialog writes the new language (verified: the callback runs while
  the dialog is still open);
* a **poll timer** - covers changes made through other routes.

On a change the module updates :mod:`WireBonder.i18n` and then calls the
configured callback, which re-registers the addon workbench so FreeCAD rebuilds
the toolbar/menu with the new texts.
"""

import FreeCAD as App

from . import i18n

__all__ = ["LanguageMonitor", "start", "stop", "refresh_now"]

#: poll interval in milliseconds (0 disables polling)
POLL_INTERVAL_MS = 1500

_monitor = None


def _to_language_code(text):
    """Map a FreeCAD language string (``'Chinese (Simplified)'``) to ``zh``/``en``."""
    if not text:
        return None
    lowered = str(text).strip().lower()
    if lowered.startswith("zh") or "chinese" in lowered:
        return "zh"
    return "en"


class _ParamObserver:
    """Bridges FreeCAD's ``ParamAttach`` callback to the monitor."""

    def __init__(self, monitor):
        self._monitor = monitor

    def onChange(self, param, reason):
        try:
            self._monitor.check()
        except Exception:
            pass

    # ParamAttach requires these to exist; they are unused here
    def slotChangedObject(self, obj, prop):
        pass

    def slotChange(self, param, reason):
        pass


class LanguageMonitor:
    """Watch the FreeCAD language setting and refresh the addon on changes."""

    PARAM_PATH = "User parameter:BaseApp/Preferences/General"

    def __init__(self, on_changed=None, poll_interval_ms=POLL_INTERVAL_MS):
        self.on_changed = on_changed
        self.poll_interval_ms = poll_interval_ms
        self._observer = None
        self._param = None
        self._timer = None
        self._busy = False
        self._last_param = None
        self._last_gui = None

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Begin watching; safe to call more than once."""
        if self._param is None:
            try:
                self._param = App.ParamGet(self.PARAM_PATH)
            except Exception:
                self._param = None

        if self._param is not None and self._observer is None:
            self._observer = _ParamObserver(self)
            try:
                self._param.Attach(self._observer)
            except Exception:
                self._observer = None

        if self._timer is None and self.poll_interval_ms:
            self._timer = self._create_timer()

        # remember the current state so the first check does not report a change
        self._last_param = self._param_value()
        self._last_gui = self._gui_locale()
        return self

    def stop(self):
        """Stop watching and release the Qt timer."""
        if self._observer is not None and self._param is not None:
            try:
                self._param.Detach(self._observer)
            except Exception:
                pass
            self._observer = None

        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    # ------------------------------------------------------------------
    # reading the two language sources
    # ------------------------------------------------------------------
    def _param_value(self):
        try:
            return self._param.GetString("Language", "") if self._param else ""
        except Exception:
            return ""

    def _gui_locale(self):
        try:
            from FreeCADGui import getLocale

            return getLocale() or ""
        except Exception:
            return ""

    def _create_timer(self):
        """Create a QTimer owned by FreeCAD's main window (kept alive there)."""
        try:
            from PySide import QtCore
            from FreeCADGui import getMainWindow

            timer = QtCore.QTimer(getMainWindow())
            timer.setInterval(int(self.poll_interval_ms))
            timer.timeout.connect(self.check)
            timer.start()
            return timer
        except Exception:
            return None

    # ------------------------------------------------------------------
    # detection
    # ------------------------------------------------------------------
    def check(self):
        """Compare the language sources with the last state; refresh on change."""
        if self._busy:
            return False
        self._busy = True
        try:
            param_value = self._param_value()
            gui_value = self._gui_locale()

            param_changed = param_value != self._last_param
            gui_changed = gui_value != self._last_gui

            if not (param_changed or gui_changed):
                return False

            self._last_param = param_value
            self._last_gui = gui_value

            # A parameter change comes from the Preferences dialog: adopt it and
            # push it to the GUI so FreeCAD's own locale follows.
            if param_changed and param_value:
                target = _to_language_code(param_value)
                try:
                    from FreeCADGui import setLocale

                    setLocale(param_value)
                    self._last_gui = param_value
                except Exception:
                    pass
            else:
                target = _to_language_code(gui_value)

            if not target:
                return False

            previous = i18n.language()
            i18n.set_language(target)
            current = i18n.language()
            if current == previous:
                return False

            App.Console.PrintMessage(
                "WireBond: language changed {} -> {}\n".format(previous, current)
            )
            if self.on_changed is not None:
                try:
                    self.on_changed(previous, current)
                except Exception as exc:
                    App.Console.PrintWarning(
                        "WireBond: language refresh failed: {}\n".format(exc)
                    )
            return True
        finally:
            self._busy = False


# ----------------------------------------------------------------------
# module level helpers (used by InitGui.py)
# ----------------------------------------------------------------------
def start(on_changed=None):
    """Create (once) and start the shared monitor."""
    global _monitor
    if _monitor is None:
        _monitor = LanguageMonitor(on_changed=on_changed)
    elif on_changed is not None:
        _monitor.on_changed = on_changed
    return _monitor.start()


def stop():
    """Stop the shared monitor, if any."""
    global _monitor
    if _monitor is not None:
        _monitor.stop()
        _monitor = None


def refresh_now(on_changed=None):
    """Force an immediate check (e.g. when the addon workbench is activated)."""
    monitor = start(on_changed)
    monitor.check()
    return monitor
