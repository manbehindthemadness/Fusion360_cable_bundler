"""
Freeze photo-inspired return and crossover poses without tracing interior paths.

Images establish visual test families, not dimensions, material limits or a
specified winding class. These are three developmental boundary configurations.
"""

from cable_bundler.routing.geometry import Vector3

from .endpoint_first import EndpointCase

REFERENCE_IMAGES = (
    "examples/ribbons/1__53567.jpg",
    "examples/ribbons/87109414.jpeg.avif",
    "examples/ribbons/CA197__32659.webp",
    "examples/ribbons/images.jpeg",
    "examples/ribbons/images 2.jpeg",
    "examples/ribbons/images 3.jpeg",
    "examples/ribbons/Belden-Flat-Ribbon-Cable.webp",
    "examples/ribbons/TempFlex_FEP_1600x650.avif",
    "examples/ribbons/Ribbon-Cable-Types.jpg.webp",
)


def reference_cases() -> tuple[EndpointCase, ...]:
    """
    Register a broad reverse-heading loop, rolled crossover and compact return.

    Keep 19 conductors at 1.5 mm diameter and the unchanged five-width sphere.
    Feasibility is unknown before evaluation, especially for the compact return;
    reject without enlarging its spacing or altering endpoint poses.
    """
    return (
        EndpointCase(
            "reference_broad_return",
            Vector3(-45, 0, 0),
            Vector3(45, 0, 0),
            Vector3(0, 0, 1),
            Vector3(0, 0, -1),
            Vector3(0, 1, 0),
            Vector3(0, 1, 0),
        ),
        EndpointCase(
            "reference_banked_crossover",
            Vector3(-40, 0, 0),
            Vector3(0, 50, 15),
            Vector3(1, 0, 0),
            Vector3(0, 1, 0),
            Vector3(0, 1, 0),
            Vector3(0, 0, 1),
        ),
        EndpointCase(
            "reference_compact_return",
            Vector3(-20, 0, 0),
            Vector3(20, 0, 10),
            Vector3(1, 0, 0),
            Vector3(-1, 0, 0),
            Vector3(0, 1, 0),
            Vector3(0, 1, 0),
        ),
    )
