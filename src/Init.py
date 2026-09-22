# -*- coding: utf-8 -*-
"""Non-GUI entry point of WireBonder.

FreeCAD executes this file through ``exec(code, globals, locals)`` (where
``globals`` and ``locals`` are not the same dictionary), so this file only
contains the simplest top-level statements and defines no function that depends
on module-level state, in order to avoid a ``NameError``.

Purpose: add the addon directory to ``sys.path`` so that ``import WireBonder``
always works in the FreeCAD Python console (the geometry core has no GUI
dependency and can be called directly from the console).
"""

import os
import sys

try:
    import WireBonder

    _addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(WireBonder.__file__)))
except Exception:
    try:
        _addon_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        _addon_dir = ""

if _addon_dir and _addon_dir not in sys.path:
    sys.path.append(_addon_dir)
