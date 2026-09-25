/** Select attachment hierarchies and edit their persistent terminal associations. */

let cancelActiveConnectionAssociationSelection = null;
let nextConnectionAssociationGroupId = 0;

/** Return the rendered identity of an association anchor. */
function connectionAssociationNodeId(anchor) {
  if (anchor.nodeKind) return `${anchor.nodeKind}:${anchor.nodeId}`;
  return anchor.attachmentId
    ? `attachment:${anchor.connectionId}:${anchor.attachmentId}`
    : `connection:${anchor.connectionId}`;
}

/** Resolve terminals beneath a node, orienting route branches away from its peer. */
function connectionAssociationCandidates(harness, anchor, peer = null) {
  if (anchor.nodeKind === "pathway" || anchor.nodeKind === "junction") {
    const dialog = document.body.querySelector(".cable-group-details-popup");
    const graphic = dialog?.querySelector(".cable-group-details-graphic");
    const nodes = new Map([...graphic?.querySelectorAll(".cable-group-details-node") || []]
      .map((node) => [node.dataset.nodeId, node]));
    const startId = `${anchor.nodeKind}:${anchor.nodeId}`;
    if (!nodes.has(startId)) return [];
    const neighbors = new Map([...nodes.keys()].map((id) => [id, new Set()]));
    graphic.querySelectorAll(".cable-group-route-link").forEach((edge) => {
      const left = edge.dataset.startNodeId;
      const right = edge.dataset.endNodeId;
      neighbors.get(left)?.add(right);
      neighbors.get(right)?.add(left);
    });
    const depths = new Map([...nodes].map(([id, node]) => [id, Number(node.dataset.depth)]));
    if (peer) {
      const peerId = connectionAssociationNodeId(peer);
      if (!nodes.has(peerId)) return [];
      depths.clear();
      depths.set(peerId, 0);
      const queue = [peerId];
      for (let index = 0; index < queue.length; index += 1) {
        const current = queue[index];
        neighbors.get(current).forEach((neighbor) => {
          if (depths.has(neighbor)) return;
          depths.set(neighbor, depths.get(current) + 1);
          queue.push(neighbor);
        });
      }
      if (!depths.has(startId)) return [];
    }
    const reachable = new Set([startId]);
    const pending = [startId];
    while (pending.length) {
      const currentId = pending.pop();
      const currentDepth = depths.get(currentId);
      (neighbors.get(currentId) || []).forEach((neighbor) => {
        if (reachable.has(neighbor)) return;
        if (depths.get(neighbor) <= currentDepth) return;
        reachable.add(neighbor);
        pending.push(neighbor);
      });
    }
    const candidates = [];
    reachable.forEach((id) => {
      const node = nodes.get(id);
      if (node?.classList.contains("connection")) {
        candidates.push(...connectionAssociationCandidates(harness, {
          connectionId: node.dataset.connectionId,
          attachmentId: null,
        }));
      }
    });
    return candidates;
  }
  const connection = harness.connections.find(
    (candidate) => candidate.connectionId === anchor.connectionId,
  );
  if (!connection) return [];
  const attachments = connection.attachments || (connection.attachment ? [connection.attachment] : []);
  const byId = new Map(attachments.map((attachment) => [attachment.attachmentId, attachment]));
  const children = new Map();
  attachments.forEach((attachment) => {
    const key = attachment.parentAttachmentId || "";
    if (!children.has(key)) children.set(key, []);
    children.get(key).push(attachment);
  });
  const roots = anchor.attachmentId
    ? (byId.has(anchor.attachmentId) ? [byId.get(anchor.attachmentId)] : [])
    : (children.get("") || []);
  const result = [];
  const pending = [...roots].reverse();
  while (pending.length) {
    const attachment = pending.pop();
    const descendants = children.get(attachment.attachmentId) || [];
    if (descendants.length) {
      pending.push(...[...descendants].reverse());
    } else {
      result.push({
        attachmentId: attachment.attachmentId,
        connectionId: connection.connectionId,
        connectionName: connection.name || "Cable end",
        label: attachment.name || "Connection",
      });
    }
  }
  return result;
}

/** Divide an attachment/owner pair across its subtree and other cable-group ends. */
function connectionAssociationPair(harness, source, target) {
  let sourceCandidates = connectionAssociationCandidates(harness, source, target);
  let targetCandidates = connectionAssociationCandidates(harness, target, source);
  const sourceIds = new Set(sourceCandidates.map((item) => item.attachmentId));
  const overlaps = targetCandidates.some((item) => sourceIds.has(item.attachmentId));
  let sourceAnchor = source;
  let targetAnchor = target;
  let sourceLabel = null;
  let targetLabel = null;
  if (overlaps) {
    const attachment = source.attachmentId ? source : target.attachmentId ? target : null;
    const owner = source.attachmentId ? target : source;
    const group = (harness.cableGroups || []).find((candidate) => (
      candidate.cableGroupId === openCableGroupDetailsState?.cableGroupId
    ));
    if (!attachment || owner.nodeKind || owner.attachmentId ||
        attachment.connectionId !== owner.connectionId ||
        !group?.connectionIds.includes(owner.connectionId)) return null;
    const otherCandidates = group.connectionIds
      .filter((connectionId) => connectionId !== owner.connectionId)
      .flatMap((connectionId) => connectionAssociationCandidates(harness, { connectionId }));
    const otherAnchor = {
      nodeKind: "cableGroupRemainder",
      nodeId: group.cableGroupId,
      connectionId: owner.connectionId,
      candidateAttachmentIds: otherCandidates.map((item) => item.attachmentId),
    };
    if (source === owner) {
      sourceCandidates = otherCandidates;
      sourceAnchor = otherAnchor;
      sourceLabel = `Other ${group.name} connections`;
    } else {
      targetCandidates = otherCandidates;
      targetAnchor = otherAnchor;
      targetLabel = `Other ${group.name} connections`;
    }
  }
  if (!sourceCandidates.length || !targetCandidates.length) return null;
  if (targetCandidates.some((item) => (
    sourceCandidates.some((sourceItem) => sourceItem.attachmentId === item.attachmentId)
  ))) return null;
  if (sourceAnchor.nodeKind && sourceAnchor.nodeKind !== "cableGroupRemainder") {
    sourceAnchor = {
      ...sourceAnchor, candidateAttachmentIds: sourceCandidates.map((item) => item.attachmentId),
    };
  }
  if (targetAnchor.nodeKind && targetAnchor.nodeKind !== "cableGroupRemainder") {
    targetAnchor = {
      ...targetAnchor, candidateAttachmentIds: targetCandidates.map((item) => item.attachmentId),
    };
  }
  return { sourceAnchor, targetAnchor, sourceCandidates, targetCandidates, sourceLabel, targetLabel };
}

/** Clear node-selection styling and document-level listeners. */
function clearConnectionAssociationSelection(container) {
  container.classList.remove("connection-association-selecting");
  container.querySelectorAll(
    ".connection-association-source, .connection-association-target, .connection-association-unavailable",
  ).forEach((node) => node.classList.remove(
    "connection-association-source",
    "connection-association-target",
    "connection-association-unavailable",
  ));
  document.removeEventListener("click", handleConnectionAssociationClick, true);
  document.removeEventListener("keydown", handleConnectionAssociationKeyDown, true);
}

let connectionAssociationSelection = null;

/** Select a highlighted second hierarchy or cancel on another click. */
function handleConnectionAssociationClick(event) {
  const selection = connectionAssociationSelection;
  if (!selection) return;
  const node = event.target.closest?.(".cable-group-details-node");
  const anchor = node ? connectionAssociationAnchorFromElement(node) : null;
  if (node && selection.eligible.has(node)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    const pair = connectionAssociationPair(selection.harness, selection.source, anchor);
    if (!pair) return;
    clearConnectionAssociationSelection(selection.container);
    connectionAssociationSelection = null;
    cancelActiveConnectionAssociationSelection = null;
    openConnectionAssociationPanel(
      selection.harness,
      pair.sourceAnchor,
      pair.targetAnchor,
      pair.sourceCandidates,
      pair.targetCandidates,
      pair.sourceLabel || selection.sourceLabel,
      pair.targetLabel || node.getAttribute("aria-label") || "Selected connection",
    );
    return;
  }
  if (selection.container.contains(event.target)) {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  }
  selection.cancel();
}

/** Allow Escape to cancel and Enter/Space to choose a highlighted hierarchy. */
function handleConnectionAssociationKeyDown(event) {
  if (!connectionAssociationSelection) return;
  if (event.key === "Escape") {
    event.preventDefault();
    event.stopPropagation();
    connectionAssociationSelection.cancel();
    return;
  }
  if (!(["Enter", " "].includes(event.key))) return;
  const node = event.target.closest?.(".cable-group-details-node");
  if (!node || !connectionAssociationSelection.eligible.has(node)) return;
  event.preventDefault();
  node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
}

/** Recover a selection anchor from a rendered diagram node. */
function connectionAssociationAnchorFromElement(node) {
  if (node.classList.contains("pathway") || node.classList.contains("junction")) {
    const [nodeKind, nodeId] = node.dataset.nodeId.split(":");
    return { nodeKind, nodeId };
  }
  const connectionId = node.dataset.connectionId;
  return node.classList.contains("attachment")
    ? { connectionId, attachmentId: node.dataset.attachmentId }
    : { connectionId, attachmentId: null };
}

/** Begin choosing a second cable-end node for a terminal association panel. */
function beginCableGroupAttachmentAssociation(harness, source) {
  if (cancelActiveConnectionAssociationSelection) {
    cancelActiveConnectionAssociationSelection();
  }
  const dialog = document.body.querySelector(".cable-group-details-popup");
  const container = dialog?.querySelector(".cable-group-details-graphic");
  if (!container) return;
  const eligible = new Set();
  const nodeElements = container.querySelectorAll(".cable-group-details-node");
  nodeElements.forEach((node) => {
    const anchor = connectionAssociationAnchorFromElement(node);
    const pair = connectionAssociationPair(harness, source, anchor);
    node.classList.remove(
      "connection-association-source",
      "connection-association-target",
      "connection-association-unavailable",
    );
    const isSource = node.dataset.nodeId === connectionAssociationNodeId(source);
    if (isSource) {
      node.classList.add("connection-association-source");
    } else if (pair) {
      eligible.add(node);
      node.classList.add("connection-association-target");
    } else {
      node.classList.add("connection-association-unavailable");
    }
  });
  container.classList.add("connection-association-selecting");
  let active = true;
  const cancel = () => {
    if (!active) return;
    active = false;
    clearConnectionAssociationSelection(container);
    if (connectionAssociationSelection?.cancel === cancel) {
      connectionAssociationSelection = null;
    }
    if (cancelActiveConnectionAssociationSelection === cancel) {
      cancelActiveConnectionAssociationSelection = null;
    }
  };
  connectionAssociationSelection = {
    harness,
    source,
    sourceLabel: [...nodeElements]
      .find((node) => node.classList.contains("connection-association-source"))
      ?.getAttribute("aria-label") || "Selected connection",
    container,
    eligible,
    cancel,
  };
  cancelActiveConnectionAssociationSelection = cancel;
  appendNotice("Associate: choose a highlighted connection node, or press Escape to cancel.");
  document.addEventListener("click", handleConnectionAssociationClick, true);
  document.addEventListener("keydown", handleConnectionAssociationKeyDown, true);
}

