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
5. build the *loop frame* of the wire profile (see :func:`horizontal_frame`):
   its X axis is the line where the first pad's plane meets the wire plane - the
   "horizontal" direction a bonder is programmed in - and its Y axis is the
   in-plane perpendicular to X, made positive towards the first face normal;
6. generate a wire loop inside P connecting C1 and C2; its shape is a list of
   control points ``(ratio, height)``: ``ratio`` is the position along the A-E
   span (0 = A, 1 = E) and ``height`` is the absolute height above A's level,
   both measured in the loop frame;
7. sweep a circle of diameter ``wire_diameter`` along that curve to obtain the
   gold wire solid.
"""

import math
import re
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
    "horizontal_frame",
    "format_loop_points",
    "parse_loop_points",
    "normalise_loop_points",
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
#: Default loop points, as ``(ratio, height_mm)`` pairs. A single pair is the
#: classic apex: ``ratio`` is the old ``PeakRatio`` (0.40) and ``height_mm`` the
#: old ``Clearance`` (0.2 mm = 200 um above A's level). Extra pairs extend the
#: 5 point loop into a ``4 + N`` point spline (see :func:`loop_profile`).
DEFAULT_LOOP_POINTS = ((0.40, 0.2),)
DEFAULT_RISE_ANGLE = 75.0      # deg from the HORIZONTAL plane; 90 deg = straight
#                                up. A steep take-off, as in the reference sketch.
DEFAULT_FALL_ANGLE = 15.0      # deg from the HORIZONTAL plane; a shallower landing
#                                than the take-off, again following the sketch
DEFAULT_BALL_DIAMETER = 0.05   # bond ball diameter 50 um (about 2.5x the wire diameter)
DEFAULT_FRUSTUM_TOP_DIAMETER = 0.05 # bond frustum top diameter
DEFAULT_FRUSTUM_BOTTOM_DIAMETER = 0.05 # bond frustum bottom diameter
DEFAULT_LEAD_DISTANCE = 0.03   # 30 um along the rise/fall ray. Swept against the
#                                reference proportions, 30 um gives a crest about
#                                125 um wide with an 14% descent deviation, a good
#                                compromise (see scripts/scan_angles.py)
DEFAULT_PLANE_ROTATION = 0.0   # wire plane rotation about the centroid line (deg), 0 = coincident
DEFAULT_PLANE_MARGIN = 2.0     # visual margin of the helper plane rectangle (mm)

#: Local frame of the bisector (wire) plane: ``xdir`` along the centroid line,
#: ``ydir`` the in-plane "up", ``zdir`` the plane normal, ``length`` = |C2 - C1|.
Frame = namedtuple("Frame", "origin xdir ydir zdir length")

#: Frame the wire profile is drawn in (a "bonder view" of the wire plane):
#:
#: * ``origin`` - A, the centroid of the first face;
#: * ``xdir``   - the *horizontal* axis: where the plane of the first pad meets
#:   the wire plane (its in-plane level line);
#: * ``ydir``   - the *height* axis: the in-plane perpendicular to ``xdir``,
#:   made positive towards the first face normal, so ``+y`` points away from the
#:   pad;
#: * ``zdir``   - the normal of the wire plane (``xdir x ydir``);
#: * ``span_x`` / ``span_y`` - the coordinates of E in this frame. ``span_x`` is
#:   always positive (it is C2 seen along the level line) and ``span_y`` is the
#:   height difference E - A (negative when the second pad is lower).
LoopFrame = namedtuple("LoopFrame", "origin xdir ydir zdir span_x span_y")


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


def horizontal_frame(frame, normal1):
    """Build the frame the wire profile is drawn in (the "bonder view").

    The profile is not laid out along the A-E line but along the *level* line of
    the first pad, exactly as a wire bonder is programmed::

        +y  (height)
         ^     x = ratio * span_x     y = absolute height above A
         |        *B
         |       /            the loop
         |      A-------------------------------* E
         +----- +x  (the level line: pad 1 plane ^ wire plane)

    * **x** (horizontal) is where the plane of the first pad meets the wire
      plane. It is the direction in which the wire runs away from the pad, and
      it is the same line for every wire that starts on a flat pad, whatever the
      second pad does;
    * **y** (height) is the in-plane perpendicular to ``x``. Its positive sense
      is the one closer to ``normal1`` (the outward normal of the first face),
      so ``+y`` always points away from the pad and a positive height means
      "above the pad", never into it;
    * the origin is A (the first centroid) and the returned ``span_x`` /
      ``span_y`` are the coordinates of E, i.e. the horizontal distance and the
      height difference between the two pads.

    With two flat pads facing the same way this degenerates to the familiar
    case ``x`` along ``C1 -> C2`` and ``y`` straight up, so the profile is then
    exactly the one produced before the level line was introduced.

    ``normal1`` must be the outward normal of the face the wire starts on; the
    wire plane (``frame``) has to contain the level line, which it does for any
    face whose normal has a component along ``frame.zdir``.
    """
    n1 = Vector(normal1.x, normal1.y, normal1.z)
    zdir = frame.zdir

    # In-plane component of the pad normal: the level line is perpendicular to
    # it, so it (or its opposite) is the height axis. Its positive sense is the
    # one closer to n1, i.e. away from the first pad.
    height_dir = n1 - zdir * float(n1.dot(zdir))
    if height_dir.Length < 1e-9:
        raise WireBondError(
            _("The first pad lies inside the wire plane, so the loop has no "
              "horizontal direction; please select a pad whose plane crosses "
              "the wire plane.")
        )
    vertical = _normalize(height_dir, _("loop height direction"))
    # The horizontal axis is the in-plane perpendicular to the height axis. The
    # cross product order is what makes (x, y, z) right handed - and that in
    # turn makes span_x positive whenever the two pads are laid out sensibly
    # (x . xdir = y . ydir >= 0, because ydir is the in-plane bisector of the
    # normals). Flipping x instead would silently flip the sign of the heights.
    horizontal = _normalize(vertical.cross(zdir), _("loop horizontal direction"))

    # Express E (the far end of the centroid line) in the new axes.
    delta = frame.xdir * frame.length
    span_x = float(delta.dot(horizontal))
    span_y = float(delta.dot(vertical))

    return LoopFrame(frame.origin, horizontal, vertical, zdir, span_x, span_y)


# ----------------------------------------------------------------------
# Wire loop profile
# ----------------------------------------------------------------------
#: Shape of the wire loop, drawn in the *loop frame* of :func:`horizontal_frame`
#: (``x`` = horizontal, ``y`` = height above the first pad). The two ends are
#: fixed by the lead-in / lead-out rays and the middle is described by a list of
#: *loop points*:
#:
#: * **A** - start, on the first pad, at ``(0, 0)``;
#: * **B** - *up start*, ``AB = lead_distance`` along the ``rise_angle`` ray
#:   leaving A;
#: * **loop points** - the user supplied ``(ratio, height)`` pairs. ``ratio``
#:   (0..1) places the point along the horizontal distance between the pads
#:   (``x = ratio * span_x``) and ``height`` (mm) is its **absolute** height
#:   above A's level. A single point recreates the classic apex - together with
#:   B and D it is the old 5 point loop, with ``ratio`` = the old ``PeakRatio``
#:   and ``height`` = the old ``Clearance``. Every extra point turns the loop
#:   into a ``4 + N`` point spline, which is what allows a flat top or a straight
#:   descent to be described;
#: * **D** - *up end*, ``ED = lead_distance`` along the ``fall_angle`` ray
#:   leaving E  (the spec sheet writes this as ``CD``; ``ED`` is meant, to
#:   mirror ``AB``);
#: * **E** - end, on the second pad, at ``(span_x, span_y)``.
#:
#:      B        *  *  *  *        D
#:      *   (the loop points)      *
#:     /                            \
#:    A                              E
#:
#: Both angles are measured **from the horizontal plane** (the ``x`` axis): 0 deg
#: is level and points at the other pad, 90 deg is straight up. That is the frame
#: a bonder is programmed in, and the angle does not change when the pads are at
#: different heights. The angle therefore says directly how steeply the wire
#: leaves and lands, which is the quantity a bonder engineer tunes.
MAX_ANGLE = 180.0          # stay just short of vertical, so B/D keep an x offset
MIN_POINT_GAP = 0.002     # minimum u gap between two loop points, as a fraction of L

#: separator between two ``ratio,height`` pairs in the persisted text form
_PAIR_SEP = ";"
#: separator between the ratio and the height inside one pair
_VALUE_SEP = ","


def format_loop_points(points):
    """Serialise ``(ratio, height_mm)`` pairs into a compact, stable string.

    The text form is ``"0.4,0.2;0.6,0.18"``: ``;`` separates the points and ``,``
    separates the position ratio from the height (in millimetres). It is
    deliberately locale independent (no decimal comma) so that it survives being
    stored in a FreeCAD property or in the user parameters.
    """
    parts = []
    for item in points or ():
        try:
            ratio = float(item[0])
            height = float(item[1])
        except Exception:
            continue
        parts.append("{:.6g}{}{:.6g}".format(ratio, _VALUE_SEP, height))
    return _PAIR_SEP.join(parts)


def parse_loop_points(text):
    """Parse a string produced by :func:`format_loop_points`.

    Returns a tuple of ``(ratio, height_mm)`` pairs, possibly empty. The reader
    is forgiving: points may be separated by ``;`` or a newline, and an entry may
    use ``,`` or whitespace between the ratio and the height. Entries that cannot
    be read as two numbers are skipped.
    """
    if not text:
        return ()
    points = []
    for chunk in re.split(r"[;\n]", str(text)):
        chunk = chunk.strip()
        if not chunk:
            continue
        bits = re.split(r"[,\s]+", chunk)
        if len(bits) < 2:
            continue
        try:
            ratio = float(bits[0])
            height = float(bits[1])
        except ValueError:
            continue
        points.append((ratio, height))
    return tuple(points)


def normalise_loop_points(points):
    """Return a clean tuple of ``(ratio, height_mm)`` pairs.

    A string is parsed first (so callers may pass the property value directly).
    Malformed entries are dropped, the ratio is clamped to ``[0, 1]`` and a
    negative height is rejected. The pairs are sorted by ratio with a stable
    sort, so equal ratios keep the caller's order; the strict spacing the spline
    needs is applied later in :func:`loop_profile`, where the span is known.
    """
    if isinstance(points, str):
        points = parse_loop_points(points)
    cleaned = []
    for item in points or ():
        try:
            ratio = float(item[0])
            height = float(item[1])
        except Exception:
            continue
        if not (math.isfinite(ratio) and math.isfinite(height)):
            continue
        if height < 0.0:
            raise WireBondError(_("Loop point heights must not be negative."))
        cleaned.append((min(max(ratio, 0.0), 1.0), height))
    cleaned.sort(key=lambda pair: pair[0])
    return tuple(cleaned)


def _spread_positions(values, gap, low, high):
    """Return ``values`` as strictly increasing positions with a minimum spacing.

    ``values`` are the requested positions in ascending order; the result stays
    inside ``[low, high]`` and each position is at least ``gap`` from the
    previous one. When the requested points cannot all fit with that gap the gap
    is reduced so that they do - this keeps the spline's "strictly increasing
    parameter" requirement satisfied instead of raising on a crowded list.
    """
    count = len(values)
    if count == 0:
        return []
    if high <= low:
        high = low + max(float(gap), 1e-9)
    span = high - low
    step = float(gap)
    if count > 1 and step * (count - 1) > span:
        step = span / float(count - 1)
    result = []
    for index, value in enumerate(values):
        lower = float(low) if index == 0 else result[-1] + step
        upper = float(high) - (count - 1 - index) * step
        if upper < lower:
            upper = lower
        result.append(min(max(float(value), lower), upper))
    return result


def loop_profile(span_x, span_y=0.0, loop_points=DEFAULT_LOOP_POINTS,
                 rise_angle=DEFAULT_RISE_ANGLE, fall_angle=DEFAULT_FALL_ANGLE,
                 lead_distance=DEFAULT_LEAD_DISTANCE):
    """Return the wire loop control points ``[(x, y), ...]`` in the loop frame.

    ``x`` is the horizontal distance from A along the level line of the first pad
    and ``y`` is the absolute height above A, both in the frame built by
    :func:`horizontal_frame` - which is also the arrangement used by
    ``scripts/wirebond_sketch.py``. The result is ``A``, ``B``, every loop point,
    ``D`` and ``E`` - i.e. ``4 + N`` points for ``N`` loop points:

    ============================  ===========================================
    point                         position
    ============================  ===========================================
    A                             ``(0, 0)``
    B                             ``(lead*cos(rise), lead*sin(rise))``
    loop point i                  ``(ratio_i * span_x, height_i)``
    D                             ``(span_x - lead*cos(fall), span_y + lead*sin(fall))``
    E                             ``(span_x, span_y)``
    ============================  ===========================================

    ``span_x`` / ``span_y`` describe where the second pad sits: ``span_x`` is the
    horizontal distance between the pads (the projection of ``C1 -> C2`` on the
    level line, always positive) and ``span_y`` is its height relative to A
    (negative when the second pad is lower).

    With a single loop point ``(ratio, height)`` the result is exactly the older
    five point profile in which ``ratio`` was ``peak_ratio`` and ``height`` was
    ``clearance``; with two pads at the same height it is also exactly the
    profile produced before the level line was introduced (``x`` = along the
    centroid line, ``y`` = above it).

    ``rise_angle`` and ``fall_angle`` are measured from the **horizontal plane**
    (the ``x`` axis): 0 deg is level and points towards the other pad, 90 deg is
    straight up. The wire therefore leaves A along the rise ray and reaches E
    from the fall ray, each for a distance of ``lead_distance``, and the angles
    keep their meaning whatever ``span_y`` is.

    Only the first argument is positional, so an older call
    ``loop_profile(length, loop_points, rise, fall, lead)`` has to be updated:
    ``length`` is now ``span_x`` and ``span_y`` comes second.
    """
    span_x = float(span_x)
    span_y = float(span_y or 0.0)
    if span_x <= 0.0:
        raise WireBondError(
            _("The horizontal distance between the two pads must be greater "
              "than zero; the pads have to be offset along the level line.")
        )

    if isinstance(loop_points, str):
        loop_points = parse_loop_points(loop_points)
    points = normalise_loop_points(loop_points)

    lead = float(lead_distance or 0.0)
    if lead <= 0.0:
        lead = DEFAULT_LEAD_DISTANCE

    rise = math.radians(min(max(float(rise_angle), 0.0), MAX_ANGLE))
    fall = math.radians(min(max(float(fall_angle), 0.0), MAX_ANGLE))

    # place the interior points by their ratio of the horizontal span, keeping
    # them strictly inside A..E and strictly increasing (the spline needs that)
    margin = span_x * 1e-4
    gap = span_x * MIN_POINT_GAP
    requested = [ratio * span_x for ratio, _height in points]
    positions = _spread_positions(requested, gap, margin, span_x - margin)
    interior = [(x, points[index][1]) for index, x in enumerate(positions)]

    # Horizontal extent of each lead. A limited lead keeps B before the first
    # loop point and D after the last one.
    dx_b = lead * math.cos(rise)
    dx_d = lead * math.cos(fall)
    if interior:
        first_x = interior[0][0]
        last_x = interior[-1][0]
        if dx_b > 0.0:
            dx_b = min(dx_b, first_x * 0.98)
        if dx_d > 0.0:
            dx_d = min(dx_d, (span_x - last_x) * 0.98)
    else:
        # no interior point: keep B and D apart so the spline stays valid
        dx_b = min(dx_b, span_x * 0.49)
        dx_d = min(dx_d, span_x * 0.49)

    profile = [
        (0.0, 0.0),                                             # A
        (dx_b, lead * math.sin(rise)),                          # B
    ]
    profile.extend(interior)                                    # the loop points
    profile.append((span_x - dx_d, span_y + lead * math.sin(fall)))  # D
    profile.append((span_x, span_y))                            # E
    return profile


def to_world(frame, points2d):
    """Map the 2D control points ``(x, y)`` of a loop frame into 3D space.

    ``frame`` is either the wire plane (:class:`Frame`, ``C1 + x*xdir + y*ydir``)
    or the loop frame (:class:`LoopFrame`, ``A + x*xdir + y*ydir``); both are used
    exactly the same way, which is why the profile is axis independent.
    """
    origin = frame.origin
    return [origin + frame.xdir * x + frame.ydir * y for (x, y) in points2d]


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
                       loop_points=DEFAULT_LOOP_POINTS,
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

    The wire lives in the bisector plane (``frame``, built by :func:`make_frame`)
    but its shape - the entry/exit angles, the lead-in distance and the loop
    points - is laid out in the loop frame of :func:`horizontal_frame`: the X
    axis is the line where the first pad's plane meets the wire plane (the level
    line) and the Y axis is the in-plane perpendicular, positive away from the
    first pad. That is the frame a bonder is programmed in, and it makes the
    rise/fall angles and the loop point heights independent of the height
    difference between the two pads.

    ``loop_points`` is the list of ``(ratio, height_mm)`` control points that
    shapes the loop (see :func:`loop_profile`). ``rotation_deg``: rotation of the
    wire plane about the centroid line (deg), default 0. ``start_ball_mode`` /
    ``end_ball_mode`` select the bump shape at each end (see :func:`bond_bumps`).
    """
    c1, n1 = face_centre_and_normal(face1)
    c2, n2 = face_centre_and_normal(face2)
    frame = make_frame(c1, n1, c2, n2, rotation_deg=rotation_deg)
    loop_frame = horizontal_frame(frame, n1)

    points2d = loop_profile(loop_frame.span_x, loop_frame.span_y, loop_points,
                            rise_angle, fall_angle, lead_distance=lead_distance)
    points3d = to_world(loop_frame, points2d)
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
        "loop_frame": loop_frame,
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
