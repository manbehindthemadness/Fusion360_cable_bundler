/** Preserve the picked face's viewing side while normalizing its surface normal. */
function contactOrientation(normal) {
  const length = Math.hypot(...normal);
  return length > 1e-9 ? normal.map((value) => value / length) : [0, 0, 1];
}

/** Keep board-forward (+Y) up when visible, using +Z for its end-on side faces. */
function contactPlanePoint(point, normal, parentAxes = null) {
  const validAxes = Array.isArray(parentAxes) && parentAxes.length === 3
    && parentAxes.every((axis) => Array.isArray(axis) && axis.length === 3
      && axis.every(Number.isFinite) && Math.hypot(...axis) > 1e-9);
  const axes = validAxes ? parentAxes.map(contactOrientation) : [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
  const facing = contactOrientation(normal);
  const inPlane = (axis) => {
    const alignment = axis.reduce((sum, value, index) => sum + value * facing[index], 0);
    const projected = axis.map((value, index) => value - alignment * facing[index]);
    return { projected, length: Math.hypot(...projected) };
  };
  const reference = [axes[1], axes[2], axes[0], [0, 1, 0], [0, 0, 1], [1, 0, 0]]
    .map(inPlane).find((candidate) => candidate.length > 1e-6);
  const yAxis = reference.projected.map((value) => value / reference.length);
  const xAxis = [
    yAxis[1] * facing[2] - yAxis[2] * facing[1],
    yAxis[2] * facing[0] - yAxis[0] * facing[2],
    yAxis[0] * facing[1] - yAxis[1] * facing[0],
  ];
  return [
    point.reduce((sum, value, index) => sum + value * xAxis[index], 0),
    -point.reduce((sum, value, index) => sum + value * yAxis[index], 0),
  ];
}

/** Remove subpixel detail while retaining corners, winding, and separate holes. */
function simplifyContactOutline(points, tolerance = 0.3) {
  if (points.length < 4) return points;
  const distanceSquared = (first, second) => (
    (first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2
  );
  const vertices = points.filter((point, index) => (
    !index || distanceSquared(point, points[index - 1]) > 1e-12
  ));
  if (vertices.length > 1 && distanceSquared(vertices[0], vertices.at(-1)) <= 1e-12) {
    vertices.pop();
  }
  if (vertices.length < 4) return vertices;
  let opposite = 1;
  for (let index = 2; index < vertices.length; index += 1) {
    if (distanceSquared(vertices[0], vertices[index])
      > distanceSquared(vertices[0], vertices[opposite])) opposite = index;
  }
  const simplifyChain = (chain) => {
    const keep = new Set([0, chain.length - 1]);
    const pending = [[0, chain.length - 1]];
    while (pending.length) {
      const [start, end] = pending.pop();
      const first = chain[start];
      const last = chain[end];
      const span = distanceSquared(first, last);
      let farthest = -1;
      let deviation = tolerance * tolerance;
      for (let index = start + 1; index < end; index += 1) {
        const point = chain[index];
        const fraction = span ? Math.max(0, Math.min(1,
          ((point[0] - first[0]) * (last[0] - first[0])
            + (point[1] - first[1]) * (last[1] - first[1])) / span)) : 0;
        const projected = [first[0] + fraction * (last[0] - first[0]),
          first[1] + fraction * (last[1] - first[1])];
        const error = distanceSquared(point, projected);
        if (error > deviation) {
          deviation = error;
          farthest = index;
        }
      }
      if (farthest >= 0) {
        keep.add(farthest);
        pending.push([start, farthest], [farthest, end]);
      }
    }
    return chain.filter((_point, index) => keep.has(index));
  };
  const first = simplifyChain(vertices.slice(0, opposite + 1));
  const second = simplifyChain([...vertices.slice(opposite), vertices[0]]);
  const simplified = [...first.slice(0, -1), ...second.slice(0, -1)];
  return simplified.length >= 3 ? simplified : vertices;
}
