# Percentage-based local thickness pinch

This is the geometric rule clarified with the user's **Macaroni demo v1**. It
replaces the historical `reach / 0.78` and `3.1D` radius restrictions for new
percentage-policy routing experiments. Those historical records remain legacy.

For a circular section with thickness/diameter `D`, half-thickness `h = D/2`,
path radius `R` and allowed fraction `p`:

`utilization = h / R`, `inside radius = R - h`, and `utilization <= p < 1`.

The demo has `R = 25 mm`, `h = 24.9 mm`: utilization is 99.6% and inside radius
is 0.1 mm, or 0.4% of R. The configured default is 99.6%; it is adjustable and
does not represent a material/strain rating. Exactly 100% is singular and rejects.

## A ribbon is one coupled surface

The current compatible chart uses perpendicular unit directors T and W, normal
`N = W × T`, centre progress `c`, tangent turn `b`, ruling slope `eta`, and its
parameter derivative `g`. Its nominal thickness envelope is:

`X(u,q,v) = r(u) + q*(W + eta*T) + v*N`, with `-D/2 <= v <= D/2`.

Material-lane progress is `s(q) = c + q*g`. The chart's director equations give
the normal-offset volume Jacobian, up to orientation:

`J_thickness(q,v) = s(q) - v*b*(1 + eta²)`.

Therefore the coupled local pinch utilization is:

`h * |b| * (1 + eta²) / min_q(s(q))`.

The turn bound uses the configured p. Width enters through material progress,
not an orientation-independent enclosing full-width radius. The factor
`1 + eta²` accounts for maximum principal curvature of this developable surface;
checking only the three path curvatures would miss it. Circular tubes use their
perpendicular circular sections instead and have no ruling-slope factor.

At the same material station, ideal path radii are `R(q) = s(q)/|b|`. The red
reference radii use `s(q)/b_allowed`. Both vary linearly across symmetric material
offsets, so the centre lies between A and B. The circles follow the selected
station; independent worst points are not mixed into a new-policy triplet.

## Independent inspection and limits of the evidence

`inspection/pinch_geometry.py` obtains principal curvatures from first and second
fundamental forms of the frozen cubic ruled surface, independently of the chart's
eta/J expression. It checks three guides plus two interior width samples, at four
fractions of every cubic. It retains pinch/order violations without repairing the
interpolation. A 65-point graph is a separate display sample, not the audit grid.

This establishes sampled local thickness regularity for the nominal envelope.
It does not establish global self-clearance, the unspecified bonded outer contour,
elastic equilibrium, native construction or complete physical acceptance.

New seed lengths use the percentage rule's half-thickness scale. They no longer
inherit the legacy reach/ruling length allowance. The solver still fits endpoint
poses; this change does not add a shortest-route objective or prove loops necessary.
