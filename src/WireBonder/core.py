# -*- coding: utf-8 -*-
"""Wire bonding geometry core.

This module only depends on FreeCAD / Part and has no GUI dependency, so it can
be driven from the command panel as well as from the console or test scripts.

Construction rules
------------------
Given two selected faces F1 and F2:

1. take the centroids C1, C2 and the connecting direction ``d = normalize(C2 - C1)``;
2. take the normals n1, n2, first align them to the same hemisphere (flip n2 when
   the angle exceeds 90 degrees), then take the bisector ``b = normalize(n1 + n2)``;
3. the target plane P is spanned by ``d`` and ``b`` and passes through C1 and C2;
4. build a local frame inside P: the x axis along ``d``, the y axis as the
   orthogonal component of ``b`` within P, the z axis as the plane normal ``x x y``;
5. generate a wire loop inside P connecting C1 and C2; the height of the loop
   peak above the connecting line is the "clearance";
6. sweep a circle of diameter ``wire_diameter`` along that curve to obtain the
   gold wire solid.
"""

import math
from collections import namedtuple

import FreeCAD as App # type: ignore
import Part # type: ignore
from FreeCAD import Vector # type: ignore

from .i18n import translate as _

__all__ = [
    "WireBondError",
    "Frame",
    "face_from_subname",
    "face_global_transform",
    "global_face",
    "face_centre_and_normal",
    "make_frame",
    "loop_profile",
    "to_world",
    "build_centreline",
    "sweep_wire",
    "bond_balls",
    "plane_face",
    "compute_from_faces",
]


class WireBondError(Exception):
    """Raised when the geometry construction fails; the message is user facing."""


# ----------------------------------------------------------------------
# Default parameters (in mm)
# ----------------------------------------------------------------------
DEFAULT_WIRE_DIAMETER = 0.02   # 20 um, typical gold wire diameter
DEFAULT_CLEARANCE = 0.2        # clearance 500 um (apex height above the centroid line)
DEFAULT_PEAK_RATIO = 0.40      # apex position as a ratio of the centroid distance
DEFAULT_RISE_ANGLE = 75.0      # deg from the A-E line; 90 deg = perpendicular.
#                                A steep take-off, as in the reference sketch.
DEFAULT_FALL_ANGLE = 15.0      # deg from the A-E line; a shallower landing than
#                                the take-off, again following the sketch
DEFAULT_BALL_DIAMETER = 0.05   # bond ball diameter 50 um (about 2.5x the wire diameter)
DEFAULT_FRUSTUM_TOP_DIAMETER = 0.05 # bond frustum top diameter
DEFAULT_FRUSTUM_BOTTOM_DIAMETER = 0.05 # bond frustum bottom diameter
DEFAULT_LEAD_DISTANCE = 0.03   # 30 um along the rise/fall ray. Swept against the
#                                reference proportions, 30 um gives a crest about
#                                125 um wide with an 14% descent deviation, a good
#                                compromise (see scripts/scan_angles.py)
DEFAULT_PLANE_ROTATION = 0.0   # wire plane rotation about the centroid line (deg), 0 = coincident
DEFAULT_PLANE_MARGIN = 2.0     # visual margin of the helper plane rectangle (mm)

Frame = namedtuple("Frame", "origin xdir ydir zdir length")


# ----------------------------------------------------------------------
# Basic helpers
# ----------------------------------------------------------------------
def _normalize(vec, what):
    """Normalise a vector; ``what`` is an English msgid localised by i18n."""
    if vec.Length < 1e-12:
        raise WireBondError(_("{} has zero length; cannot determine its direction.").format(what))
    return Vector(vec.x, vec.y, vec.z) / vec.Length


def face_from_subname(shape, subname):
    """Return the face denoted by a GUI sub-element name such as ``Face3``."""
    if not subname.startswith("Face"):
        raise WireBondError(
            _("Selected sub-element {} is not a face; please select exactly "
              "two faces.").format(subname)
        )
    try:
        index = int(subname[4:]) - 1
    except ValueError:
        raise WireBondError(
            _("Cannot parse sub-element name: {}").format(subname)
        )

    faces = shape.Faces
    if index < 0 or index >= len(faces):
        raise WireBondError(_("Face index out of range: {}").format(subname))
    return faces[index]


def face_global_transform(obj):
    """Return the transform needed to lift ``obj.Shape`` into global coordinates.

    ``obj.Shape`` already contains the object's **own** Placement but **not the
    parent container** (``App::Part`` / ``PartDesign::Body`` ...) Placement. For
    parts inside an assembly, using ``face.CenterOfMass`` directly yields a
    position offset from the global assembly and the wire is drawn outside the
    model. This returns ``getGlobalPlacement() * Placement^-1``, i.e. the part
    contributed by the parent chain; ``None`` when no transform is needed.
    """
    try:
        return obj.getGlobalPlacement().multiply(obj.Placement.inverse())
    except Exception:
        return None


def global_face(obj, subname):
    """Return the face ``subname`` of ``obj``, transformed to **global** coordinates.

    All geometry computations should use this function (rather than
    ``face_from_subname``), otherwise the wire position of parts inside an
    assembly is wrong. Returns the face unchanged when there is no parent transform.
    """
    face = face_from_subname(obj.Shape, subname)
    extra = face_global_transform(obj)
    if extra is None:
        return face
    try:
        if extra.isIdentity():
            return face
    except Exception:
        pass
    return face.transformed(extra.toMatrix())


def face_centre_and_normal(face):
    """Return the face centroid and normal (normal oriented by the face, normalised).

    Note: the face passed in should already be in global coordinates (obtain it
    with :func:`global_face`).
    """
    centre = face.CenterOfMass
    try:
        normal = face.normalAt(0.5, 0.5)
    except Exception:  # degenerate case: fall back to the surface axis
        try:
            normal = face.Surface.Axis
        except Exception:
            raise WireBondError(_("Cannot obtain the face normal."))
    return centre, _normalize(normal, _("face normal"))


# ----------------------------------------------------------------------
# Bisector plane construction
# ----------------------------------------------------------------------
def make_frame(c1, n1, c2, n2, rotation_deg=DEFAULT_PLANE_ROTATION):
    """Build the local frame of the wire plane (bisector plane).

    Returns ``Frame(origin, xdir, ydir, zdir, length)``:
        origin = C1
        xdir   = centroid line direction
        ydir   = bisector of the two centroid normals (orthogonal component in plane)
        zdir   = plane normal = xdir x ydir
        length = |C2 - C1|

    ``rotation_deg`` is the **rotation of the wire plane about the centroid
    line** (in degrees): ``0`` means the wire plane is exactly coincident with
    the bisector plane; a non-zero value rotates the local y/z axes about the x
    axis by that angle, so the wire enters and leaves diagonally and the loop
    peak direction changes accordingly.
    """
    c1 = Vector(c1.x, c1.y, c1.z)
    c2 = Vector(c2.x, c2.y, c2.z)
    n1 = Vector(n1.x, n1.y, n1.z)
    n2 = Vector(n2.x, n2.y, n2.z)

    length = (c2 - c1).Length
    if length < 1e-9:
        raise WireBondError(
            _("The two face centroids coincide; cannot determine the "
              "connecting direction.")
        )

    xdir = _normalize(c2 - c1, _("centroid line"))

    # align both normals to the same hemisphere
    if float(n1.dot(n2)) < 0.0:
        n2 = Vector(-n2.x, -n2.y, -n2.z)

    bisector = n1 + n2
    if bisector.Length < 1e-9:
        raise WireBondError(
            _("The two face normals are 180 degrees apart, so no bisector "
              "exists; please select two faces with a consistent orientation.")
        )

    # keep the component of the bisector perpendicular to the line
    # (Gram-Schmidt) so that the y axis lies inside the plane
    ydir_raw = bisector - xdir * float(bisector.dot(xdir))
    if ydir_raw.Length < 1e-9 * max(1.0, bisector.Length):
        raise WireBondError(
            _("The centroid line is parallel to the normal bisector, so the "
              "plane is not unique; please select two faces whose normals "
              "differ in direction.")
        )
    ydir = _normalize(ydir_raw, _("normal bisector"))
    zdir = _normalize(xdir.cross(ydir), _("plane normal"))

    # rotate the wire plane about the centroid line (x axis):
    # 0 degrees means fully coincident with the bisector plane
    rotation = float(rotation_deg or 0.0)
    if abs(rotation) > 1e-12:
        rot = App.Rotation(xdir, rotation)
        ydir = _normalize(rot.multVec(ydir), _("rotated Y axis"))
        zdir = _normalize(rot.multVec(zdir), _("rotated plane normal"))

    return Frame(c1, xdir, ydir, zdir, length)


# ----------------------------------------------------------------------
# Wire loop profile
# ----------------------------------------------------------------------
#: Shape of the wire loop, with five control points A -> B -> C -> D -> E:
#:
#: * **A** - start, on the first pad;
#: * **B** - *up start*, ``AB = lead_distance`` along the ``rise_angle`` ray
#:   leaving A;
#: * **C** - *apex*, between A and E, placed by ``peak_ratio`` and ``clearance``;
#: * **D** - *up end*, ``ED = lead_distance`` along the ``fall_angle`` ray
#:   leaving E  (the spec sheet writes this as ``CD``; ``ED`` is meant, to
#:   mirror ``AB``);
#: * **E** - end, on the second pad.
#:
#:      B                                    D
#:      *            * (C, apex)             *
#:     /                                      \
#:    A                                        E
#:
#: Both angles are measured **from the line A-E**: 0 deg points at the other
#: pad, 90 deg is perpendicular to that line (straight up). The angle therefore
#: says directly how steeply the wire leaves and lands, which is the quantity a
#: bonder engineer tunes - unlike the previous height ratio.
MAX_LEAD_FRACTION = 0.30   # lead may use at most this fraction of the span
MAX_ANGLE = 89.0           # stay just short of vertical, so B/D keep an x offset


def loop_profile(length, clearance, peak_ratio=DEFAULT_PEAK_RATIO,
                 rise_angle=DEFAULT_RISE_ANGLE, fall_angle=DEFAULT_FALL_ANGLE,
                 lead_distance=DEFAULT_LEAD_DISTANCE):
    """Return the wire loop control points ``[(u, v), ...]`` in plane-local coordinates.

    ``u`` runs along the centroid line (0 -> length) and ``v`` is the height
    above that line (0 -> clearance). Five points are returned:

    =====  =====================  ==========================================
    point  u                      v
    =====  =====================  ==========================================
    A      ``0``                  ``0``
    B      ``lead * cos(rise)``   ``lead * sin(rise)``
    C      ``peak_ratio * L``     ``clearance``
    D      ``L - lead*cos(fall)`` ``lead * sin(fall)``
    E      ``L``                  ``0``
    =====  =====================  ==========================================

    ``rise_angle`` and ``fall_angle`` are measured from the A-E line: 0 deg
    points towards the other pad, 90 deg is perpendicular to it. The wire
    therefore leaves A along the rise ray and reaches E from the fall ray,
    each for a distance of ``lead_distance``.

    The distance from D to C is not an independent value - it follows from the
    other parameters, which is what makes this formulation easy to reason
    about: you set how steeply the wire enters and leaves, how far up it goes
    and where the apex sits, and the rest is geometry.
    """
    length = float(length)
    height = float(clearance)
    if length <= 0.0:
        raise WireBondError(_("The centroid distance must be greater than zero."))
    if height < 0.0:
        raise WireBondError(_("Clearance must not be negative."))

    ratio = min(max(float(peak_ratio), 0.05), 0.95)
    peak_u = length * ratio

    lead = float(lead_distance or 0.0)
    if lead <= 0.0:
        lead = DEFAULT_LEAD_DISTANCE

    rise = math.radians(min(max(float(rise_angle), 0.0), MAX_ANGLE))
    fall = math.radians(min(max(float(fall_angle), 0.0), MAX_ANGLE))

    # Horizontal extent of each lead. A limited lead keeps B before C and D
    # after C, which the spline interpolation requires (strictly increasing u).
    du_b = lead * math.cos(rise)
    du_d = lead * math.cos(fall)
    room = max(length * (1.0 - ratio), 1e-9)
    if du_b > 0.0 and peak_u > 0.0:
        du_b = min(du_b, peak_u * 0.98)
    if du_d > 0.0 and room > 0.0:
        du_d = min(du_d, room * 0.98)

    return [
        (0.0, 0.0),                                                   # A
        (du_b, lead * math.sin(rise)),                                # B
        (peak_u, height),                                             # C
        (length - du_d, lead * math.sin(fall)),                       # D
        (length, 0.0),                                                # E
    ]


def to_world(frame, points2d):
    """Map the local 2D control points into 3D space."""
    return [frame.origin + frame.xdir * u + frame.ydir * v for (u, v) in points2d]


def build_centreline(points3d):
    """Build an interpolated spline from the control points; returns the centreline (Part.Wire)."""
    curve = Part.BSplineCurve()
    curve.interpolate([Vector(p.x, p.y, p.z) for p in points3d])
    return Part.Wire([curve.toShape()])


def sweep_wire(path_wire, diameter):
    """Sweep a circle of the given diameter along the path; returns the wire solid (Part.Solid)."""
    diameter = float(diameter)
    if diameter <= 0.0:
        raise WireBondError(_("Wire diameter must be greater than zero."))

    edge = path_wire.Edges[0]
    start = edge.valueAt(edge.FirstParameter)
    tangent = _normalize(
        edge.tangentAt(edge.FirstParameter), _("path start tangent")
    )

    profile = Part.Wire([Part.makeCircle(diameter / 2.0, start, tangent)])
    solid = path_wire.makePipeShell([profile], True, False)

    # OCCT sometimes returns an inward facing shell (negative volume); flip it
    volume = solid.Volume
    if volume < 0.0:
        fixed = solid.copy()
        fixed.reverse()
        solid = fixed
    if not solid.isValid():
        App.Console.PrintWarning(
            _("WireBond: the swept result is not a valid solid; please check "
              "whether the wire diameter is too small.\n")
        )
    return solid


#: Bond bump shapes selectable on the panel
BUMP_NONE = "none"
BUMP_SPHERE = "sphere"
BUMP_FRUSTUM = "frustum"
BUMP_MODES = (BUMP_NONE, BUMP_SPHERE, BUMP_FRUSTUM)


def bond_bumps(centre1, centre2, mode=BUMP_SPHERE,
               diameter=DEFAULT_BALL_DIAMETER,
               top_diameter=DEFAULT_FRUSTUM_TOP_DIAMETER,
               bottom_diameter=DEFAULT_FRUSTUM_BOTTOM_DIAMETER,
               direction=None):
    """Create a bond bump at each centroid, in the shape selected by ``mode``.

    ``mode`` is one of :data:`BUMP_NONE`, :data:`BUMP_SPHERE` or
    :data:`BUMP_FRUSTUM`:

    * ``none`` - returns an empty list (no bump geometry);
    * ``sphere`` - a ball of ``diameter``, the classic ball bond;
    * ``frustum`` - a truncated cone from ``bottom_diameter`` (sitting on the
      pad) to ``top_diameter``, with a height of ``diameter``.

    ``direction`` is the outward normal of the pad the bump sits on; the sphere
    ignores it, the frustum is oriented along it so its wider or narrower end
    faces the pad as intended. Coordinates are global, as produced by
    :func:`global_face`.
    """
    # An unset value means "use the default shape", not "no bump": only an
    # explicit "none" disables the geometry.
    if mode is None or mode == "":
        mode = BUMP_SPHERE
    else:
        mode = str(mode).strip().lower()

    if mode in (BUMP_NONE, "off", "disabled", "0", "false"):
        return []
    if mode not in (BUMP_SPHERE, BUMP_FRUSTUM):
        # be forgiving about unknown values: fall back to the classic ball
        mode = BUMP_SPHERE

    height = float(diameter)
    if height <= 0.0:
        raise WireBondError(_("Ball diameter must be greater than zero."))

    centres = [Vector(c.x, c.y, c.z) for c in (centre1, centre2)]
    bumps = []

    if mode == BUMP_SPHERE:
        radius = height / 2.0
        for centre in centres:
            bumps.append(Part.makeSphere(radius, centre))
        return bumps

    # frustum: radius of the end sitting on the pad is "bottom", the other is "top"
    bottom_radius = float(bottom_diameter) / 2.0
    top_radius = float(top_diameter) / 2.0
    if bottom_radius <= 0.0 or top_radius <= 0.0:
        raise WireBondError(_("Ball diameter must be greater than zero."))

    axis = Vector(0, 0, 1) if direction is None else Vector(
        direction.x, direction.y, direction.z)
    if axis.Length < 1e-12:
        axis = Vector(0, 0, 1)
    axis.normalize()

    for centre in centres:
        if abs(bottom_radius - top_radius) < 1e-9:
            # A frustum with equal radii is a cylinder, and OCC's makeCone
            # refuses equal radii ("creation of cone failed"). This is the
            # default state, since both diameters fall back to BallDiameter.
            bumps.append(Part.makeCylinder(bottom_radius, height, centre,
                                           axis, 360))
        else:
            bumps.append(Part.makeCone(bottom_radius, top_radius, height,
                                       centre, axis, 360))
    return bumps


def bond_balls(centre1, centre2, diameter=DEFAULT_BALL_DIAMETER):
    """Backwards compatible wrapper: two spherical bumps of ``diameter``."""
    return bond_bumps(centre1, centre2, mode=BUMP_SPHERE, diameter=diameter)


def plane_face(frame, margin=DEFAULT_PLANE_MARGIN, width_factor=0.35):
    """Visual rectangle of the bisector plane (helper plane, shown on its own).

    The rectangle extends ``margin`` beyond both ends of the connecting line,
    and its width is a fraction of the line length.
    """
    half_w = max(frame.length * float(width_factor), 1e-6) + float(margin)
    u0, u1 = -abs(float(margin)), frame.length + abs(float(margin))
    v0, v1 = -half_w, half_w
    pts = [
        frame.origin + frame.xdir * u + frame.ydir * v
        for (u, v) in ((u0, v0), (u1, v0), (u1, v1), (u0, v1), (u0, v0))
    ]
    return Part.Face(Part.makePolygon(pts))


# ----------------------------------------------------------------------
# One-shot interface (used by the command, scripts and tests)
# ----------------------------------------------------------------------
def compute_from_faces(face1, face2, wire_diameter=DEFAULT_WIRE_DIAMETER,
                       clearance=DEFAULT_CLEARANCE,
                       peak_ratio=DEFAULT_PEAK_RATIO,
                       rise_angle=DEFAULT_RISE_ANGLE,
                       fall_angle=DEFAULT_FALL_ANGLE,
                       make_solid=True,
                       ball_diameter=DEFAULT_BALL_DIAMETER,
                       top_diameter=None,
                       bottom_diameter=None,
                       start_ball_mode=BUMP_SPHERE,
                       end_ball_mode=BUMP_SPHERE,
                       lead_distance=DEFAULT_LEAD_DISTANCE,
                       rotation_deg=DEFAULT_PLANE_ROTATION):
    """Compute the bisector plane, the gold wire and the bond bumps from two faces.

    ``rotation_deg``: rotation of the wire plane about the centroid line (deg),
    default 0. ``start_ball_mode`` / ``end_ball_mode`` select the bump shape at
    each end (see :func:`bond_bumps`).
    """
    c1, n1 = face_centre_and_normal(face1)
    c2, n2 = face_centre_and_normal(face2)
    frame = make_frame(c1, n1, c2, n2, rotation_deg=rotation_deg)

    points2d = loop_profile(frame.length, clearance, peak_ratio,
                            rise_angle, fall_angle,
                            lead_distance=lead_distance)
    points3d = to_world(frame, points2d)
    centre_line = build_centreline(points3d)

    solid = None
    if make_solid:
        solid = sweep_wire(centre_line, wire_diameter)

    if top_diameter is None:
        top_diameter = ball_diameter
    if bottom_diameter is None:
        bottom_diameter = ball_diameter

    # Bumps sit on their own pad, so each follows that face's outward normal.
    # The two ends may use different shapes: C1 (first bond point) and C2.
    balls = []
    for centre, normal, mode in ((c1, n1, start_ball_mode),
                                 (c2, n2, end_ball_mode)):
        if mode == BUMP_NONE:
            continue
        balls.extend(bond_bumps(
            centre, centre, mode=mode, diameter=ball_diameter,
            top_diameter=top_diameter, bottom_diameter=bottom_diameter,
            direction=normal))

    return {
        "frame": frame,
        "centre1": c1,
        "centre2": c2,
        "normal1": n1,
        "normal2": n2,
        "points2d": points2d,
        "points3d": points3d,
        "centre_line": centre_line,
        "solid": solid,
        "balls": balls,
        "plane": plane_face(frame),
    }
