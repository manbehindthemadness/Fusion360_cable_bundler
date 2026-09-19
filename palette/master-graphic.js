const RELATIONSHIP_DIAGRAM_CONTRACT_VERSION = "10";
const RELATIONSHIP_DIAGRAM_LAYOUT = "layered-cardinal-topology";

/** Assemble the filterable master relationship diagram from focused components. */
function renderRelationshipMap(harness) {
  const diagramViewKey = harnessKey(harness);
  const savedDiagramView = relationshipDiagramViews.get(diagramViewKey);
  let restoreInitialView = savedDiagramView !== undefined;
  const connections = new Map(
    harness.connections.map((connection) => [connection.connectionId, connection]),
  );
  const container = document.createElement("div");
  const toolbar = document.createElement("div");
  const filter = document.createElement("input");
  const summary = document.createElement("span");
  const settings = document.createElement("label");
  const collapseInput = document.createElement("input");
  const workspace = createBlockDiagramWorkspace(
    "Zoomable master relationship diagram",
    {
      initialView: savedDiagramView,
      onViewChange: (view) => relationshipDiagramViews.set(diagramViewKey, {
        ...relationshipDiagramViews.get(diagramViewKey),
        ...view,
      }),
      onRedraw: () => redraw(),
    },
  );
  const focusController = createRelationshipFocusController(container);
  const wireCreationController = createWireCreationController(harness, container);
  const showContextMenu = addRelationshipMapContextMenu(workspace, harness);
  container.className = "section-content relationship-map";
  container.dataset.diagramContractVersion = RELATIONSHIP_DIAGRAM_CONTRACT_VERSION;
  container.dataset.diagramLayout = RELATIONSHIP_DIAGRAM_LAYOUT;
  container.dataset.hasSavedDiagramView = `${savedDiagramView !== undefined}`;
  container.fitDiagram = workspace.fit;
  toolbar.className = "relationship-map-toolbar";
  filter.className = "filter";
  filter.type = "search";
  filter.placeholder = "Find a wire group, connection, or pathway…";
  filter.setAttribute("aria-label", "Filter master relationship graphic");
  filter.autocomplete = "off";
  filter.value = relationshipFilters.get(harnessKey(harness)) || "";
  summary.className = "relationship-map-summary";
  summary.textContent = `${(harness.wireGroups || []).length} wire groups`;
  toolbar.append(filter, summary);
  settings.className = "relationship-map-settings";
  settings.textContent = "Collapse end lists above";
  collapseInput.type = "number";
  collapseInput.min = `${MIN_RELATIONSHIP_COLLAPSE_LIMIT}`;
  collapseInput.max = `${MAX_RELATIONSHIP_COLLAPSE_LIMIT}`;
  collapseInput.step = "1";
  collapseInput.value = `${relationshipCollapseLimit(harness)}`;
  collapseInput.setAttribute("aria-label", "Connections before end lists collapse");
  settings.append(collapseInput, "connections");

  let renderedStack = null;
  let renderedComponents = [];
  const redraw = () => {
    if (!renderedStack) {
      workspace.fit();
      return;
    }
    const selectedLayout = layoutRelationshipGraph(renderedStack, renderedComponents, harness, {
      width: workspace.viewport.clientWidth,
      height: workspace.viewport.clientHeight,
      layoutKey: relationshipDiagramViews.get(diagramViewKey)?.layoutKey,
      advanceLayout: true,
      reuseLayouts: true,
    });
    if (!selectedLayout) return;
    relationshipDiagramViews.set(diagramViewKey, {
      ...relationshipDiagramViews.get(diagramViewKey),
      ...selectedLayout,
    });
    workspace.fit();
  };

  const draw = () => {
    wireCreationController.cancel();
    const query = filter.value.trim().toLocaleLowerCase();
    const collapseLimit = clampRelationshipCollapseLimit(collapseInput.value);
    relationshipFilters.set(harnessKey(harness), query);
    workspace.stage.replaceChildren();
    const stack = document.createElement("div");
    renderedStack = null;
    renderedComponents = [];
    stack.className = "relationship-pathway-stack";
    stack.dataset.diagramContractVersion = RELATIONSHIP_DIAGRAM_CONTRACT_VERSION;
    stack.dataset.diagramLayout = RELATIONSHIP_DIAGRAM_LAYOUT;
    relationshipTopology(harness).forEach((component) => {
      const searchable = component.nodes.map((node) => {
        if (node.kind === "junction") return node.item.name || "";
        const groups = relationshipPathwayGroups(harness, node.item.pathwayId);
        const endpointSearch = ["start", "end"].flatMap((endpoint) => (
          relationshipEndGroups(harness, node.item.pathwayId, endpoint, connections)
            .map((group) => group.searchable)
        )).join(" ");
        const groupSearch = groups.reduce(
          (search, group) => `${search} ${wireGroupLabel(harness, group)}`,
          "",
        );
        return `${node.item.name} ${node.item.startName || ""} ${node.item.endName || ""} ${groupSearch} ${endpointSearch}`;
      }).join(" ").toLocaleLowerCase();
      if (query && !searchable.includes(query)) return;
      component.nodes.forEach((node) => {
        const wrapper = document.createElement("div");
        const memberGroups = node.kind === "junction"
          ? relationshipJunctionGroups(harness, node.item)
          : relationshipPathwayGroups(harness, node.item.pathwayId);
        const focusNodeIds = [node.id, ...node.neighbors];
        wrapper.className = `relationship-topology-node relationship-topology-${node.kind}`;
        wrapper.dataset.nodeId = node.id;
        wrapper.dataset.wireGroupIds = relationshipGroupIds(memberGroups);
        if (node.kind === "junction") {
          wrapper.dataset.junctionId = node.item.junctionId;
          wrapper.append(renderRelationshipJunctionHub(
            harness, node.item, showContextMenu, focusController, focusNodeIds,
          ));
        } else {
          wrapper.dataset.pathwayId = node.item.pathwayId;
          wrapper.append(renderRelationshipPathwayNode(
            harness,
            node.item,
            connections,
            query,
            collapseLimit,
            showContextMenu,
            focusController,
            wireCreationController,
            focusNodeIds,
          ));
        }
        node.element = wrapper;
        stack.append(wrapper);
      });
      renderedComponents.push(component);
    });
    if (!renderedComponents.length) {
      const message = emptyMessage(
        harness.pathways.length || (harness.junctions || []).length
          ? "No relationships match this filter."
          : "No pathways or junctions to display yet.",
      );
      message.className = "empty relationship-map-empty";
      workspace.stage.append(message);
      window.requestAnimationFrame(() => {
        if (restoreInitialView) restoreInitialView = false;
        else workspace.fit();
      });
      return;
    }
    workspace.stage.append(stack);
    renderedStack = stack;
    window.requestAnimationFrame(() => {
      const selectedLayout = layoutRelationshipGraph(stack, renderedComponents, harness, {
        width: workspace.viewport.clientWidth,
        height: workspace.viewport.clientHeight,
        layoutKey: relationshipDiagramViews.get(diagramViewKey)?.layoutKey,
      });
      if (!selectedLayout) return;
      relationshipDiagramViews.set(diagramViewKey, {
        ...relationshipDiagramViews.get(diagramViewKey),
        ...selectedLayout,
      });
      if (restoreInitialView) restoreInitialView = false;
      else workspace.fit();
    });
  };
  filter.addEventListener("input", draw);
  collapseInput.addEventListener("change", () => {
    const limit = clampRelationshipCollapseLimit(collapseInput.value);
    collapseInput.value = `${limit}`;
    writeSession(relationshipCollapseStorageKey(harness), `${limit}`);
    [...relationshipEndListOverrides.keys()]
      .filter((key) => key.startsWith(`${harnessKey(harness)}:`))
      .forEach((key) => relationshipEndListOverrides.delete(key));
    draw();
  });
  container.append(toolbar, settings, workspace.root);
  draw();
  return container;
}
