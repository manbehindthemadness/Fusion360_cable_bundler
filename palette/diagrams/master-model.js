/** Derive stable cable-group membership and topology for the master diagram. */

function relationshipGroupIds(groups) {
  return groups.map((group) => group.cableGroupId).filter(Boolean).join(" ");
}

function relationshipElementGroupIds(element) {
  const value = element.dataset?.cableGroupIds || element.dataset?.cableGroupId || "";
  return new Set(value.split(" ").filter(Boolean));
}

function relationshipSetsIntersect(left, right) {
  return [...left].some((value) => right.has(value));
}

/** Apply transient focus to every master-diagram element sharing group membership. */
function createRelationshipFocusController(container) {
  const itemClasses = [
    "relationship-topology-node",
    "relationship-topology-edge",
    "relationship-topology-port",
    "relationship-end-entry",
    "cable-trace",
    "stripe-trace",
    "trace-contrast-halo",
    "aggregate-trace",
  ];
  let pointerFocus = null;
  let keyboardFocus = null;
  let pointerEnabled = true;
  const sources = new Set();

  const items = () => [...new Set(itemClasses.flatMap(
    (className) => Array.from(container.querySelectorAll(`.${className}`)),
  ))];
  const clearClasses = () => {
    container.classList.remove("relationship-focus-active");
    items().forEach((item) => item.classList.remove(
      "relationship-focus-match", "relationship-focus-dimmed", "relationship-focus-source",
    ));
    sources.forEach((source) => source.classList.remove(
      "relationship-focus-match", "relationship-focus-dimmed", "relationship-focus-source",
    ));
  };
  const apply = () => {
    clearClasses();
    const focus = keyboardFocus || pointerFocus;
    if (!focus) return;
    container.classList.add("relationship-focus-active");
    const groupIds = new Set(focus.groupIds);
    const nodeIds = new Set(focus.nodeIds);
    items().forEach((item) => {
      const itemGroupIds = relationshipElementGroupIds(item);
      const itemNodeIds = new Set([
        item.dataset?.nodeId,
        item.dataset?.sourceId,
        item.dataset?.targetId,
      ].filter(Boolean));
      const matches = groupIds.size
        ? relationshipSetsIntersect(groupIds, itemGroupIds)
        : relationshipSetsIntersect(nodeIds, itemNodeIds);
      item.classList.add(matches ? "relationship-focus-match" : "relationship-focus-dimmed");
    });
    focus.source.classList.add("relationship-focus-source", "relationship-focus-match");
    focus.source.classList.remove("relationship-focus-dimmed");
  };
  const bind = (source, descriptor) => {
    sources.add(source);
    const focus = {
      source,
      groupIds: descriptor.groups.map((group) => group.cableGroupId),
      nodeIds: descriptor.nodeIds || [],
    };
    source.addEventListener("mouseenter", () => {
      if (!paletteHasFocus() || !pointerEnabled) return;
      pointerFocus = focus;
      apply();
    });
    source.addEventListener("mouseleave", () => {
      if (pointerFocus === focus) pointerFocus = null;
      apply();
    });
    source.addEventListener("focus", () => {
      keyboardFocus = focus;
      apply();
    });
    source.addEventListener("blur", () => {
      if (keyboardFocus === focus) keyboardFocus = null;
      apply();
    });
  };
  const setPointerEnabled = (value) => {
    pointerEnabled = value;
    container.dataset.hoverDisabled = `${!value}`;
    if (!pointerEnabled) {
      pointerFocus = null;
      apply();
      send("clear_highlight").catch(() => {});
    }
  };
  return { bind, setPointerEnabled };
}

function relationshipEndGroups(harness, pathwayId, endpoint, connections) {
  const cableGroupByConnection = new Map();
  (harness.cableGroups || []).forEach((cableGroup) => {
    (cableGroup.connectionIds || []).forEach((connectionId) => {
      cableGroupByConnection.set(connectionId, cableGroup);
    });
  });
  return (harness.standaloneEnds || [])
    .filter((end) => end.pathwayId === pathwayId && end.endpoint === endpoint)
    .map((end) => {
      const connection = connections.get(end.connectionId);
      const cableGroup = cableGroupByConnection.get(end.connectionId) || null;
      const label = connection?.name || `Missing End ${endpoint === "start" ? "A" : "B"}`;
      return {
        connectionId: end.connectionId,
        connectionName: connection?.name || "",
        groups: cableGroup ? [cableGroup] : [],
        standalone: true,
        cableGroupId: cableGroup?.cableGroupId || "",
        label,
        searchable: `${label} ${connection?.name || ""} ${cableGroup?.materials?.insulationMaterial || ""} ${cableGroup?.materials?.mainColor?.name || ""}`
          .toLocaleLowerCase(),
      };
    });
}

function relationshipPathwayGroups(harness, pathwayId) {
  return (harness.cableGroups || []).filter((group) => (
    (group.routeLegs || []).some((leg) => (leg.pathwayIds || []).includes(pathwayId))
  ));
}

/** Return the selected pathway and its exclusively downstream pathway branch. */
function relationshipPathwayDeletionIds(harness, pathwayId) {
  return relationshipBranchDeletionIds(harness, [pathwayId]);
}

/** Return exclusively downstream pathways reached from the supplied roots. */
function relationshipBranchDeletionIds(harness, rootPathwayIds) {
  const deletedPathwayIds = new Set(rootPathwayIds);
  let changed = true;
  while (changed) {
    changed = false;
    (harness.junctions || []).forEach((junction) => {
      const relationships = junction.pathwayRelationships || [];
      const incomingPathwayIds = relationships
        .filter((relationship) => relationship.endpoint === "end")
        .map((relationship) => relationship.pathwayId);
      if (!incomingPathwayIds.length || !incomingPathwayIds.every(
        (candidateId) => deletedPathwayIds.has(candidateId),
      )) return;
      relationships
        .filter((relationship) => relationship.endpoint === "start")
        .forEach((relationship) => {
          if (deletedPathwayIds.has(relationship.pathwayId)) return;
          deletedPathwayIds.add(relationship.pathwayId);
          changed = true;
        });
    });
  }
  return deletedPathwayIds;
}

function relationshipJunctionGroups(harness, junction) {
  return (harness.cableGroups || []).filter((group) => (
    (group.routeLegs || []).some((leg) => (
      (leg.controlSteps || []).some((step) => step.controlId === junction.controlId)
    ))
  ));
}

function relationshipTopology(harness) {
  const nodes = new Map();
  const edges = [];
  const addNode = (kind, item, index) => {
    const id = `${kind}:${kind === "pathway" ? item.pathwayId : item.junctionId}`;
    nodes.set(id, { id, kind, item, index, incoming: [], outgoing: [], neighbors: [] });
  };
  harness.pathways.forEach((pathway, index) => addNode("pathway", pathway, index));
  (harness.junctions || []).forEach((junction, index) => (
    addNode("junction", junction, harness.pathways.length + index)
  ));
  (harness.junctions || []).forEach((junction) => {
    const junctionId = `junction:${junction.junctionId}`;
    (junction.pathwayRelationships || []).forEach((relationship) => {
      const pathwayId = `pathway:${relationship.pathwayId}`;
      if (!nodes.has(junctionId) || !nodes.has(pathwayId)) return;
      const sourceId = relationship.endpoint === "end" ? pathwayId : junctionId;
      const targetId = relationship.endpoint === "end" ? junctionId : pathwayId;
      const edge = { junction, relationship, sourceId, targetId };
      edges.push(edge);
      nodes.get(sourceId).outgoing.push(targetId);
      nodes.get(targetId).incoming.push(sourceId);
      nodes.get(junctionId).neighbors.push(pathwayId);
      nodes.get(pathwayId).neighbors.push(junctionId);
    });
  });
  const indegrees = new Map([...nodes].map(([id, node]) => [id, node.incoming.length]));
  const ready = [...nodes.values()].filter((node) => !indegrees.get(node.id))
    .sort((left, right) => left.index - right.index);
  const depths = new Map([...nodes.keys()].map((id) => [id, 0]));
  while (ready.length) {
    const node = ready.shift();
    node.outgoing.forEach((targetId) => {
      depths.set(targetId, Math.max(depths.get(targetId), depths.get(node.id) + 1));
      indegrees.set(targetId, indegrees.get(targetId) - 1);
      if (!indegrees.get(targetId)) {
        ready.push(nodes.get(targetId));
        ready.sort((left, right) => left.index - right.index);
      }
    });
  }
  const visited = new Set();
  const components = [];
  [...nodes.values()].sort((left, right) => left.index - right.index).forEach((root) => {
    if (visited.has(root.id)) return;
    const queue = [root];
    const componentNodes = [];
    visited.add(root.id);
    while (queue.length) {
      const node = queue.shift();
      componentNodes.push({ ...node, depth: depths.get(node.id) || 0 });
      node.neighbors.forEach((neighborId) => {
        if (!visited.has(neighborId)) {
          visited.add(neighborId);
          queue.push(nodes.get(neighborId));
        }
      });
    }
    componentNodes.sort((left, right) => left.depth - right.depth || left.index - right.index);
    const nodeIds = new Set(componentNodes.map((node) => node.id));
    components.push({
      nodes: componentNodes,
      edges: edges.filter((edge) => nodeIds.has(edge.sourceId) && nodeIds.has(edge.targetId)),
    });
  });
  return components;
}
