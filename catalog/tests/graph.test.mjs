import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
const source = await readFile(
  new URL("../ui/graph.js", import.meta.url),
  "utf8",
);
const { graphModel } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);
test("resource graph excludes literals and keeps RDF types optional", () => {
  const triples = [
    {
      subject: "urn:dataset",
      predicate: "urn:title",
      object: "https://a.test/literal",
      object_type: "literal",
    },
    {
      subject: "urn:dataset",
      predicate: "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      object: "urn:Dataset",
      object_type: "uri",
    },
    {
      subject: "urn:dataset",
      predicate: "urn:distribution",
      object: "distribution",
      object_type: "bnode",
    },
    {
      subject: "distribution",
      subject_type: "bnode",
      predicate: "urn:accessURL",
      object: "https://a.test/data",
      object_type: "uri",
    },
  ];
  const model = graphModel(triples, "urn:dataset");
  assert.equal(model.nodes.length, 3);
  assert.equal(model.edges.length, 2);
  assert.ok(!model.nodes.some((n) => n.value.endsWith("literal")));
  assert.equal(graphModel(triples, "urn:dataset", true).nodes.length, 4);
  assert.equal(model.nodes.filter((n) => n.type === "bnode").length, 1);
});
test("cyclic and disconnected resource graphs have finite positions", () => {
  const triples = [
    { subject: "urn:a", predicate: "urn:rel", object: "urn:b" },
    { subject: "urn:b", predicate: "urn:rel", object: "urn:a" },
    { subject: "urn:c", predicate: "urn:rel", object: "urn:c" },
  ];
  const model = graphModel(triples, "urn:a");
  assert.ok(
    model.nodes.every((n) => Number.isFinite(n.x) && Number.isFinite(n.y)),
  );
  assert.equal(model.edges.length, 3);
  assert.equal(graphModel([], "urn:a").nodes.length, 1);
});

test("focused graph keeps the immediate parent and dataset links, full view restores the path", () => {
  const dcat = "http://www.w3.org/ns/dcat#";
  const triples = [
    {
      subject: "urn:catalog",
      predicate: dcat + "dataset",
      object: "urn:series",
    },
    {
      subject: "urn:series",
      predicate: dcat + "seriesMember",
      object: "urn:nested",
    },
    {
      subject: "urn:nested",
      predicate: dcat + "seriesMember",
      object: "urn:dataset",
    },
    {
      subject: "urn:dataset",
      predicate: dcat + "distribution",
      object: "urn:distribution",
    },
    {
      subject: "urn:distribution",
      predicate: dcat + "accessURL",
      object: "https://a.test/data",
    },
  ];
  const focused = graphModel(triples, "urn:dataset");
  assert.deepEqual(
    new Set(focused.nodes.map((n) => n.value)),
    new Set(["urn:dataset", "urn:nested", "urn:distribution"]),
  );
  assert.equal(focused.edges.length, 2);
  assert.equal(graphModel(triples, "urn:dataset", true).edges.length, 5);
});
