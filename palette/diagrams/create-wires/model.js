/** Connectivity and staged assignment model for wire creation. */

/** Coordinate pathway-boundary selection and the planned wire-creation workspace. */

let cancelActiveWireCreationSelection = null;

/** Return the stable graph identity for one pathway boundary. */
function wireCreationBoundaryKey(pathwayId, endpoint) {
  return `pathway:${pathwayId}:${endpoint}`;
}

/** Return every pathway boundary physically reachable from one boundary. */
function wireCreationReachableBoundaries(harness, sourceKey) {
  const graph = new Map();
  const addNode = (key) => {
    if (!graph.has(key)) graph.set(key, new Set());
  };
  const connect = (left, right) => {
    addNode(left);
    addNode(right);
    graph.get(left).add(right);
    graph.get(right).add(left);
  };
  harness.pathways.forEach((pathway) => connect(
    wireCreationBoundaryKey(pathway.pathwayId, "start"),
    wireCreationBoundaryKey(pathway.pathwayId, "end"),
  ));
  (harness.junctions || []).forEach((junction) => {
    const junctionKey = `junction:${junction.junctionId}`;
    addNode(junctionKey);
    (junction.pathwayRelationships || []).forEach((relationship) => connect(
      junctionKey,
      wireCreationBoundaryKey(relationship.pathwayId, relationship.endpoint),
    ));
  });

  const reachable = new Set();
  const pending = [sourceKey];
  while (pending.length) {
    const current = pending.shift();
    if (reachable.has(current)) continue;
    reachable.add(current);
    (graph.get(current) || []).forEach((neighbor) => pending.push(neighbor));
  }
  reachable.delete(sourceKey);
  return reachable;
}

/** Return ends at the two selected boundaries for group assignment. */
function wireCreationDisconnectedGroups(harness, left, right) {
  return {
    left: left.groups,
    right: right.groups,
  };
}

/** Format one selected boundary for a popup column heading. */
function wireCreationBoundaryLabel(boundary) {
  const side = boundary.endpoint === "start" ? "A" : "B";
  return `${boundary.pathway.name || "Unnamed pathway"} · End ${side}`;
}

/** Return the durable identity needed to rebuild one popup boundary. */
function wireCreationBoundaryState(boundary) {
  return { pathwayId: boundary.pathway.pathwayId, endpoint: boundary.endpoint };
}

/** Rebuild one popup boundary from refreshed harness state. */
function resolveWireCreationBoundary(harness, state) {
  const pathway = harness.pathways.find(
    (candidate) => candidate.pathwayId === state.pathwayId,
  );
  if (!pathway || !["start", "end"].includes(state.endpoint)) return null;
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  return {
    key: wireCreationBoundaryKey(pathway.pathwayId, state.endpoint),
    pathway,
    endpoint: state.endpoint,
    groups: relationshipEndGroups(harness, pathway.pathwayId, state.endpoint, connections),
  };
}

/** Highlight the geometry represented by one popup end group. */
function highlightWireCreationEnd(harness, group) {
  if (group.wireGroupId) {
    return highlightMember(harness, "wire_group", group.wireGroupId);
  }
  if (group.connectionId) {
    return highlightMember(harness, "connection", group.connectionId);
  }
  return undefined;
}

/** Create the transient ordered state for a newly opened wire workspace. */
function initialWireCreationAssignments(groups) {
  const rightByGroup = new Map(
    groups.right.filter((group) => group.wireGroupId).map((group) => [
      group.wireGroupId, group,
    ]),
  );
  const pairedIds = new Set();
  const initialPartners = {};
  const rows = [];
  groups.left.forEach((left) => {
    const right = left.wireGroupId && rightByGroup.get(left.wireGroupId);
    if (!right) return;
    pairedIds.add(left.connectionId);
    pairedIds.add(right.connectionId);
    initialPartners[left.connectionId] = right.connectionId;
    initialPartners[right.connectionId] = left.connectionId;
    rows.push({
      left: { connectionId: left.connectionId, returnIndex: 0 },
      right: { connectionId: right.connectionId, returnIndex: 0 },
    });
  });
  return {
    pools: {
      left: groups.left.map((group) => group.connectionId).filter((id) => !pairedIds.has(id)),
      right: groups.right.map((group) => group.connectionId).filter((id) => !pairedIds.has(id)),
    },
    rows,
    initialPartners,
    movedConnectionIds: {},
    renames: {},
    deletedConnectionIds: {},
  };
}

/** Reconcile popup-only assignments with refreshed harness data. */
function reconcileWireCreationAssignments(assignments, groups) {
  if (!assignments) return initialWireCreationAssignments(groups);
  if (!assignments.pools) assignments.pools = { left: [], right: [] };
  assignments.initialPartners ||= {};
  assignments.movedConnectionIds ||= {};
  assignments.renames ||= {};
  assignments.deletedConnectionIds ||= {};
  const available = {
    left: new Set(groups.left.map((group) => group.connectionId).filter(
      (connectionId) => !assignments.deletedConnectionIds[connectionId],
    )),
    right: new Set(groups.right.map((group) => group.connectionId).filter(
      (connectionId) => !assignments.deletedConnectionIds[connectionId],
    )),
  };
  const seen = { left: new Set(), right: new Set() };
  let newlyPendingRow = null;
  assignments.rows = (assignments.rows || []).map((row) => {
    const wasComplete = Boolean(row.left) && Boolean(row.right);
    const refreshed = { left: null, right: null };
    ["left", "right"].forEach((side) => {
      const item = row[side];
      if (item && available[side].has(item.connectionId) &&
          !seen[side].has(item.connectionId)) {
        refreshed[side] = item;
        seen[side].add(item.connectionId);
      }
    });
    if (wasComplete && Boolean(refreshed.left) !== Boolean(refreshed.right)) {
      newlyPendingRow = refreshed;
    }
    return refreshed;
  }).filter((row) => row.left || row.right);
  ["left", "right"].forEach((side) => {
    const pool = (assignments.pools?.[side] || []).filter((connectionId) => {
      if (!available[side].has(connectionId) || seen[side].has(connectionId)) return false;
      seen[side].add(connectionId);
      return true;
    });
    groups[side].forEach((group) => {
      if (!seen[side].has(group.connectionId)) {
        pool.push(group.connectionId);
        seen[side].add(group.connectionId);
      }
    });
    assignments.pools[side] = pool;
  });
  const pendingRows = assignments.rows.filter(
    (row) => Boolean(row.left) !== Boolean(row.right),
  );
  if (pendingRows.length > 1) {
    returnOtherPendingWireCreationRows(assignments, newlyPendingRow || pendingRows[0]);
  }
  return assignments;
}

/** Insert an item into its outer pool without exceeding the current list bounds. */
function insertWireCreationPoolItem(assignments, side, item, index) {
  const pool = assignments.pools[side];
  const target = Math.max(0, Math.min(index, pool.length));
  pool.splice(target, 0, item.connectionId);
}

/** Return every incomplete row except the requested row to its outer pool. */
function returnOtherPendingWireCreationRows(assignments, keepRow) {
  assignments.rows = assignments.rows.filter((row) => {
    if (row === keepRow || Boolean(row.left) === Boolean(row.right)) return true;
    const side = row.left ? "left" : "right";
    const item = row[side];
    insertWireCreationPoolItem(assignments, side, item, item.returnIndex);
    return false;
  });
}

/** Move one outer-pool card into a center row. */
function assignWireCreationPoolItem(assignments, side, poolIndex, rowIndex) {
  const connectionId = assignments.pools[side][poolIndex];
  if (!connectionId) return;
  const pendingIndex = assignments.rows.findIndex(
    (row) => Boolean(row.left) !== Boolean(row.right),
  );
  const opposite = side === "left" ? "right" : "left";
  const pending = assignments.rows[pendingIndex];
  assignments.pools[side].splice(poolIndex, 1);
  const item = { connectionId, returnIndex: poolIndex };
  if (pending && pending[opposite] && !pending[side]) {
    pending[side] = item;
    return;
  }
  if (pending && pending[side]) {
    insertWireCreationPoolItem(assignments, side, pending[side], pending[side].returnIndex);
    assignments.rows.splice(pendingIndex, 1);
    if (pendingIndex < rowIndex) rowIndex -= 1;
  }
  const row = { left: null, right: null };
  row[side] = item;
  assignments.rows.splice(Math.max(0, Math.min(rowIndex, assignments.rows.length)), 0, row);
}

/** Return one center card to its source pool and preserve the one-pending-row invariant. */
function unassignWireCreationRowItem(assignments, side, rowIndex, poolIndex) {
  const row = assignments.rows[rowIndex];
  const item = row?.[side];
  if (!item) return;
  if (assignments.initialPartners?.[item.connectionId]) {
    assignments.movedConnectionIds ||= {};
    assignments.movedConnectionIds[item.connectionId] = true;
  }
  insertWireCreationPoolItem(assignments, side, item, poolIndex);
  row[side] = null;
  if (!row.left && !row.right) assignments.rows.splice(rowIndex, 1);
  else returnOtherPendingWireCreationRows(assignments, row);
}

/** Exchange two occupied center-row members without moving their partners. */
function swapWireCreationRowItems(assignments, side, sourceRowIndex, targetRowIndex) {
  if (sourceRowIndex === targetRowIndex) return;
  const source = assignments.rows[sourceRowIndex];
  const target = assignments.rows[targetRowIndex];
  if (!source?.[side] || !target?.[side]) return;
  [source[side], target[side]].forEach((item) => {
    if (assignments.initialPartners?.[item.connectionId]) {
      assignments.movedConnectionIds ||= {};
      assignments.movedConnectionIds[item.connectionId] = true;
    }
  });
  [source[side], target[side]] = [target[side], source[side]];
}

/** Remove one standalone end from the staged workspace without persisting it. */
function deleteWireCreationEnd(assignments, connectionId) {
  assignments.deletedConnectionIds[connectionId] = true;
  delete assignments.renames[connectionId];
  ["left", "right"].forEach((side) => {
    assignments.pools[side] = assignments.pools[side].filter((id) => id !== connectionId);
  });
  assignments.rows.forEach((row) => {
    ["left", "right"].forEach((side) => {
      if (row[side]?.connectionId === connectionId) row[side] = null;
    });
  });
  assignments.rows = assignments.rows.filter((row) => row.left || row.right);
  const pendingRows = assignments.rows.filter(
    (row) => Boolean(row.left) !== Boolean(row.right),
  );
  if (pendingRows.length > 1) returnOtherPendingWireCreationRows(assignments, pendingRows[0]);
}

/** Return the complete left/right relationships currently staged in the center. */
function wireCreationCompletePairings(assignments) {
  return assignments.rows.filter((row) => row.left && row.right).map((row) => ({
    leftConnectionId: row.left.connectionId,
    rightConnectionId: row.right.connectionId,
  }));
}

/** Return persisted-pair members that the current arrangement explicitly reassigns. */
function wireCreationDetachedConnectionIds(assignments, pairings, deleted) {
  const finalPartners = {};
  pairings.forEach((pairing) => {
    finalPartners[pairing.leftConnectionId] = pairing.rightConnectionId;
    finalPartners[pairing.rightConnectionId] = pairing.leftConnectionId;
  });
  return Object.keys(assignments.movedConnectionIds).filter(
    (connectionId) => !deleted.has(connectionId)
      && finalPartners[connectionId] !== assignments.initialPartners[connectionId],
  );
}

/** Resolve staged connected status using the same detach-then-merge semantics as Save. */
function wireCreationStagedConnectedIds(harness, assignments) {
  const deleted = new Set(Object.keys(assignments.deletedConnectionIds));
  const pairings = wireCreationCompletePairings(assignments);
  const detached = new Set(
    wireCreationDetachedConnectionIds(assignments, pairings, deleted),
  );
  const groups = (harness.wireGroups || []).map((group) => (
    (group.connectionIds || []).filter(
      (connectionId) => !deleted.has(connectionId) && !detached.has(connectionId),
    )
  ));
  const groupIndex = (connectionId) => groups.findIndex(
    (members) => members.includes(connectionId),
  );
  pairings.forEach((pairing) => {
    const leftIndex = groupIndex(pairing.leftConnectionId);
    const rightIndex = groupIndex(pairing.rightConnectionId);
    if (leftIndex >= 0 && leftIndex === rightIndex) return;
    if (leftIndex < 0 && rightIndex < 0) {
      groups.push([pairing.leftConnectionId, pairing.rightConnectionId]);
    } else if (leftIndex < 0) {
      groups[rightIndex].push(pairing.leftConnectionId);
    } else if (rightIndex < 0) {
      groups[leftIndex].push(pairing.rightConnectionId);
    } else {
      const keepIndex = Math.min(leftIndex, rightIndex);
      const removeIndex = Math.max(leftIndex, rightIndex);
      groups[keepIndex].push(...groups[removeIndex]);
      groups.splice(removeIndex, 1);
    }
  });
  return new Set(groups.filter((members) => members.length >= 2).flat());
}

/** Render one draggable end card with the master diagram's end interactions. */

