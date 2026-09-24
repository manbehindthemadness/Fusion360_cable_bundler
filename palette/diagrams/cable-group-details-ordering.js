/** Order Cable Details graph columns to reduce visible route crossings. */

/** Count edge inversions between matching pairs of adjacent diagram columns. */
function cableGroupDetailsEdgeCrossingCount(edges, positions, depths) {
  let crossings = 0;
  edges.forEach((edge, index) => {
    const leftDepth = depths.get(edge.leftId);
    const rightDepth = depths.get(edge.rightId);
    const sourceId = leftDepth <= rightDepth ? edge.leftId : edge.rightId;
    const targetId = sourceId === edge.leftId ? edge.rightId : edge.leftId;
    edges.slice(index + 1).forEach((other) => {
      const otherLeftDepth = depths.get(other.leftId);
      const otherRightDepth = depths.get(other.rightId);
      const otherSourceId = otherLeftDepth <= otherRightDepth
        ? other.leftId : other.rightId;
      const otherTargetId = otherSourceId === other.leftId ? other.rightId : other.leftId;
      if (depths.get(sourceId) !== depths.get(otherSourceId)
        || depths.get(targetId) !== depths.get(otherTargetId)
        || sourceId === otherSourceId || targetId === otherTargetId) return;
      const sourceOrder = positions.get(sourceId) - positions.get(otherSourceId);
      const targetOrder = positions.get(targetId) - positions.get(otherTargetId);
      if (sourceOrder * targetOrder < 0) crossings += 1;
    });
  });
  return crossings;
}

/** Prefer fewer crossings, then shorter vertical travel through the layered graph. */
function cableGroupDetailsOrderingScore(topology, positions, depths) {
  const crossings = cableGroupDetailsEdgeCrossingCount(topology.edges, positions, depths);
  const verticalTravel = topology.edges.reduce((total, edge) => (
    total + Math.abs(positions.get(edge.leftId) - positions.get(edge.rightId))
  ), 0);
  return { crossings, verticalTravel };
}

/** Return whether a candidate layered ordering is better than the retained one. */
function cableGroupDetailsOrderingIsBetter(candidate, retained) {
  return candidate.crossings < retained.crossings
    || (candidate.crossings === retained.crossings
      && candidate.verticalTravel < retained.verticalTravel);
}

/** Return a branch-preserving node order when the route topology is a forest. */
function cableGroupDetailsForestNodeOrder(topology, preferredRootId, stableKeys) {
  const nodes = new Map(topology.nodes.map((node) => [node.id, node]));
  const visited = new Set();
  const componentRoots = [];
  const orderedNodeIds = new Map();
  topology.nodes.slice().sort((left, right) => (
    stableKeys.get(left.id).localeCompare(stableKeys.get(right.id))
  )).forEach((start) => {
    if (visited.has(start.id)) return;
    const component = [];
    const pending = [start.id];
    visited.add(start.id);
    while (pending.length) {
      const currentId = pending.shift();
      component.push(currentId);
      nodes.get(currentId).neighbors.forEach((neighborId) => {
        if (visited.has(neighborId) || !nodes.has(neighborId)) return;
        visited.add(neighborId);
        pending.push(neighborId);
      });
    }
    const rootId = component.includes(preferredRootId)
      ? preferredRootId
      : component.slice().sort((leftId, rightId) => (
        stableKeys.get(leftId).localeCompare(stableKeys.get(rightId))
      ))[0];
    componentRoots.push({ rootId });
  });
  const edgeCount = topology.edges.length;
  const componentCount = componentRoots.length;
  if (edgeCount !== topology.nodes.length - componentCount) return null;

  let leafIndex = 0;
  componentRoots.forEach(({ rootId }) => {
    const visit = (nodeId, parentId) => {
      const children = [...nodes.get(nodeId).neighbors]
        .filter((neighborId) => neighborId !== parentId && nodes.has(neighborId))
        .sort((leftId, rightId) => (
          stableKeys.get(leftId).localeCompare(stableKeys.get(rightId))
        ));
      if (!children.length) {
        const order = leafIndex;
        leafIndex += 1;
        orderedNodeIds.set(nodeId, order);
        return order;
      }
      const childOrders = children.map((childId) => visit(childId, nodeId));
      const order = Math.min(...childOrders);
      orderedNodeIds.set(nodeId, order);
      return order;
    };
    visit(rootId, null);
  });
  return orderedNodeIds;
}

/** Order layered nodes with deterministic barycentric sweeps. */
function optimizeCableGroupDetailsNodeOrder(topology, columns, depths, preferredRootId) {
  const columnDepths = [...columns.keys()].sort((left, right) => left - right);
  const stableKeys = new Map(topology.nodes.map((node) => [
    node.id, `${node.kind}:${node.label}:${node.id}`,
  ]));
  const stableOrder = new Map();
  columnDepths.forEach((depth) => columns.get(depth).sort((left, right) => (
    stableKeys.get(left.id).localeCompare(stableKeys.get(right.id))
  )));
  const copyOrder = () => new Map(columnDepths.map((depth) => [
    depth, columns.get(depth).map((node) => node.id),
  ]));
  stableOrder.set("stable", copyOrder());
  stableOrder.set("reverse", new Map(columnDepths.map((depth) => [
    depth, [...stableOrder.get("stable").get(depth)].reverse(),
  ])));
  const positions = new Map();
  let bestOrder = stableOrder.get("stable");
  let bestScore;
  const compareScores = (left, right) => (
    left.crossings - right.crossings || left.verticalTravel - right.verticalTravel
  );
  const evaluate = (initialOrder) => {
    const nodesById = new Map(topology.nodes.map((node) => [node.id, node]));
    columnDepths.forEach((depth) => {
      columns.set(depth, initialOrder.get(depth).map((nodeId) => nodesById.get(nodeId)));
    });
    const recordPositions = () => columnDepths.forEach((depth) => (
      columns.get(depth).forEach((node, index) => positions.set(node.id, index))
    ));
    recordPositions();
    let candidateOrder = copyOrder();
    let candidateScore = cableGroupDetailsOrderingScore(topology, positions, depths);
    const sweep = (forward) => {
      const orderedDepths = forward
        ? columnDepths.slice(1) : columnDepths.slice(0, -1).reverse();
      orderedDepths.forEach((depth) => {
        const adjacentDepth = depth + (forward ? -1 : 1);
        const scores = new Map(columns.get(depth).map((node) => {
          const adjacent = [...node.neighbors]
            .filter((neighborId) => depths.get(neighborId) === adjacentDepth)
            .map((neighborId) => positions.get(neighborId));
          const score = adjacent.length
            ? adjacent.reduce((total, position) => total + position, 0) / adjacent.length
            : positions.get(node.id);
          return [node.id, score];
        }));
        columns.get(depth).sort((left, right) => (
          scores.get(left.id) - scores.get(right.id)
          || stableKeys.get(left.id).localeCompare(stableKeys.get(right.id))
        ));
        columns.get(depth).forEach((node, index) => positions.set(node.id, index));
      });
    };
    for (let iteration = 0; iteration < 12; iteration += 1) {
      sweep(true);
      sweep(false);
      recordPositions();
      const score = cableGroupDetailsOrderingScore(topology, positions, depths);
      if (cableGroupDetailsOrderingIsBetter(score, candidateScore)) {
        candidateScore = score;
        candidateOrder = copyOrder();
      }
    }
    return { order: candidateOrder, score: candidateScore };
  };
  const initialOrders = [...stableOrder.values()];
  for (let offset = 1; offset <= 4; offset += 1) {
    initialOrders.push(new Map(columnDepths.map((depth) => {
      const nodes = stableOrder.get("stable").get(depth);
      const shift = nodes.length ? (offset * depth) % nodes.length : 0;
      return [depth, [...nodes.slice(shift), ...nodes.slice(0, shift)]];
    })));
  }
  const forestOrder = cableGroupDetailsForestNodeOrder(
    topology, preferredRootId, stableKeys,
  );
  if (forestOrder) {
    initialOrders.push(new Map(columnDepths.map((depth) => [
      depth,
      stableOrder.get("stable").get(depth).slice().sort((left, right) => (
        forestOrder.get(left) - forestOrder.get(right)
        || stableKeys.get(left).localeCompare(stableKeys.get(right))
      )),
    ])));
  }
  initialOrders.forEach((initialOrder) => {
    const candidate = evaluate(initialOrder);
    if (!bestScore || compareScores(candidate.score, bestScore) < 0) {
      bestOrder = candidate.order;
      bestScore = candidate.score;
    }
  });
  columnDepths.forEach((depth) => {
    const nodes = new Map(columns.get(depth).map((node) => [node.id, node]));
    columns.set(depth, bestOrder.get(depth).map((nodeId) => nodes.get(nodeId)));
  });
  columnDepths.forEach((depth) => columns.get(depth).forEach((node, index) => (
    positions.set(node.id, index)
  )));
  return cableGroupDetailsOrderingScore(topology, positions, depths);
}
