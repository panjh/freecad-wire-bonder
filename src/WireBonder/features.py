# -*- coding: utf-8 -*-
"""Parametric objects: the gold wire (WireBond) and the bisector plane (WireBondPlane).

Both are ``Part::FeaturePython`` objects that reference the two faces selected
by the user through ``App::PropertyLinkSub``. After any parameter change (wire
diameter, clearance, loop peak position, ...) FreeCAD re-runs ``execute()``
automatically and rebuilds the geometry.
"""

import os

import FreeCAD as App
import Part

from . import core
from .i18n import translate as _

ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "icons")

GOLD = (1.0, 0.84, 0.0)
GOLD_EDGE = (0.62, 0.50, 0.0)
PLANE_FACE = (0.204, 0.659, 0.325)
PLANE_EDGE = (0.078, 0.373, 0.227)


def _add_property(obj, prop_type, name, group, doc, default=None):
    """Add the property only when it does not exist yet, to avoid redefinition."""
    if name in obj.PropertiesList:
        return
    obj.addProperty(prop_type, name, group, doc)
    if default is not None:
        setattr(obj, name, default)


# ----------------------------------------------------------------------
# Gold wire object
# ----------------------------------------------------------------------
class WireBondFeature:
    """Parametric gold wire (wire bond) object."""

    def __init__(self, obj):
        obj.Proxy = self
        _add_property(obj, "App::PropertyLinkSub", "Face1", "WireBond",
                      _("First plane (Face)"))
        _add_property(obj, "App::PropertyLinkSub", "Face2", "WireBond",
                      _("Second plane (Face)"))
        _add_property(obj, "App::PropertyLength", "WireDiameter", "WireBond",
                      _("Wire diameter (default 20 um)"),
                      core.DEFAULT_WIRE_DIAMETER)
        _add_property(obj, "App::PropertyLength", "Clearance", "WireBond",
                      _("Clearance: loop height above the centroid line "
                        "(default 500 um)"),
                      core.DEFAULT_CLEARANCE)
        _add_property(obj, "App::PropertyFloat", "PeakRatio", "WireBond",
                      _("Loop peak position as a ratio of the centroid "
                        "distance (0.05 - 0.95)"),
                      core.DEFAULT_PEAK_RATIO)
        _add_property(obj, "App::PropertyFloat", "RiseRatio", "WireBond",
                      _("Height ratio of the steep rise point near the start "
                        "(0 - 1)"),
                      core.DEFAULT_RISE_RATIO)
        _add_property(obj, "App::PropertyFloat", "FallRatio", "WireBond",
                      _("Height ratio of the descending point near the end "
                        "(0 - 0.3)"),
                      core.DEFAULT_FALL_RATIO)
        _add_property(obj, "App::PropertyBool", "MakeSolid", "WireBond",
                      _("Create the gold wire solid (slower for very small "
                        "diameters)"), False)
        _add_property(obj, "App::PropertyBool", "ShowCentreline", "WireBond",
                      _("Also show the wire centreline"), True)
        # A PropertyEnumeration stores its choices when a *list* is assigned,
        # and its current value when a *string* is assigned - so the list has to
        # come first. Read the choices back with
        # ``obj.getEnumerationsOfProperty("BallMode")``; ``list(obj.BallMode)``
        # would iterate the current value string instead.
        _add_property(obj, "App::PropertyEnumeration", "BallMode", "WireBond",
                      _("Bond bump shape: none / sphere (ball bond) / "
                        "frustum (truncated cone)"))
        obj.BallMode = list(core.BUMP_MODES)
        obj.BallMode = core.BUMP_SPHERE
        # Per-end shape: C1 (first bond point) and C2 (second bond point) may
        # differ. ``BallMode`` acts as the default for both, so older documents
        # and scripts keep working unchanged.
        _add_property(obj, "App::PropertyEnumeration", "StartBallMode", "WireBond",
                      _("Shape of the bump at the first bond point (C1)"))
        obj.StartBallMode = list(core.BUMP_MODES)
        obj.StartBallMode = core.BUMP_SPHERE
        _add_property(obj, "App::PropertyEnumeration", "EndBallMode", "WireBond",
                      _("Shape of the bump at the second bond point (C2)"))
        obj.EndBallMode = list(core.BUMP_MODES)
        obj.EndBallMode = core.BUMP_SPHERE
        _add_property(obj, "App::PropertyLength", "LeadDistance", "WireBond",
                      _("Distance from each pad to its entry/exit control point; "
                        "with the rise/fall ratios it sets the entry and exit "
                        "angles (default 10 um)"),
                      core.DEFAULT_LEAD_DISTANCE)
        _add_property(obj, "App::PropertyLength", "TopLength", "WireBond",
                      _("Length of the flat section at the top of the loop "
                        "(default 300 um); a longer top leaves a shorter but "
                        "steeper descent"),
                      core.DEFAULT_TOP_LENGTH)
        _add_property(obj, "App::PropertyBool", "MakeBalls", "WireBond",
                      _("Legacy switch: unchecking it is the same as setting "
                        "Bond Shape to none"), True)
        _add_property(obj, "App::PropertyLength", "BallDiameter", "WireBond",
                      _("Ball diameter (default 50 um); for a frustum it is "
                        "the bump height"),
                      core.DEFAULT_BALL_DIAMETER)
        _add_property(obj, "App::PropertyLength", "BallTopDiameter", "WireBond",
                      _("Frustum: diameter of the end away from the pad"),
                      core.DEFAULT_BALL_DIAMETER)
        _add_property(obj, "App::PropertyLength", "BallBottomDiameter", "WireBond",
                      _("Frustum: diameter of the end sitting on the pad"),
                      core.DEFAULT_BALL_DIAMETER)
        _add_property(obj, "App::PropertyAngle", "PlaneRotation", "WireBond",
                      _("Rotation of the wire plane about the centroid line "
                        "(0 deg = coincident with the bisector plane)"),
                      core.DEFAULT_PLANE_ROTATION)

    # -- geometry rebuild -------------------------------------------
    def execute(self, obj):
        try:
            face1 = self._resolve_face(obj, "Face1")
            face2 = self._resolve_face(obj, "Face2")
        except core.WireBondError:
            raise
        except Exception as exc:  # e.g. the referenced object was deleted
            raise core.WireBondError(
                _("Cannot read the selected faces: {}").format(exc)
            )

        result = core.compute_from_faces(
            face1,
            face2,
            wire_diameter=float(obj.WireDiameter),
            clearance=float(obj.Clearance),
            peak_ratio=float(obj.PeakRatio),
            rise_ratio=float(obj.RiseRatio),
            fall_ratio=float(obj.FallRatio),
            make_solid=bool(obj.MakeSolid),
            make_balls=bool(obj.MakeBalls),
            ball_diameter=float(obj.BallDiameter),
            ball_mode=getattr(obj, "BallMode", core.BUMP_SPHERE),
            top_diameter=float(getattr(obj, "BallTopDiameter",
                                       obj.BallDiameter)),
            bottom_diameter=float(getattr(obj, "BallBottomDiameter",
                                          obj.BallDiameter)),
            start_ball_mode=getattr(obj, "StartBallMode",
                                    getattr(obj, "BallMode", core.BUMP_SPHERE)),
            end_ball_mode=getattr(obj, "EndBallMode",
                                  getattr(obj, "BallMode", core.BUMP_SPHERE)),
            lead_distance=float(getattr(obj, "LeadDistance",
                                        core.DEFAULT_LEAD_DISTANCE)),
            top_length=float(getattr(obj, "TopLength",
                                     core.DEFAULT_TOP_LENGTH)),
            rotation_deg=obj.PlaneRotation.getValueAs("deg"),
        )

        shapes = []
        if result["solid"] is not None:
            shapes.append(result["solid"])
        if result["solid"] is None or obj.ShowCentreline:
            shapes.append(result["centre_line"])
        shapes.extend(result["balls"])  # the bond bumps at the two bond points

        obj.Shape = shapes[0] if len(shapes) == 1 else Part.makeCompound(shapes)

    @staticmethod
    def _resolve_face(obj, prop):
        """Return the referenced face, transformed to global coordinates (including App::Part parent transforms)."""
        ref = getattr(obj, prop)
        if not ref or ref[0] is None:
            raise core.WireBondError(
                _("{} has no face assigned.").format(prop)
            )
        target, sub = ref
        name = sub[0] if isinstance(sub, (list, tuple)) else sub
        return core.global_face(target, name)

    def onChanged(self, obj, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return


class ViewProviderWireBond:
    """Display style of the gold wire (gold coloured)."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object
        try:
            vobj.ShapeColor = GOLD
            vobj.LineColor = GOLD_EDGE
            vobj.LineWidth = 2.0
            vobj.PointSize = 2.0
        except Exception:
            pass

    def getIcon(self):
        return os.path.join(ICON_DIR, "WireBond_Create.svg")

    def updateData(self, obj, prop):
        return

    def onChanged(self, vobj, prop):
        return

    def getDisplayModes(self, obj):
        return ["Flat Lines", "Shaded", "Wireframe", "Points"]

    def getDefaultDisplayMode(self):
        return "Flat Lines"

    def setDisplayMode(self, mode):
        return mode

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return


# ----------------------------------------------------------------------
# Bisector plane object
# ----------------------------------------------------------------------
class BisectorPlaneFeature:
    """Bisector plane built from two faces (display / reference only)."""

    def __init__(self, obj):
        obj.Proxy = self
        _add_property(obj, "App::PropertyLinkSub", "Face1", "Plane",
                      _("First plane (Face)"))
        _add_property(obj, "App::PropertyLinkSub", "Face2", "Plane",
                      _("Second plane (Face)"))
        _add_property(obj, "App::PropertyLength", "Margin", "Plane",
                      _("Margin of the rectangle beyond both ends of the "
                        "centroid line"), core.DEFAULT_PLANE_MARGIN)
        _add_property(obj, "App::PropertyFloat", "WidthFactor", "Plane",
                      _("Rectangle half width = centroid distance x this "
                        "factor"), 0.35)
        _add_property(obj, "App::PropertyAngle", "PlaneRotation", "Plane",
                      _("Rotation of the wire plane about the centroid line "
                        "(0 deg = coincident with the bisector plane)"),
                      core.DEFAULT_PLANE_ROTATION)

    def execute(self, obj):
        face1 = WireBondFeature._resolve_face(obj, "Face1")
        face2 = WireBondFeature._resolve_face(obj, "Face2")
        c1, n1 = core.face_centre_and_normal(face1)
        c2, n2 = core.face_centre_and_normal(face2)
        frame = core.make_frame(
            c1, n1, c2, n2, rotation_deg=obj.PlaneRotation.getValueAs("deg")
        )
        obj.Shape = core.plane_face(
            frame, margin=float(obj.Margin), width_factor=float(obj.WidthFactor)
        )

    def onChanged(self, obj, prop):
        return

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return


class ViewProviderBisectorPlane:
    """Display style of the bisector plane (semi-transparent green)."""

    def __init__(self, vobj):
        vobj.Proxy = self
        self.Object = vobj.Object

    def attach(self, vobj):
        self.Object = vobj.Object
        try:
            vobj.ShapeColor = PLANE_FACE
            vobj.LineColor = PLANE_EDGE
            vobj.Transparency = 70
            vobj.LineWidth = 1.0
        except Exception:
            pass

    def getIcon(self):
        return os.path.join(ICON_DIR, "WireBond_Plane.svg")

    def updateData(self, obj, prop):
        return

    def onChanged(self, vobj, prop):
        return

    def getDisplayModes(self, obj):
        return ["Flat Lines", "Shaded", "Wireframe"]

    def getDefaultDisplayMode(self):
        return "Flat Lines"

    def setDisplayMode(self, mode):
        return mode

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def dumps(self):
        return None

    def loads(self, state):
        return
