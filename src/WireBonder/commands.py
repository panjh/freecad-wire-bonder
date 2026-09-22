# -*- coding: utf-8 -*-
"""FreeCAD commands: create a wire bond (gold wire) from two selected faces."""

import os

import FreeCAD as App # type: ignore
import FreeCADGui as Gui # type: ignore

try:
    from PySide import QtWidgets # type: ignore
except ImportError:  # pragma: no cover
    from PySide2 import QtWidgets # type: ignore

from . import core
from .i18n import translate as _
from .taskpanel import WireBondTaskPanel, containing_body

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons")


def selected_faces():
    """Collect the currently selected faces; returns [(obj, "FaceN"), ...]."""
    picked = []
    for sel in Gui.Selection.getSelectionEx():
        obj = sel.Object
        if obj is None or not hasattr(obj, "Shape"):
            continue
        for sub in sel.SubElementNames:
            if sub.startswith("Face"):
                picked.append((obj, sub))
    return picked


def _face_selection_or_warn():
    """Return exactly two faces; otherwise show a message box and return None."""
    picked = selected_faces()
    if len(picked) == 2 and picked[0] != picked[1]:
        return picked

    if len(picked) < 2:
        message = _(
            "Please select two faces in the 3D view first (hold Ctrl for "
            "multi-select).\nFaces detected so far: {}."
        ).format(len(picked))
    else:
        message = _(
            "Too many faces selected ({}); please keep exactly two faces."
        ).format(len(picked))
    QtWidgets.QMessageBox.information(None, _("Wire Bond"), message)
    return None


class CreateWireBondCommand:
    """Open the parameter panel and create the gold wire from the two faces."""

    def GetResources(self):
        # Resolved on every call so that a runtime language switch is reflected
        # as soon as FreeCAD rebuilds the toolbar/menu (see LanguageMonitor).
        return {
            "Pixmap": os.path.join(ICON_DIR, "WireBond_Create.svg"),
            "MenuText": _("Create Wire Bond"),
            "ToolTip": _(
                "Build the bisector plane of two faces and create a wire loop "
                "(gold wire) between the two face centroids.\n"
                "The wire diameter and clearance can be set in the panel."
            ),
        }

    def IsActive(self):
        return App.ActiveDocument is not None and len(selected_faces()) == 2

    def Activated(self):
        selection = _face_selection_or_warn()
        if selection is None:
            return

        # Pre-check: surface degenerate cases (opposite normals / line parallel
        # to the bisector) as early as possible
        try:
            (obj1, sub1), (obj2, sub2) = selection
            # Note: use global_face rather than face_from_subname - the parent
            # container (App::Part ...) transform must be added, otherwise the
            # centroid of a part inside an assembly deviates from global coords
            face1 = core.global_face(obj1, sub1)
            face2 = core.global_face(obj2, sub2)
            c1, n1 = core.face_centre_and_normal(face1)
            c2, n2 = core.face_centre_and_normal(face2)
            frame = core.make_frame(c1, n1, c2, n2)
            App.Console.PrintMessage(
                _("Wire Bond: centroid distance {:.3f} mm, plane normal "
                  "({:.3f}, {:.3f}, {:.3f})\n").format(
                    frame.length, frame.zdir.x, frame.zdir.y, frame.zdir.z
                )
            )

            # Explain the PartDesign Body scope isolation upfront
            # (informational only, never blocks)
            bodies = []
            for target in (obj1, obj2):
                body = containing_body(target)
                if body is not None and body.Name not in bodies:
                    bodies.append(body.Name)
            if bodies:
                App.Console.PrintWarning(
                    _("Wire Bond: the selected faces belong to PartDesign Body "
                      "({}). The wire object is created outside of the Body, so "
                      "FreeCAD reports \"Link(s) ... go out of the allowed "
                      "scope\" - this is a scope-isolation warning and does not "
                      "affect the geometry; to get rid of it, model the pads "
                      "with the Part workbench (Part::Box, etc.).\n").format(
                        ", ".join(bodies)
                    )
                )
        except core.WireBondError as exc:
            QtWidgets.QMessageBox.warning(None, _("Wire Bond"), str(exc))
            return

        Gui.Control.showDialog(WireBondTaskPanel(selection))


class CreateBisectorPlaneCommand:
    """Create the bisector plane only (no gold wire)."""

    def GetResources(self):
        return {
            "Pixmap": os.path.join(ICON_DIR, "WireBond_Plane.svg"),
            "MenuText": _("Create Bisector Plane"),
            "ToolTip": _(
                "Only build the bisector plane of two faces, without creating "
                "a wire."
            ),
        }

    def IsActive(self):
        return App.ActiveDocument is not None and len(selected_faces()) == 2

    def Activated(self):
        from . import features

        selection = _face_selection_or_warn()
        if selection is None:
            return

        doc = App.ActiveDocument
        (obj1, sub1), (obj2, sub2) = selection

        doc.openTransaction("Create Bisector Plane")
        try:
            plane = doc.addObject("Part::FeaturePython", "WireBondPlane")
            features.BisectorPlaneFeature(plane)
            if plane.ViewObject is not None:
                features.ViewProviderBisectorPlane(plane.ViewObject)
            plane.Face1 = (obj1, sub1)
            plane.Face2 = (obj2, sub2)
            doc.recompute()
            doc.commitTransaction()
        except Exception as exc:
            doc.abortTransaction()
            QtWidgets.QMessageBox.critical(
                None, _("Wire Bond"),
                _("Failed to create the bisector plane:\n{}").format(exc)
            )


#: command name -> callable returning the (translated) resource dict.
#: Used by InitGui.py to re-apply labels when the language changes at runtime,
#: because FreeCAD would otherwise keep retranslating the QAction texts through
#: its own Qt translator, which a dictionary based addon does not provide.
COMMAND_RESOURCES = {
    "WireBonder_CreateWireBond": CreateWireBondCommand().GetResources,
    "WireBonder_CreatePlane": CreateBisectorPlaneCommand().GetResources,
}

Gui.addCommand("WireBonder_CreateWireBond", CreateWireBondCommand())
Gui.addCommand("WireBonder_CreatePlane", CreateBisectorPlaneCommand())
