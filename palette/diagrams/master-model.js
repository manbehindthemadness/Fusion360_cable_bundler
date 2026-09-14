/** Derive stable relationship membership and topology for the master diagram. */

function relationshipWireIds(wires) {
  return wires.map((wire) => wire.wireId).join(" ");
}

function relationshipElementWireIds(element) {
  const value = element.dataset?.wireIds || element.dataset?.wireId || "";
  return new Set(value.split(" ").filter(Boolean));
}

function relationshipSetsIntersect(left, right) {
  return [...left].some((value) => right.has(value));
}

/** Apply transient focus to every master-diagram element sharing route membership. */
function createRelationshipFocusController(container) {
  const itemClasses = [
    "relationship-topology-node",
    "relationship-topology-edge",
    "relationship-topology-port",
    "relationship-end-entry",
    "wire-trace",
    "stripe-trace",
    "aggregate-trace",
  ];
  let pointerFocus = null;
  let keyboardFocus = null;
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
    const wireIds = new Set(focus.wireIds);
    const nodeIds = new Set(focus.nodeIds);
    items().forEach((item) => {
      const itemWireIds = relationshipElementWireIds(item);
      const itemNodeIds = new Set([
        item.dataset?.nodeId,
        item.dataset?.sourceId,
        item.dataset?.targetId,
      ].filter(Boolean));
      const matches = wireIds.size
        ? relationshipSetsIntersect(wireIds, itemWireIds)
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
      wireIds: descriptor.wires.map((wire) => wire.wireId),
      nodeIds: descriptor.nodeIds || [],
    };
    source.addEventListener("mouseenter", () => {
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
  return { bind };
}

function relationshipEndGroups(harness, pathwayId, endpoint, connections) {
  const connectionField = endpoint === "start" ? "startConnectionId" : "endConnectionId";
  const endpointNameField = endpoint === "start" ? "startEndName" : "endEndName";
  const groups = new Map();
  harness.wires
    .filter((wire) => {
      const pathwayIndex = endpoint === "start" ? 0 : wire.orderedPathwayIds.length - 1;
      return wire.orderedPathwayIds[pathwayIndex] === pathwayId;
    })
    .forEach((wire) => {
      const connectionId = wire[connectionField] || "";
      const groupKey = connectionId || `missing:${wire.wireId}`;
      if (!groups.has(groupKey)) {
        groups.set(groupKey, {
          connectionId,
          connectionName: connections.get(connectionId)?.name || "",
          endpointNames: new Set(),
          wires: [],
          standalone: false,
        });
      }
      const group = groups.get(groupKey);
      if (wire[endpointNameField]) group.endpointNames.add(wire[endpointNameField]);
      group.wires.push(wire);
    });
  (harness.standaloneEnds || [])
    .filter((end) => end.pathwayId === pathwayId && end.endpoint === endpoint)
    .forEach((end) => {
      const connection = connections.get(end.connectionId);
      groups.set(end.connectionId, {
        connectionId: end.connectionId,
        connectionName: connection?.name || "",
        endpointNames: new Set(),
        wires: [],
        standalone: true,
      });
    });
  return [...groups.values()].map((group) => {
    const endpointNames = [...group.endpointNames];
    const label = endpointNames.length === 1
      ? endpointNames[0]
      : group.connectionName || `Missing End ${endpoint === "start" ? "A" : "B"}`;
    const wireSearch = group.wires.map((wire) => (
      `${wireLabel(wire)} ${wire.wireNumber} ${wire.materials?.insulationMaterial || ""} ${wire.materials?.mainColor?.name || ""}`
    )).join(" ");
    return {
      ...group,
      label,
      searchable: `${label} ${group.connectionName} ${endpointNames.join(" ")} ${wireSearch}`
        .toLocaleLowerCase(),
    };
  });
}

function relationshipPathwayWires(harness, pathwayId) {
  return harness.wires.filter((wire) => wire.orderedPathwayIds.includes(pathwayId));
}

/** Return the selected pathway and its exclusively downstream pathway branch. */
function relationshipPathwayDeletionIds(harness, pathwayId) {
  const deletedPathwayIds = new Set([pathwayId]);
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

function relationshipJunctionWires(harness, junction) {
  const relationships = junction.pathwayRelationships || [];
  const preceding = new Set(
    relationships.filter((item) => item.endpoint === "end").map((item) => item.pathwayId),
  );
  const following = new Set(
    relationships.filter((item) => item.endpoint === "start").map((item) => item.pathwayId),
  );
  return harness.wires.filter((wire) => wire.orderedPathwayIds.some((pathwayId, index) => (
    preceding.has(pathwayId) && following.has(wire.orderedPathwayIds[index + 1])
  )));
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
