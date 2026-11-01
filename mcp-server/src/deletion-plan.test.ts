import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildDeletionPlan, type RepoImage } from "./deletion-plan.js";

const image = (digest: string, tags: string[] = [], children: string[] = []): RepoImage => ({
  digest,
  tags,
  children,
});

describe("buildDeletionPlan", () => {
  it("deletes nothing when no image carries a protected tag", () => {
    const plan = buildDeletionPlan([image("a", ["c1"]), image("b", ["c2"])], ["latest"]);

    assert.equal(plan.protectedTagFound, false);
    assert.deepEqual(plan.first, []);
    assert.deepEqual(plan.then, []);
  });

  it("keeps the latest image and deletes all older single-manifest images", () => {
    const plan = buildDeletionPlan(
      [image("new", ["latest", "c3"]), image("old1", ["c2"]), image("old2", ["c1"])],
      ["latest"],
    );

    assert.deepEqual(plan.first, ["old1", "old2"]);
    assert.deepEqual(plan.then, []);
  });

  it("protects the children of the latest index", () => {
    const plan = buildDeletionPlan(
      [image("index", ["latest"], ["img", "att"]), image("img"), image("att")],
      ["latest"],
    );

    assert.deepEqual(plan.first, []);
    assert.deepEqual(plan.then, []);
    assert.ok(plan.images.every((i) => i.protected));
  });

  it("deletes an old index before its children", () => {
    const plan = buildDeletionPlan(
      [image("new", ["latest"]), image("oldIndex", ["c1"], ["img", "att"]), image("img"), image("att")],
      ["latest"],
    );

    assert.deepEqual(plan.first, ["oldIndex"]);
    assert.deepEqual(plan.then, ["img", "att"]);
  });

  it("deletes untagged manifests that no index references", () => {
    const plan = buildDeletionPlan([image("new", ["latest"]), image("orphan")], ["latest"]);

    assert.deepEqual(plan.first, ["orphan"]);
  });

  it("keeps a manifest shared by the latest index and an old index", () => {
    const plan = buildDeletionPlan(
      [image("newIndex", ["latest"], ["shared"]), image("oldIndex", ["c1"], ["shared"]), image("shared")],
      ["latest"],
    );

    assert.deepEqual(plan.first, ["oldIndex"]);
    assert.deepEqual(plan.then, []);
  });

  it("supports several protected tags", () => {
    const plan = buildDeletionPlan(
      [image("prod", ["latest"]), image("staging", ["staging-latest"]), image("old", ["c1"])],
      ["latest", "staging-latest"],
    );

    assert.deepEqual(plan.first, ["old"]);
  });
});
