import pytest

from remediation_agent.cleanup import DeletionPlan, RepoImage, build_plan, delete


def image(digest, tags=(), children=()):
    return RepoImage(digest, list(tags), list(children))


def test_deletes_nothing_without_a_protected_tag():
    plan = build_plan([image("a", ["c1"]), image("b", ["c2"])], ["latest"])

    assert plan.empty
    assert plan.reason


def test_keeps_latest_and_deletes_older_images():
    plan = build_plan(
        [image("new", ["latest", "1.0.4"]), image("old1", ["1.0.3"]), image("old2", ["1.0.2"])],
        ["latest"],
    )

    assert plan.protected == ["new"]
    assert plan.first == ["old1", "old2"]


def test_protects_the_children_of_the_latest_index():
    plan = build_plan(
        [image("index", ["latest"], ["img", "att"]), image("img"), image("att")], ["latest"]
    )

    assert plan.empty
    assert sorted(plan.protected) == ["att", "img", "index"]


def test_deletes_an_old_index_before_its_children():
    plan = build_plan(
        [
            image("new", ["latest"]),
            image("old", ["1.0.3"], ["img", "att"]),
            image("img"),
            image("att"),
        ],
        ["latest"],
    )

    assert plan.first == ["old"]
    assert plan.then == ["img", "att"]


def test_keeps_a_manifest_shared_with_the_latest_index():
    plan = build_plan(
        [
            image("new", ["latest"], ["shared"]),
            image("old", ["1.0.3"], ["shared"]),
            image("shared"),
        ],
        ["latest"],
    )

    assert plan.first == ["old"]
    assert plan.then == []


class FakeEcr:
    def __init__(self, failures=None):
        self.calls = []
        self.failures = failures or []

    def batch_delete_image(self, repositoryName, imageIds):
        self.calls.append([i["imageDigest"] for i in imageIds])
        return {"imageIds": imageIds, "failures": self.failures}


def test_delete_runs_indexes_first_then_children():
    ecr = FakeEcr()

    delete(ecr, "repo", DeletionPlan(protected=["new"], first=["old"], then=["img", "att"]))

    assert ecr.calls == [["old"], ["img", "att"]]


def test_delete_stops_when_ecr_refuses():
    ecr = FakeEcr(failures=[{"failureCode": "ImageReferencedByManifestList"}])

    with pytest.raises(RuntimeError):
        delete(ecr, "repo", DeletionPlan(protected=["new"], first=["old"], then=["img"]))

    assert ecr.calls == [["old"]]
