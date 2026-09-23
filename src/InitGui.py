# -*- coding: utf-8 -*-
"""WireBonder workbench registration entry point (GUI).

Installation: copy the ``src`` directory of this project into the FreeCAD Mod
directory and rename it to ``WireBonder``, e.g. on Windows
``%APPDATA%\\FreeCAD\\v1-1\\Mod\\WireBonder``. After restarting FreeCAD,
"Wire Bonding" appears in the workbench selector.

WARNING - things to keep in mind when editing this file
-------------------------------------------------------
FreeCAD executes this file through ``exec(code, globals, locals)``, and the
``globals`` and ``locals`` it passes are **not the same dictionary**. That
creates two traps:

1. the namespace has **no ``__file__``**;
2. module-level assignments only land in ``locals``, while name lookup inside
   functions and class bodies uses ``globals`` - therefore **a top-level
   function that references a module-level variable raises
   ``NameError: name 'XXX' is not defined``**, and the addon silently fails
   (the error appears only in the startup log, with no visible hint in the UI).

That is why all logic lives inside **a single function** here: every piece of
state is a local variable of that function, referenced by inner functions and
by the workbench class through closures, with no module-level state at all.
"""


def _register_addon():
    """Locate the addon directory and register the Wire Bonding workbench."""
    import os
    import sys
    import time
    import traceback

    log_lines = []

    def log(message):
        log_lines.append("[{}] {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), message))

    def find_addon_dir(candidates):
        """Return the real addon root among ``candidates`` (must contain WireBonder/core.py)."""
        for root in candidates:
            try:
                if os.path.isfile(os.path.join(root, "WireBonder", "core.py")):
                    return root
            except Exception:
                continue
        return ""

    # ---------------- locate the addon directory ----------------
    candidates = []
    try:
        import WireBonder
        candidates.append(
            os.path.dirname(os.path.dirname(os.path.abspath(WireBonder.__file__)))
        )
    except Exception as exc:
        log("import WireBonder failed: {!r}".format(exc))

    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError as exc:
        log("no __file__ in this namespace ({!r}), fall back to sys.path".format(exc))

    try:
        import FreeCAD # type: ignore
        candidates.append(os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "WireBonder"))
    except Exception:
        pass

    candidates.extend(list(sys.path))

    addon_dir = find_addon_dir(candidates)
    package_dir = os.path.join(addon_dir, "WireBonder") if addon_dir else ""
    icon_dir = os.path.join(package_dir, "resources", "icons") if package_dir else ""

    if addon_dir:
        if addon_dir not in sys.path:
            sys.path.append(addon_dir)
        if package_dir not in sys.path:
            sys.path.append(package_dir)

    log("addon_dir  = {}".format(addon_dir or "<not found>"))
    log("package_dir= {}".format(package_dir or "<not found>"))
    log("icon_dir   = {} (exists: {})".format(icon_dir, os.path.isdir(icon_dir)))

    # Localisation: follow the FreeCAD language setting (Chinese -> Chinese,
    # anything else -> English). Must come after sys.path is set up, otherwise
    # the WireBonder package may not be importable yet.
    try:
        from WireBonder.i18n import language as _language
        from WireBonder.i18n import translate as _

        log("language   = {}".format(_language()))
    except Exception as exc:  # fallback: return the English msgid unchanged
        log("i18n unavailable: {!r}".format(exc))

        def _(message):
            return message

    commands = ["WireBonder_CreateWireBond", "WireBonder_CreatePlane"]

    import FreeCADGui as Gui # type: ignore

    # The translated strings are resolved inside the methods (not as class
    # attributes) so that rebuilding the workbench picks up a new language.
    def _menu_text():
        return _("Wire Bonding")

    def _tooltip():
        return _(
            "Build the bisector plane of two faces and create a wire loop "
            "(gold wire)"
        )

    workbench_holder = {"instance": None}

    class WireBonderWorkbench(Gui.Workbench):
        """Wire bonding helper workbench."""

        Icon = os.path.join(icon_dir, "WireBonder.svg") if icon_dir else ""

        @property
        def MenuText(self):
            return _menu_text()

        @property
        def ToolTip(self):
            return _tooltip()

        def Initialize(self):
            import WireBonder.commands  # noqa: F401  importing registers the commands

            group = _menu_text()
            self.appendToolbar(group, commands)
            self.appendMenu(group, commands)

        def Activated(self):
            # The Preferences dialog may have changed the language; re-check on
            # every activation so the strings are current.
            _check_language()

        def Deactivated(self):
            return

        def ContextMenu(self, recipient):
            self.appendContextMenu(_menu_text(), commands)

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    def register_workbench():
        """(Re-)register the workbench so FreeCAD rebuilds menus in the new language."""
        try:
            if "WireBonderWorkbench" in Gui.listWorkbenches():
                Gui.removeWorkbench("WireBonderWorkbench")
            workbench_holder["instance"] = WireBonderWorkbench()
            Gui.addWorkbench(workbench_holder["instance"])
            log("addWorkbench OK")
            return True
        except Exception:
            log("addWorkbench FAILED:\n" + traceback.format_exc())
            return False

    # ---------------- runtime language switching ----------------
    try:
        from WireBonder import language_monitor

        def _apply_action_labels():
            """Set the translated text/tooltip on our toolbar and menu actions.

            FreeCAD builds the QAction texts from ``GetResources()`` once, then
            retranslates them through its own Qt translator - which a dictionary
            based addon does not ship, so the texts would fall back to the raw
            English msgid. Assigning them explicitly keeps the buttons in sync.
            """
            try:
                from PySide import QtGui # type: ignore
                from WireBonder import commands as _commands

                window = Gui.getMainWindow()
                for action in window.findChildren(QtGui.QAction):
                    factory = _commands.COMMAND_RESOURCES.get(action.objectName())
                    if not factory:
                        continue
                    resources = factory()
                    action.setText(resources["MenuText"])
                    tooltip = resources.get("ToolTip", "")
                    action.setToolTip(tooltip)
                    action.setStatusTip(tooltip)
            except Exception as exc:
                log("action relabel skipped: {!r}".format(exc))

        def _relabel_actions():
            """Relabel the actions *after* FreeCAD handled its own LanguageChange.

            The event is delivered asynchronously and FreeCAD overwrites the
            action texts with the untranslated FreeCAD strings while handling it,
            so an immediate assignment would be lost. Deferring by one event
            loop turn makes our labels win.
            """
            try:
                from PySide import QtCore # type: ignore

                QtCore.QTimer.singleShot(0, _apply_action_labels)
            except Exception:
                _apply_action_labels()

        def _on_language_changed(previous, current):
            """Re-register the workbench after a runtime language change."""
            log("language switched {} -> {}".format(previous, current))
            register_workbench()
            # rebuild the active toolbar/menu so the new texts show up
            try:
                if Gui.activeWorkbench().name() == "WireBonderWorkbench":
                    Gui.activateWorkbench("PartDesignWorkbench")
                    Gui.activateWorkbench("WireBonderWorkbench")
            except Exception:
                pass
            _relabel_actions()

        def _check_language():
            language_monitor.refresh_now(_on_language_changed)

    except Exception as exc:
        log("language monitor unavailable: {!r}".format(exc))

        def _check_language():
            return False

    register_workbench()
    try:
        from WireBonder import language_monitor as _monitor

        _monitor.start(_on_language_changed)
        log("language monitor started")
    except Exception as exc:
        log("language monitor not started: {!r}".format(exc))

    # ---------------- write the log (helps diagnosing load problems) ----------------
    targets = []
    if addon_dir:
        targets.append(os.path.join(addon_dir, "wirebonder_load.log"))
    try:
        import tempfile
        targets.append(os.path.join(tempfile.gettempdir(), "wirebonder_load.log"))
    except Exception:
        pass

    text = "\n".join(log_lines) + "\n"
    for target in targets:
        try:
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text)
        except Exception:
            continue


try:
    _register_addon()
except Exception:  # last resort: never let this addon break the FreeCAD startup
    import traceback as _traceback

    try:
        import tempfile as _tempfile
        import os as _os

        with open(
            _os.path.join(_tempfile.gettempdir(), "wirebonder_boot.log"),
            "a",
            encoding="utf-8",
        ) as _handle:
            _handle.write("WireBonder InitGui.py failed:\n" + _traceback.format_exc())
    except Exception:
        pass
