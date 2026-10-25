"""
Match a planar cap to its location as well as its plane, including coplanar ends.
"""

from cable_bundler.routing.geometry import Vector3, difference, dot, magnitude


def cap_matches(
    endpoint: Vector3,
    tangent: Vector3,
    plane_origin: Vector3,
    plane_normal: Vector3,
    boundary_center: Vector3,
) -> bool:
    """
    Check a symmetric cap's center and plane under the existing native tolerances.

    Positions are millimeters. Bounding-box centers are valid for the symmetric
    original lobe contours and circular trace caps in this experiment only.
    This does not measure native flow, intermediate skin or mechanical compliance.
    """
    return (
        abs(dot(plane_normal, tangent)) > 1 - 1e-7
        and abs(dot(difference(plane_origin, endpoint), tangent)) < 1e-5
        and magnitude(difference(boundary_center, endpoint)) < 1e-5
    )
