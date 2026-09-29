// Adapted from tmdt-buw/semantic-data-catalog (F. Hoelken et al.), Apache-2.0.
import { mountGraph } from "./graph.js";
const state = {
  catalogs: [],
  datasets: [],
  selectedId: "",
  selectedGraph: "",
  filter: "",
  details: new Map(),
  open: new Set(),
  expandedDefaults: false,
};
const el = Object.fromEntries(
  [
    "searchInput",
    "refreshButton",
    "collapseButton",
    "catalogTree",
    "catalogCount",
    "emptyState",
    "loadError",
    "detailEmpty",
    "detailContent",
    "detailTitle",
    "detailId",
    "detailProvider",
    "detailTypes",
    "detailCatalog",
    "providerDid",
    "dspEndpoint",
    "assetId",
    "sourceLinks",
    "rdfGraph",
    "nodeInspector",
    "zoomIn",
    "zoomOut",
    "fitGraph",
    "showTypes",
    "graphCount",
    "expandGraph",
    "graphWorkspace",
    "graphDialog",
    "graphDialogContent",
    "closeGraph",
  ].map((id) => [id, document.getElementById(id)]),
);
export const shortIri = (value) =>
  (value || "").split(/[/#]/).filter(Boolean).pop() || value || "Untitled";
const make = (tag, className, content) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (content !== undefined) node.textContent = content;
  return node;
};
const key = (id, graph) => JSON.stringify([graph, id]);
function safeLink(raw, label) {
  try {
    const url = new URL(raw);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      return make("span", "", label || raw);
    const link = make("a", "", label || raw);
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  } catch {
    return make("span", "", label || raw);
  }
}
function matches(dataset) {
  const query = state.filter.trim().toLowerCase();
  return (
    !query ||
    [
      dataset.title,
      dataset.provider,
      dataset.dataset_id,
      dataset.metadata?.catalog_id,
      dataset.metadata?.provider_did,
      dataset.metadata?.dsp_endpoint,
      dataset.metadata?.asset_id,
      ...(dataset.metadata?.search_terms || []),
    ].some((v) =>
      String(v || "")
        .toLowerCase()
        .includes(query),
    )
  );
}
function disclosure(label, id, className, defaultOpen = false) {
  const item = make("details", className);
  item.open = state.open.has(id) || defaultOpen;
  if (defaultOpen) state.open.add(id);
  item.append(label);
  item.addEventListener("toggle", () =>
    item.open ? state.open.add(id) : state.open.delete(id),
  );
  return item;
}
function renderTree() {
  el.catalogTree.replaceChildren();
  let total = 0;
  for (const catalog of state.catalogs) {
    const datasets = state.datasets.filter(
      (d) =>
        d.metadata?.graph === catalog.graph &&
        d.metadata?.catalog_id === catalog.catalog_id,
    );
    const visible = datasets.filter(matches);
    total += visible.length;
    const query = state.filter.trim().toLowerCase();
    const catalogMatch = [
      catalog.title,
      catalog.catalog_id,
      catalog.provider,
      catalog.metadata?.provider_did,
      catalog.metadata?.dsp_endpoint,
    ].some((v) =>
      String(v || "")
        .toLowerCase()
        .includes(query),
    );
    if (query && !visible.length && !catalogMatch) continue;
    const summary = make("summary", "catalog-summary");
    const title = make("div", "tree-title");
    title.append(
      make("strong", "", catalog.title || shortIri(catalog.catalog_id)),
      make(
        "span",
        "tree-subtitle",
        catalog.metadata?.provider_did || catalog.provider,
      ),
    );
    summary.append(
      title,
      make("span", "count-badge", `${visible.length} / ${datasets.length}`),
    );
    const item = disclosure(
      summary,
      key(catalog.catalog_id, catalog.graph),
      "catalog-branch",
      Boolean(query),
    );
    const info = make("dl", "catalog-connector");
    for (const [label, value] of [
      ["Provider-DID", catalog.metadata?.provider_did],
      ["DSP-Endpoint", catalog.metadata?.dsp_endpoint],
    ]) {
      const row = make("div");
      row.append(
        make("dt", "", label),
        make("dd", "mono", value || "Not supplied"),
      );
      info.append(row);
    }
    item.append(info);
    const hierarchy = catalog.metadata?.hierarchy || [];
    const byId = new Map(datasets.map((d) => [d.dataset_id, d]));
    const visibleIds = new Set(visible.map((d) => d.dataset_id));
    const children = (parent) =>
      hierarchy.filter((n) => n.parent_id === parent);
    function hasMatch(node, seen = new Set()) {
      if (seen.has(node.id)) return false;
      const next = new Set(seen).add(node.id);
      return (
        visibleIds.has(node.id) ||
        children(node.id).some((n) => hasMatch(n, next))
      );
    }
    const rendered = new Set();
    function renderNodes(parent, container, ancestors = new Set()) {
      for (const node of children(parent)) {
        if (ancestors.has(node.id) || (query && !hasMatch(node))) continue;
        rendered.add(node.id);
        if (node.kind === "series") {
          const label = make("summary", "series-summary");
          label.append(
            make("span", "tree-kind", "GROUP"),
            make("span", "", node.title || shortIri(node.id)),
          );
          const branch = disclosure(
            label,
            key(node.id, catalog.graph),
            "series-branch",
            Boolean(query),
          );
          renderNodes(node.id, branch, new Set(ancestors).add(node.id));
          container.append(branch);
        } else if (byId.has(node.id))
          container.append(datasetBranch(byId.get(node.id)));
      }
    }
    const list = make("div", "tree-children");
    renderNodes(catalog.catalog_id, list, new Set([catalog.catalog_id]));
    // Older discovery responses, or disconnected memberships, remain browsable.
    for (const dataset of visible)
      if (!rendered.has(dataset.dataset_id))
        list.append(datasetBranch(dataset));
    if (!datasets.length)
      list.append(make("p", "empty", "No datasets in this catalog."));
    item.append(list);
    el.catalogTree.append(item);
  }
  el.emptyState.hidden =
    total > 0 || (!state.filter && state.catalogs.length > 0);
  if (!state.catalogs.length) {
    el.emptyState.hidden = false;
    el.emptyState.textContent = "No catalogs published yet.";
  } else el.emptyState.textContent = "No datasets match this search.";
}
function datasetBranch(dataset) {
  const id = key(dataset.dataset_id, dataset.metadata?.graph);
  const summary = make("summary", "dataset-summary");
  const button = make("button", "dataset-select");
  button.type = "button";
  const selected =
    state.selectedId === dataset.dataset_id &&
    state.selectedGraph === dataset.metadata?.graph;
  button.setAttribute("aria-pressed", String(selected));
  button.append(
    make("span", "tree-kind", "DATASET"),
    make("strong", "", dataset.title || shortIri(dataset.dataset_id)),
    make(
      "span",
      "tree-subtitle",
      dataset.metadata?.asset_id || shortIri(dataset.dataset_id),
    ),
  );
  button.addEventListener("click", (event) => {
    event.preventDefault();
    selectDataset(dataset.dataset_id, dataset.metadata.graph).catch(showError);
  });
  summary.append(button);
  const branch = disclosure(summary, id, "dataset-branch");
  const detail = state.details.get(id);
  if (detail) {
    const children = (detail.triples || []).filter(
      (t) =>
        t.subject === dataset.dataset_id &&
        [
          "http://www.w3.org/ns/dcat#distribution",
          "https://w3id.org/construct-dcat#hasAASSubmodel",
        ].includes(t.predicate) &&
        t.object_type !== "literal",
    );
    for (const triple of children) {
      const child = make("div", "resource-child");
      child.append(
        make(
          "span",
          "tree-kind",
          triple.predicate.endsWith("distribution")
            ? "DISTRIBUTION"
            : "SUBMODEL",
        ),
        make("span", "", shortIri(triple.object)),
      );
      const urls = detail.triples.filter(
        (t) =>
          t.subject === triple.object &&
          [
            "http://www.w3.org/ns/dcat#accessURL",
            "http://www.w3.org/ns/dcat#downloadURL",
          ].includes(t.predicate),
      );
      for (const url of urls)
        child.append(safeLink(url.object, "Open source ↗"));
      branch.append(child);
    }
    if (!children.length)
      branch.append(
        make("p", "empty", "No distribution or submodel link supplied."),
      );
  } else branch.append(make("p", "empty", "Expand to load resources."));
  branch.addEventListener("toggle", () => {
    if (branch.open && !state.details.has(id))
      getDetail(dataset.dataset_id, dataset.metadata.graph)
        .then(renderTree)
        .catch(showError);
  });
  return branch;
}
const pending = new Map();
async function getDetail(id, graph) {
  const cacheKey = key(id, graph);
  if (state.details.has(cacheKey)) return state.details.get(cacheKey);
  if (pending.has(cacheKey)) return pending.get(cacheKey);
  const request = (async () => {
    const response = await fetch(
      `/datasets/detail?dataset_id=${encodeURIComponent(id)}&graph=${encodeURIComponent(graph)}`,
    );
    if (!response.ok)
      throw new Error("Dataset unavailable. Refresh the catalog.");
    const detail = await response.json();
    state.details.set(cacheKey, detail);
    return detail;
  })();
  pending.set(cacheKey, request);
  try {
    return await request;
  } finally {
    pending.delete(cacheKey);
  }
}
async function selectDataset(id, graph) {
  state.selectedId = id;
  state.selectedGraph = graph;
  state.open.add(key(id, graph));
  const catalog = state.catalogs.find((c) => c.graph === graph);
  if (catalog) {
    state.open.add(key(catalog.catalog_id, graph));
    const visit = (child, seen = new Set()) => {
      if (seen.has(child)) return;
      seen.add(child);
      for (const node of catalog.metadata?.hierarchy || [])
        if (node.id === child) {
          state.open.add(key(node.parent_id, graph));
          visit(node.parent_id, seen);
        }
    };
    visit(id);
  }
  el.detailContent.hidden = true;
  el.detailEmpty.hidden = false;
  el.detailEmpty.textContent = "Loading dataset…";
  renderTree();
  const detail = await getDetail(id, graph);
  if (state.selectedId !== id || state.selectedGraph !== graph) return;
  el.detailEmpty.hidden = true;
  el.detailContent.hidden = false;
  el.loadError.hidden = true;
  for (const [target, value] of [
    ["detailTitle", detail.title || shortIri(id)],
    ["detailId", id],
    ["detailCatalog", detail.metadata?.catalog_id],
    ["detailProvider", detail.provider],
    ["detailTypes", (detail.types || []).map(shortIri).join(", ")],
    ["providerDid", detail.metadata?.provider_did],
    ["assetId", detail.metadata?.asset_id],
  ])
    el[target].textContent = value || "Not supplied";
  el.dspEndpoint.replaceChildren(
    safeLink(
      detail.metadata?.dsp_endpoint || "",
      detail.metadata?.dsp_endpoint || "Not supplied",
    ),
  );
  el.sourceLinks.replaceChildren();
  for (const url of new Set(
    detail.triples
      .filter((t) =>
        [
          "http://www.w3.org/ns/dcat#accessURL",
          "http://www.w3.org/ns/dcat#downloadURL",
        ].includes(t.predicate),
      )
      .map((t) => t.object),
  )) {
    const link = safeLink(url, "Open source data ↗");
    if (link.tagName === "A") {
      const li = make("li");
      li.append(link);
      el.sourceLinks.append(li);
    }
  }
  if (!el.sourceLinks.children.length)
    el.sourceLinks.append(make("li", "muted", "No web access link supplied."));
  mountGraph(el, detail, state.datasets, (dataset) => {
    if (!matches(dataset)) {
      state.filter = "";
      el.searchInput.value = "";
    }
    selectDataset(dataset.dataset_id, dataset.metadata.graph).catch(showError);
  });
  renderTree();
}
function showError(error) {
  el.loadError.hidden = false;
  el.loadError.textContent = error.message;
}
async function refresh() {
  el.refreshButton.disabled = true;
  try {
    const responses = await Promise.all([
      fetch("/catalogs"),
      fetch("/datasets"),
    ]);
    if (responses.some((r) => !r.ok))
      throw new Error("Cannot load the catalog. Try Refresh.");
    [state.catalogs, state.datasets] = await Promise.all(
      responses.map((r) => r.json()),
    );
    state.details.clear();
    if (!state.expandedDefaults) {
      state.catalogs.forEach((c) => state.open.add(key(c.catalog_id, c.graph)));
      state.expandedDefaults = true;
    }
    el.catalogCount.textContent = `${state.catalogs.length} publishers · ${state.datasets.length} datasets`;
    el.loadError.hidden = true;
    renderTree();
    if (
      state.datasets.some(
        (d) =>
          d.dataset_id === state.selectedId &&
          d.metadata.graph === state.selectedGraph,
      )
    )
      await selectDataset(state.selectedId, state.selectedGraph);
    else {
      state.selectedId = "";
      state.selectedGraph = "";
      el.detailContent.hidden = true;
      el.detailEmpty.hidden = false;
      el.detailEmpty.textContent = "Select a dataset to inspect its metadata.";
    }
  } finally {
    el.refreshButton.disabled = false;
  }
}
el.expandGraph.onclick = () => {
  el.graphDialogContent.append(el.graphWorkspace);
  el.graphDialog.showModal();
};
el.closeGraph.onclick = () => el.graphDialog.close();
el.graphDialog.addEventListener("close", () => {
  el.detailContent.append(el.graphWorkspace);
  el.expandGraph.focus();
});
el.searchInput.addEventListener("input", (event) => {
  state.filter = event.target.value;
  renderTree();
});
el.refreshButton.addEventListener("click", () => refresh().catch(showError));
el.collapseButton.addEventListener("click", () => {
  state.open.clear();
  el.catalogTree.querySelectorAll("details").forEach((d) => {
    d.open = false;
  });
});
refresh().catch(showError);
