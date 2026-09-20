/** Candidate topology layout construction and compaction. */

function relationshipRootCandidates(component) {
  const junctions = component.nodes.filter((node) => node.kind === "junction");
  return (junctions.length ? junctions : component.nodes).slice().sort((left, right) => (
    right.neighbors.length - left.neighbors.length
    || left.index - right.index
    || left.id.localeCompare(right.id)
  ));
}

function relationshipLayerCrossingCount(component, positions) {
  let crossings = 0;
  component.edges.forEach((edge, index) => component.edges.slice(index + 1).forEach((other) => {
    const source = component.nodes.find((node) => node.id === edge.sourceId);
    const target = component.nodes.find((node) => node.id === edge.targetId);
    const otherSource = component.nodes.find((node) => node.id === other.sourceId);
    const otherTarget = component.nodes.find((node) => node.id === other.targetId);
    if (!source || !target || !otherSource || !otherTarget) return;
    if (source.depth !== otherSource.depth || target.depth !== otherTarget.depth) return;
    if (source.id === otherSource.id || target.id === otherTarget.id) return;
    const sourceOrder = positions.get(source.id) - positions.get(otherSource.id);
    const targetOrder = positions.get(target.id) - positions.get(otherTarget.id);
    if (sourceOrder * targetOrder < 0) crossings += 1;
  }));
  return crossings;
}

/** Return a stable same-depth order after deterministic median sweeps. */
function optimizeRelationshipNodeOrder(component) {
  const layers = new Map();
  component.nodes.forEach((node) => {
    if (!layers.has(node.depth)) layers.set(node.depth, []);
    layers.get(node.depth).push(node);
  });
  const depths = [...layers.keys()].sort((left, right) => left - right);
  const original = new Map();
  depths.forEach((depth) => layers.get(depth).forEach((node, index) => {
    original.set(node.id, index);
  }));
  const positions = new Map(original);
  const adjacentPositions = (node) => component.edges.flatMap((edge) => {
    if (edge.sourceId === node.id) return [positions.get(edge.targetId)];
    if (edge.targetId === node.id) return [positions.get(edge.sourceId)];
    return [];
  }).filter((position) => position !== undefined);
  for (let pass = 0; pass < 6; pass += 1) {
    const orderedDepths = pass % 2 ? depths.slice().reverse() : depths;
    orderedDepths.forEach((depth) => {
      layers.get(depth).sort((left, right) => {
        const score = (node) => {
          const adjacent = adjacentPositions(node);
          return adjacent.length
            ? adjacent.reduce((total, value) => total + value, 0) / adjacent.length
            : positions.get(node.id);
        };
        return score(left) - score(right)
          || original.get(left.id) - original.get(right.id)
          || left.id.localeCompare(right.id);
      }).forEach((node, index) => positions.set(node.id, index));
    });
  }
  const selected = relationshipLayerCrossingCount(component, positions)
    <= relationshipLayerCrossingCount(component, original) ? positions : original;
  return component.nodes.slice().sort((left, right) => (
    left.depth - right.depth || selected.get(left.id) - selected.get(right.id)
  ));
}

function relationshipOrderedNeighbors(component, node, orderMode) {
  const nodes = new Map(component.nodes.map((candidate) => [candidate.id, candidate]));
  const ordered = node.neighbors.slice().sort((leftId, rightId) => {
    const left = nodes.get(leftId);
    const right = nodes.get(rightId);
    return orderMode === "dense"
      ? right.neighbors.length - left.neighbors.length || left.id.localeCompare(right.id)
      : left.id.localeCompare(right.id);
  });
  return orderMode === "reverse" ? ordered.reverse() : ordered;
}

/** Seed one component in topology rings around a candidate root and branch order. */
function radialRelationshipComponent(component, rotation, dimensions, root, orderMode) {
  const depths = new Map([[root.id, 0]]);
  const queue = [root];
  const traversal = [root];
  while (queue.length) {
    const node = queue.shift();
    relationshipOrderedNeighbors(component, node, orderMode).forEach((neighborId) => {
      if (depths.has(neighborId)) return;
      depths.set(neighborId, depths.get(node.id) + 1);
      const neighbor = component.nodes.find((candidate) => candidate.id === neighborId);
      queue.push(neighbor);
      traversal.push(neighbor);
    });
  }
  const rings = new Map();
  traversal.forEach((node) => {
    const depth = depths.get(node.id) || 0;
    if (!rings.has(depth)) rings.set(depth, []);
    rings.get(depth).push(node);
  });
  const positions = new Map([[root.id, { x: 0, y: 0 }]]);
  let radius = 0;
  let priorDiagonal = Math.hypot(
    dimensions.get(root.id).width,
    dimensions.get(root.id).height,
  );
  [...rings.keys()].sort((left, right) => left - right).slice(1).forEach((depth) => {
    const nodes = rings.get(depth);
    const maximumDiagonal = Math.max(...nodes.map((node) => {
      const size = dimensions.get(node.id);
      return Math.hypot(size.width, size.height);
    }));
    radius += priorDiagonal / 2 + maximumDiagonal / 2 + TOPOLOGY_CONNECTED_GAP;
    priorDiagonal = maximumDiagonal;
    nodes.forEach((node, index) => {
      const angle = rotation * Math.PI / 2 - Math.PI / 2
        + 2 * Math.PI * index / nodes.length;
      positions.set(node.id, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius });
    });
  });
  return positions;
}

function relationshipPairGap(component, firstId, secondId) {
  const connected = component.edges.some((edge) => (
    edge.sourceId === firstId && edge.targetId === secondId
    || edge.sourceId === secondId && edge.targetId === firstId
  ));
  return connected ? TOPOLOGY_CONNECTED_GAP : TOPOLOGY_NODE_GAP;
}

function relationshipNodePositionClears(component, node, point, positions, dimensions) {
  const size = dimensions.get(node.id);
  return component.nodes.every((other) => {
    if (other.id === node.id) return true;
    const otherPoint = positions.get(other.id);
    const otherSize = dimensions.get(other.id);
    const gap = relationshipPairGap(component, node.id, other.id);
    const horizontalClearance = Math.abs(otherPoint.x - point.x)
      - (size.width + otherSize.width) / 2;
    const verticalClearance = Math.abs(otherPoint.y - point.y)
      - (size.height + otherSize.height) / 2;
    return horizontalClearance >= gap || verticalClearance >= gap;
  });
}

/** Resolve rectangular overlap without changing deterministic topology order. */
function separateRelationshipNodes(component, positions, dimensions) {
  for (let iteration = 0; iteration < 80; iteration += 1) {
    let moved = false;
    component.nodes.forEach((node, index) => component.nodes.slice(index + 1).forEach((other) => {
      const first = positions.get(node.id);
      const second = positions.get(other.id);
      const firstSize = dimensions.get(node.id);
      const secondSize = dimensions.get(other.id);
      const gap = relationshipPairGap(component, node.id, other.id);
      const overlapX = (firstSize.width + secondSize.width) / 2 + gap
        - Math.abs(second.x - first.x);
      const overlapY = (firstSize.height + secondSize.height) / 2 + gap
        - Math.abs(second.y - first.y);
      if (overlapX <= 0 || overlapY <= 0) return;
      moved = true;
      if (overlapX < overlapY) {
        const direction = second.x === first.x
          ? (node.id.localeCompare(other.id) < 0 ? 1 : -1)
          : Math.sign(second.x - first.x);
        first.x -= direction * overlapX / 2;
        second.x += direction * overlapX / 2;
      } else {
        const direction = second.y === first.y
          ? (node.id.localeCompare(other.id) < 0 ? 1 : -1)
          : Math.sign(second.y - first.y);
        first.y -= direction * overlapY / 2;
        second.y += direction * overlapY / 2;
      }
    }));
    if (!moved) break;
  }
}

/** Remove remaining axis slack without crossing another node's protected envelope. */
function compactRelationshipAxes(component, positions, dimensions) {
  for (let pass = 0; pass < 12; pass += 1) {
    let moved = false;
    const centroid = component.nodes.reduce((point, node) => ({
      x: point.x + positions.get(node.id).x / component.nodes.length,
      y: point.y + positions.get(node.id).y / component.nodes.length,
    }), { x: 0, y: 0 });
    component.nodes.slice().sort((left, right) => (
      right.neighbors.length - left.neighbors.length || left.id.localeCompare(right.id)
    )).forEach((node) => {
      ["x", "y"].forEach((axis) => {
        const point = positions.get(node.id);
        let movement = centroid[axis] - point[axis];
        while (Math.abs(movement) >= 0.5) {
          const candidate = { ...point, [axis]: point[axis] + movement };
          if (relationshipNodePositionClears(
            component, node, candidate, positions, dimensions,
          )) {
            point[axis] = candidate[axis];
            moved = true;
            break;
          }
          movement /= 2;
        }
      });
    });
    if (!moved) break;
  }
}

function relationshipRectangleSupport(size, direction) {
  return Math.abs(direction.x) * size.width / 2 + Math.abs(direction.y) * size.height / 2;
}

/** Pull connected nodes toward their minimum safe edge gap without introducing overlap. */
function compactRelationshipComponent(component, positions, dimensions, rootId) {
  for (let iteration = 0; iteration < 48; iteration += 1) {
    component.edges.forEach((edge) => {
      const source = positions.get(edge.sourceId);
      const target = positions.get(edge.targetId);
      const difference = { x: target.x - source.x, y: target.y - source.y };
      const length = Math.hypot(difference.x, difference.y) || 1;
      const direction = { x: difference.x / length, y: difference.y / length };
      const desired = relationshipRectangleSupport(dimensions.get(edge.sourceId), direction)
        + relationshipRectangleSupport(dimensions.get(edge.targetId), direction)
        + TOPOLOGY_CONNECTED_GAP;
      const adjustment = Math.max(0, length - desired) * 0.18;
      if (!adjustment) return;
      const sourceWeight = edge.sourceId === rootId ? 0 : edge.targetId === rootId ? 1 : 0.5;
      const targetWeight = 1 - sourceWeight;
      source.x += direction.x * adjustment * sourceWeight;
      source.y += direction.y * adjustment * sourceWeight;
      target.x -= direction.x * adjustment * targetWeight;
      target.y -= direction.y * adjustment * targetWeight;
    });
    const centroid = component.nodes.reduce((point, node) => ({
      x: point.x + positions.get(node.id).x / component.nodes.length,
      y: point.y + positions.get(node.id).y / component.nodes.length,
    }), { x: 0, y: 0 });
    component.nodes.forEach((node) => {
      if (node.id === rootId) return;
      const point = positions.get(node.id);
      point.x += (centroid.x - point.x) * 0.025;
      point.y += (centroid.y - point.y) * 0.025;
    });
    separateRelationshipNodes(component, positions, dimensions);
  }
  compactRelationshipAxes(component, positions, dimensions);
}

function relationshipBounds(nodes, positions, dimensions) {
  const left = Math.min(...nodes.map((node) => (
    positions.get(node.id).x - dimensions.get(node.id).width / 2
  )));
  const right = Math.max(...nodes.map((node) => (
    positions.get(node.id).x + dimensions.get(node.id).width / 2
  )));
  const top = Math.min(...nodes.map((node) => (
    positions.get(node.id).y - dimensions.get(node.id).height / 2
  )));
  const bottom = Math.max(...nodes.map((node) => (
    positions.get(node.id).y + dimensions.get(node.id).height / 2
  )));
  return { left, right, top, bottom, width: right - left, height: bottom - top };
}

function relationshipEdgeCrossings(components, positions) {
  const orientation = (first, second, third) => (
    (second.x - first.x) * (third.y - first.y)
    - (second.y - first.y) * (third.x - first.x)
  );
  return components.reduce((count, component) => count + component.edges.reduce(
    (edgeCount, edge, index) => edgeCount + component.edges.slice(index + 1).filter((other) => {
      if ([edge.sourceId, edge.targetId].some((id) => (
        id === other.sourceId || id === other.targetId
      ))) return false;
      const first = positions.get(edge.sourceId);
      const second = positions.get(edge.targetId);
      const third = positions.get(other.sourceId);
      const fourth = positions.get(other.targetId);
      return orientation(first, second, third) * orientation(first, second, fourth) < 0
        && orientation(third, fourth, first) * orientation(third, fourth, second) < 0;
    }).length,
    0,
  ), 0);
}

/** Build, orient, and compact one deterministic cardinal-topology candidate. */
function legacyRelationshipTopologyLayoutCandidate(components, specification, options = {}) {
  const componentLayouts = components.map((component, componentIndex) => {
    const root = specification.roots[componentIndex];
    let dimensions = new Map(component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node),
    ]));
    let positions = radialRelationshipComponent(
      component, specification.rotation, dimensions, root, specification.orderMode,
    );
    let dockSides = new Map(component.nodes.filter((node) => node.kind === "pathway")
      .map((node) => [node.id, relationshipPathwayDockSides(component, node, positions)]));
    dimensions = new Map(component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
    ]));
    positions = radialRelationshipComponent(
      component, specification.rotation, dimensions, root, specification.orderMode,
    );
    dockSides = new Map(component.nodes.filter((node) => node.kind === "pathway")
      .map((node) => [node.id, relationshipPathwayDockSides(component, node, positions)]));
    dimensions = new Map(component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
    ]));
    separateRelationshipNodes(component, positions, dimensions);
    compactRelationshipComponent(component, positions, dimensions, root.id);
    return { component, positions, dockSides, dimensions,
      bounds: relationshipBounds(component.nodes, positions, dimensions) };
  });
  const padding = TOPOLOGY_CANVAS_PADDING;
  const gap = TOPOLOGY_COMPONENT_GAP;
  const totalArea = componentLayouts.reduce(
    (total, item) => total + (item.bounds.width + gap) * (item.bounds.height + gap), 0,
  );
  const viewportAspect = Math.max(0.5, Math.min(
    2.5,
    (options.width || 1) / Math.max(1, options.height || 1),
  ));
  const rowTarget = Math.max(260, Math.sqrt(totalArea * viewportAspect));
  const positions = new Map();
  const dockSides = new Map();
  const dimensions = new Map();
  let x = padding;
  let y = padding;
  let rowHeight = 0;
  let maximumRight = padding;
  componentLayouts.forEach((item) => {
    if (x > padding && x + item.bounds.width > rowTarget + padding) {
      x = padding;
      y += rowHeight + gap;
      rowHeight = 0;
    }
    item.component.nodes.forEach((node) => {
      const point = item.positions.get(node.id);
      positions.set(node.id, {
        x: x + point.x - item.bounds.left,
        y: y + point.y - item.bounds.top,
      });
      dimensions.set(node.id, item.dimensions.get(node.id));
    });
    item.dockSides.forEach((sides, id) => dockSides.set(id, sides));
    maximumRight = Math.max(maximumRight, x + item.bounds.width);
    rowHeight = Math.max(rowHeight, item.bounds.height);
    x += item.bounds.width + gap;
  });
  const width = Math.max(260, maximumRight + padding);
  const height = Math.max(260, y + rowHeight + padding);
  const edgeLength = components.flatMap((component) => component.edges).reduce(
    (total, edge) => {
      const source = positions.get(edge.sourceId);
      const target = positions.get(edge.targetId);
      return total + Math.hypot(target.x - source.x, target.y - source.y);
    }, 0,
  );
  return {
    positions, dockSides, dimensions, width, height,
    rotation: specification.rotation,
    layoutKey: specification.key,
    crossings: relationshipEdgeCrossings(components, positions),
    edgeLength,
  };
}

function relationshipLayerOrder(nodes, orderMode, optimizedOrder) {
  const ordered = nodes.slice().sort((left, right) => (
    orderMode === "dense"
      ? right.neighbors.length - left.neighbors.length
        || optimizedOrder.get(left.id) - optimizedOrder.get(right.id)
      : optimizedOrder.get(left.id) - optimizedOrder.get(right.id)
        || left.id.localeCompare(right.id)
  ));
  return orderMode === "reverse" ? ordered.reverse() : ordered;
}

/** Place topology layers without overlap using immutable visible-node dimensions. */
function layeredRelationshipGeometry(components, specification, dimensions) {
  const horizontal = specification.flow === "horizontal";
  const componentLayouts = components.map((component, componentIndex) => {
    const root = specification.roots[componentIndex];
    const depths = new Map([[root.id, 0]]);
    const queue = [root];
    while (queue.length) {
      const node = queue.shift();
      relationshipOrderedNeighbors(component, node, specification.orderMode)
        .forEach((neighborId) => {
          if (depths.has(neighborId)) return;
          depths.set(neighborId, depths.get(node.id) + 1);
          queue.push(component.nodes.find((candidate) => candidate.id === neighborId));
        });
    }
    const depthComponent = {
      ...component,
      nodes: component.nodes.map((node) => ({ ...node, depth: depths.get(node.id) || 0 })),
    };
    const optimizedOrder = new Map(optimizeRelationshipNodeOrder(depthComponent).map(
      (node, index) => [node.id, index],
    ));
    const byDepth = new Map();
    component.nodes.forEach((node) => {
      const depth = depths.get(node.id) || 0;
      if (!byDepth.has(depth)) byDepth.set(depth, []);
      byDepth.get(depth).push(node);
    });
    const sortedDepths = [...byDepth.keys()].sort((left, right) => left - right);
    if (specification.direction === "reverse") sortedDepths.reverse();
    const layers = sortedDepths.map((depth) => {
      const nodes = relationshipLayerOrder(
        byDepth.get(depth), specification.orderMode, optimizedOrder,
      );
      const sizes = nodes.map((node) => dimensions.get(node.id));
      return {
        nodes,
        width: horizontal
          ? Math.max(...sizes.map((size) => size.width))
          : sizes.reduce((total, size) => total + size.width, 0)
            + Math.max(0, sizes.length - 1) * TOPOLOGY_NODE_GAP,
        height: horizontal
          ? sizes.reduce((total, size) => total + size.height, 0)
            + Math.max(0, sizes.length - 1) * TOPOLOGY_NODE_GAP
          : Math.max(...sizes.map((size) => size.height)),
      };
    });
    const width = horizontal
      ? layers.reduce((total, layer) => total + layer.width, 0)
        + Math.max(0, layers.length - 1) * TOPOLOGY_CONNECTED_GAP
      : Math.max(...layers.map((layer) => layer.width));
    const height = horizontal
      ? Math.max(...layers.map((layer) => layer.height))
      : layers.reduce((total, layer) => total + layer.height, 0)
        + Math.max(0, layers.length - 1) * TOPOLOGY_CONNECTED_GAP;
    const positions = new Map();
    let flowOffset = 0;
    layers.forEach((layer) => {
      let crossOffset = horizontal ? (height - layer.height) / 2 : (width - layer.width) / 2;
      layer.nodes.forEach((node) => {
        const size = dimensions.get(node.id);
        positions.set(node.id, horizontal ? {
          x: flowOffset + layer.width / 2,
          y: crossOffset + size.height / 2,
        } : {
          x: crossOffset + size.width / 2,
          y: flowOffset + layer.height / 2,
        });
        crossOffset += (horizontal ? size.height : size.width) + TOPOLOGY_NODE_GAP;
      });
      flowOffset += (horizontal ? layer.width : layer.height) + TOPOLOGY_CONNECTED_GAP;
    });
    return { component, positions, width, height };
  });
  const positions = new Map();
  let componentOffset = TOPOLOGY_CANVAS_PADDING;
  let maximumCrossExtent = 0;
  componentLayouts.forEach((layout) => {
    layout.component.nodes.forEach((node) => {
      const point = layout.positions.get(node.id);
      positions.set(node.id, horizontal ? {
        x: point.x + TOPOLOGY_CANVAS_PADDING,
        y: point.y + componentOffset,
      } : {
        x: point.x + componentOffset,
        y: point.y + TOPOLOGY_CANVAS_PADDING,
      });
    });
    componentOffset += (horizontal ? layout.height : layout.width) + TOPOLOGY_COMPONENT_GAP;
    maximumCrossExtent = Math.max(
      maximumCrossExtent, horizontal ? layout.width : layout.height,
    );
  });
  return {
    positions,
    width: horizontal
      ? maximumCrossExtent + TOPOLOGY_CANVAS_PADDING * 2
      : componentOffset - TOPOLOGY_COMPONENT_GAP + TOPOLOGY_CANVAS_PADDING,
    height: horizontal
      ? componentOffset - TOPOLOGY_COMPONENT_GAP + TOPOLOGY_CANVAS_PADDING
      : maximumCrossExtent + TOPOLOGY_CANVAS_PADDING * 2,
  };
}

/** Build a layered candidate whose dimensions and endpoint orientation converge. */
function relationshipTopologyLayoutCandidate(components, specification) {
  let dockSides = new Map(components.flatMap((component) => component.nodes
    .filter((node) => node.kind === "pathway")
    .map((node) => [node.id, { start: "left", end: "right" }])));
  let dimensions;
  let geometry;
  for (let pass = 0; pass < 4; pass += 1) {
    dimensions = new Map(components.flatMap((component) => component.nodes.map((node) => [
      node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
    ])));
    geometry = layeredRelationshipGeometry(components, specification, dimensions);
    const nextDockSides = new Map(components.flatMap((component) => component.nodes
      .filter((node) => node.kind === "pathway")
      .map((node) => [
        node.id, relationshipPathwayDockSides(
          component, node, geometry.positions, specification.flow,
        ),
      ])));
    const unchanged = [...nextDockSides].every(([id, sides]) => (
      sides.start === dockSides.get(id)?.start && sides.end === dockSides.get(id)?.end
    ));
    dockSides = nextDockSides;
    if (unchanged) break;
  }
  dimensions = new Map(components.flatMap((component) => component.nodes.map((node) => [
    node.id, relationshipNodeDimensions(node, dockSides.get(node.id)),
  ])));
  geometry = layeredRelationshipGeometry(components, specification, dimensions);
  const edgeLength = components.flatMap((component) => component.edges).reduce(
    (total, edge) => {
      const source = geometry.positions.get(edge.sourceId);
      const target = geometry.positions.get(edge.targetId);
      return total + Math.abs(target.x - source.x) + Math.abs(target.y - source.y);
    }, 0,
  );
  return {
    positions: geometry.positions,
    dockSides,
    dimensions,
    width: Math.max(260, geometry.width),
    height: Math.max(260, geometry.height),
    rotation: specification.rotation,
    layoutKey: specification.key,
    crossings: relationshipEdgeCrossings(components, geometry.positions),
    edgeLength,
  };
}

function relationshipLayoutSpecifications(components) {
  const roots = components.map(relationshipRootCandidates);
  const maximumRootCount = Math.max(...roots.map((items) => items.length));
  const specifications = [];
  for (let rootIndex = 0; rootIndex < maximumRootCount; rootIndex += 1) {
    ["horizontal", "vertical"].forEach((flow, flowIndex) => {
      ["forward", "reverse"].forEach((direction, directionIndex) => {
        ["stable", "reverse", "dense"].forEach((orderMode) => {
          const selectedRoots = roots.map((items) => items[rootIndex % items.length]);
          const rotation = flowIndex + directionIndex * 2;
          specifications.push({
            flow, direction, orderMode, rotation, roots: selectedRoots,
            key: [flow, direction, orderMode, ...selectedRoots.map((root) => root.id)].join("|"),
          });
        });
      });
    });
  }
  return specifications.slice(0, TOPOLOGY_LAYOUT_CANDIDATE_LIMIT);
}

/** Materialize one candidate as plain geometry without changing rendered elements. */
function materializeRelationshipLayout(components, layout) {
  return components.map((component) => ({
    ...component,
    nodes: component.nodes.map((node) => {
      const center = layout.positions.get(node.id);
      const dimensions = layout.dimensions.get(node.id);
      const left = center.x - dimensions.width / 2;
      const top = center.y - dimensions.height / 2;
      if (node.kind !== "pathway") {
        return {
          ...node, ...dimensions, left, top, hubCenter: center,
          dockPoints: null,
        };
      }
      const dockSides = layout.dockSides.get(node.id);
      const dockPoints = {};
      ["start", "end"].forEach((endpoint) => {
        const point = dimensions.docks[endpoint];
        dockPoints[dockSides[endpoint]] = { x: left + point.x, y: top + point.y };
      });
      return {
        ...node,
        ...dimensions,
        left,
        top,
        dockSides,
        dockPoints,
        hubCenter: { x: left + dimensions.centerX, y: top + dimensions.centerY },
      };
    }),
  }));
}
