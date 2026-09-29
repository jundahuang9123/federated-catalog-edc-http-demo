const RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type";
const short = (value) => value.split(/[/#]/).filter(Boolean).pop() || value;
const identity = (value, type) =>
  `${type === "bnode" ? "bnode" : "uri"}:${value}`;
export function graphModel(triples, datasetId, showTypes = false) {
  const nodes = new Map();
  const edges = [];
  const add = (value, type = "uri") => {
    const id = identity(value, type);
    if (!nodes.has(id)) nodes.set(id, { id, value, type, label: short(value) });
    return id;
  };
  add(datasetId);
  for (const triple of triples) {
    if (triple.object_type === "literal") continue;
    if (!showTypes) {
      const hidden = [
        RDF_TYPE,
        "https://w3id.org/construct-dcat#usesOntology",
        "https://w3id.org/construct-dcat#describesAssetType",
        "http://www.w3.org/ns/dcat#accessURL",
        "http://www.w3.org/ns/dcat#downloadURL",
      ];
      if (hidden.includes(triple.predicate)) continue;
      if (
        [
          "http://www.w3.org/ns/dcat#dataset",
          "http://www.w3.org/ns/dcat#seriesMember",
        ].includes(triple.predicate) &&
        triple.object !== datasetId
      )
        continue;
    }
    const source = add(triple.subject, triple.subject_type);
    const target = add(triple.object, triple.object_type);
    edges.push({ source, target, predicate: triple.predicate });
  }
  // Shortest directed distance from containment roots. Cycles stay bounded.
  const incoming = new Set(edges.map((e) => e.target));
  let frontier = [...nodes.keys()].filter((id) => !incoming.has(id));
  if (!frontier.length) frontier = [identity(datasetId, "uri")];
  const ranks = new Map(frontier.map((id) => [id, 0]));
  for (let depth = 0; frontier.length && depth < nodes.size; depth++) {
    const next = [];
    for (const source of frontier)
      for (const edge of edges.filter((e) => e.source === source)) {
        if (!ranks.has(edge.target)) {
          ranks.set(edge.target, depth + 1);
          next.push(edge.target);
        }
      }
    frontier = next;
  }
  const columns = new Map();
  for (const node of nodes.values()) {
    const rank = ranks.get(node.id) ?? 1;
    if (!columns.has(rank)) columns.set(rank, []);
    columns.get(rank).push(node);
  }
  for (const [rank, column] of columns)
    column.forEach((node, i) => {
      node.x = 110 + rank * 270;
      node.y = 230 + (i - (column.length - 1) / 2) * 105;
    });
  if (!showTypes) {
    const root = identity(datasetId, "uri");
    const parents = new Set(
      edges.filter((e) => e.target === root).map((e) => e.source),
    );
    const others = [...nodes.values()].filter(
      (n) => n.id !== root && !parents.has(n.id),
    );
    nodes.get(root).x = 365;
    nodes.get(root).y = 230;
    [...parents].forEach((id, i) => {
      nodes.get(id).x = 110;
      nodes.get(id).y = 230 + (i - (parents.size - 1) / 2) * 105;
    });
    others.forEach((n, i) => {
      n.x = 640;
      n.y = 230 + (i - (others.length - 1) / 2) * 105;
    });
  }
  return { nodes: [...nodes.values()], edges };
}
export function mountGraph(el, detail, datasets, navigate) {
  const ns = "http://www.w3.org/2000/svg";
  let model,
    svg,
    layer,
    selected = identity(detail.dataset_id, "uri"),
    scale = 1,
    tx = 0,
    ty = 0;
  const svgNode = (tag, attributes = {}) => {
    const element = document.createElementNS(ns, tag);
    for (const [key, value] of Object.entries(attributes))
      element.setAttribute(key, String(value));
    return element;
  };
  const textNode = (tag, className, content) => {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = content;
    return element;
  };
  const transform = () =>
    layer.setAttribute("transform", `translate(${tx} ${ty}) scale(${scale})`);
  function fit() {
    const xs = model.nodes.map((n) => n.x),
      ys = model.nodes.map((n) => n.y);
    const minX = Math.min(...xs) - 115,
      maxX = Math.max(...xs) + 115,
      minY = Math.min(...ys) - 50,
      maxY = Math.max(...ys) + 50;
    scale = Math.min(1.3, 760 / (maxX - minX), 380 / (maxY - minY));
    tx = 430 - ((minX + maxX) / 2) * scale;
    ty = 230 - ((minY + maxY) / 2) * scale;
    transform();
  }
  function zoom(factor, point = { x: 430, y: 230 }) {
    const next = Math.max(0.15, Math.min(4, scale * factor));
    tx = point.x - ((point.x - tx) * next) / scale;
    ty = point.y - ((point.y - ty) * next) / scale;
    scale = next;
    transform();
  }
  function point(event) {
    const p = new DOMPoint(event.clientX, event.clientY);
    return p.matrixTransform(svg.getScreenCTM().inverse());
  }
  function inspect(id) {
    selected = id;
    draw();
    const node = model.nodes.find((n) => n.id === id);
    if (!node) return;
    el.nodeInspector.replaceChildren(
      textNode(
        "p",
        "eyebrow",
        node.value === detail.dataset_id
          ? "Selected dataset"
          : "Selected resource",
      ),
      textNode("h4", "", node.label),
      textNode(
        "p",
        "mono resource-id",
        node.type === "bnode" ? `Blank node: ${node.value}` : node.value,
      ),
    );
    const properties = detail.triples.filter(
      (t) => identity(t.subject, t.subject_type) === id,
    );
    const list = document.createElement("dl");
    list.className = "node-properties";
    for (const triple of properties) {
      const row = document.createElement("div"),
        term = textNode("dt", "", short(triple.predicate)),
        value = textNode("dd", "", triple.object);
      term.title = triple.predicate;
      if (triple.language)
        value.append(textNode("span", "language-tag", ` @${triple.language}`));
      if (
        triple.datatype &&
        !triple.language &&
        triple.datatype !== "http://www.w3.org/2001/XMLSchema#string"
      ) {
        const datatype = textNode(
          "span",
          "language-tag",
          ` (${short(triple.datatype)})`,
        );
        datatype.title = triple.datatype;
        value.append(datatype);
      }
      if (
        triple.object_type !== "literal" &&
        model.nodes.some(
          (n) => n.id === identity(triple.object, triple.object_type),
        )
      ) {
        const button = textNode(
          "button",
          "property-link",
          short(triple.object),
        );
        button.type = "button";
        button.title = triple.object;
        button.onclick = () =>
          inspect(identity(triple.object, triple.object_type));
        value.replaceChildren(button);
      }
      row.append(term, value);
      list.append(row);
    }
    if (!properties.length)
      el.nodeInspector.append(
        textNode(
          "p",
          "muted",
          "Linked resource — no local properties in this dataset’s description.",
        ),
      );
    else el.nodeInspector.append(list);
    // Resolve a related dataset using its publisher listing, without merging graphs.
    for (const dataset of datasets.filter(
      (d) =>
        d.dataset_id === node.value &&
        !(
          d.dataset_id === detail.dataset_id &&
          d.metadata?.graph === detail.metadata?.graph
        ),
    )) {
      const button = textNode(
        "button",
        "secondary",
        `Explore dataset · ${dataset.provider}`,
      );
      button.type = "button";
      button.onclick = () => navigate(dataset);
      el.nodeInspector.append(button);
    }
  }
  function draw() {
    layer.replaceChildren();
    const defs = svgNode("defs");
    const marker = svgNode("marker", {
      id: "graph-arrow",
      viewBox: "0 0 10 10",
      refX: 10,
      refY: 5,
      markerWidth: 7,
      markerHeight: 7,
      orient: "auto-start-reverse",
    });
    marker.append(
      svgNode("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#8ea7aa" }),
    );
    defs.append(marker);
    layer.append(defs);
    for (const edge of model.edges) {
      const source = model.nodes.find((n) => n.id === edge.source),
        target = model.nodes.find((n) => n.id === edge.target);
      const dx = target.x - source.x,
        dy = target.y - source.y,
        distance = Math.hypot(dx, dy) || 1;
      const x1 = source.x + (dx / distance) * 55,
        y1 = source.y + (dy / distance) * 22,
        x2 = target.x - (dx / distance) * 95,
        y2 = target.y - (dy / distance) * 27;
      const path = svgNode("path", {
        class: "graph-edge",
        d:
          edge.source === edge.target
            ? `M ${source.x} ${source.y - 28} C ${source.x + 150} ${source.y - 100} ${source.x + 150} ${source.y + 100} ${source.x} ${source.y + 28}`
            : `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1} ${(x1 + x2) / 2} ${y2} ${x2} ${y2}`,
        "marker-end": "url(#graph-arrow)",
      });
      const title = svgNode("title");
      title.textContent = edge.predicate;
      path.append(title);
      layer.append(path);
      const label = svgNode("text", {
        class: "graph-label",
        x: (x1 + x2) / 2,
        y: (y1 + y2) / 2 - (Math.abs(dy) < 40 ? 40 : 8),
        "text-anchor": "middle",
      });
      label.textContent = short(edge.predicate);
      layer.append(label);
    }
    for (const node of model.nodes) {
      const group = svgNode("g", {
        class: `graph-resource${node.id === selected ? " active" : ""}`,
        transform: `translate(${node.x} ${node.y})`,
        tabindex: 0,
        role: "button",
        "aria-label": `Inspect ${node.value}`,
        "data-node": node.id,
      });
      group.append(
        svgNode("rect", { x: -96, y: -28, width: 192, height: 56, rx: 12 }),
      );
      const label = svgNode("text", { "text-anchor": "middle", y: -2 });
      label.textContent =
        node.label.length > 24 ? node.label.slice(0, 22) + "…" : node.label;
      group.append(label);
      const subtitle = svgNode("text", {
        class: "graph-node-kind",
        "text-anchor": "middle",
        y: 16,
      });
      subtitle.textContent =
        node.value === detail.dataset_id
          ? "SELECTED DATASET"
          : node.type === "bnode"
            ? "BLANK NODE"
            : "RESOURCE";
      group.append(subtitle);
      const title = svgNode("title");
      title.textContent = node.value;
      group.append(title);
      group.onkeydown = (event) => {
        if (["Enter", " "].includes(event.key)) {
          event.preventDefault();
          inspect(node.id);
          layer.querySelectorAll("[data-node]").forEach((g) => {
            if (g.dataset.node === node.id) g.focus();
          });
        }
      };
      layer.append(group);
    }
    transform();
  }
  function build() {
    model = graphModel(
      detail.triples || [],
      detail.dataset_id,
      el.showTypes.checked,
    );
    if (!model.nodes.some((n) => n.id === selected))
      selected = identity(detail.dataset_id, "uri");
    svg = svgNode("svg", {
      viewBox: "0 0 860 460",
      role: "group",
      "aria-label": "Interactive dataset resource graph",
    });
    layer = svgNode("g");
    svg.append(layer);
    el.rdfGraph.replaceChildren(svg);
    el.graphCount.textContent = `${model.nodes.length} resources · ${model.edges.length} links`;
    draw();
    fit();
    inspect(selected);
    let drag;
    svg.onpointerdown = (event) => {
      if (event.button !== 0) return;
      const start = point(event),
        id = event.target.closest("[data-node]")?.dataset.node;
      const node = model.nodes.find((n) => n.id === id);
      drag = { start, node, x: node?.x, y: node?.y, tx, ty, moved: false };
      svg.setPointerCapture(event.pointerId);
    };
    svg.onpointermove = (event) => {
      if (!drag) return;
      const current = point(event),
        dx = current.x - drag.start.x,
        dy = current.y - drag.start.y;
      if (Math.hypot(dx, dy) > 3) drag.moved = true;
      if (drag.node) {
        drag.node.x = drag.x + dx / scale;
        drag.node.y = drag.y + dy / scale;
        draw();
      } else {
        tx = drag.tx + dx;
        ty = drag.ty + dy;
        transform();
      }
    };
    svg.onpointerup = (event) => {
      if (drag?.node && !drag.moved) inspect(drag.node.id);
      drag = null;
      if (svg.hasPointerCapture(event.pointerId))
        svg.releasePointerCapture(event.pointerId);
    };
    svg.onpointercancel = () => {
      drag = null;
    };
    svg.addEventListener(
      "wheel",
      (event) => {
        event.preventDefault();
        zoom(event.deltaY < 0 ? 1.12 : 1 / 1.12, point(event));
      },
      { passive: false },
    );
  }
  el.zoomIn.onclick = () => zoom(1.2);
  el.zoomOut.onclick = () => zoom(1 / 1.2);
  el.fitGraph.onclick = fit;
  el.showTypes.onchange = build;
  build();
}
