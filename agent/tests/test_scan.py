import json

from remediation_agent.scan import scan_state

INDEX = "application/vnd.oci.image.index.v1+json"
MANIFEST = "application/vnd.oci.image.manifest.v1+json"


class FakeEcr:
    def __init__(self, media_type, children=(), statuses=None):
        self.media_type = media_type
        self.children = children
        self.statuses = statuses or {}

    def describe_images(self, repositoryName, imageIds):
        return {"imageDetails": [{"imageDigest": "top", "imageManifestMediaType": self.media_type}]}

    def batch_get_image(self, repositoryName, imageIds, acceptedMediaTypes):
        manifests = [
            {"digest": d, "annotations": {"vnd.docker.reference.type": "attestation-manifest"}}
            if d == "att"
            else {"digest": d}
            for d in self.children
        ]
        return {"images": [{"imageManifest": json.dumps({"manifests": manifests})}]}

    def describe_image_scan_findings(self, repositoryName, imageId, maxResults):
        return {"imageScanStatus": {"status": self.statuses[imageId["imageDigest"]]}}


class FakeInspector:
    def __init__(self, findings_per_digest):
        self.findings_per_digest = findings_per_digest

    def get_paginator(self, name):
        return self

    def paginate(self, filterCriteria):
        digest = filterCriteria["ecrImageHash"][0]["value"]
        return [{"findings": [{}] * self.findings_per_digest.get(digest, 0)}]


def test_counts_findings_of_the_index_children_but_not_the_attestation():
    ecr = FakeEcr(INDEX, children=["img", "att"], statuses={"img": "ACTIVE"})

    state = scan_state(ecr, FakeInspector({"img": 3}), "repo", "latest")

    assert state["digests"] == ["img"]
    assert state["ready"] and state["count"] == 3


def test_not_ready_while_the_scan_is_complete_but_not_active():
    ecr = FakeEcr(MANIFEST, statuses={"top": "COMPLETE"})

    state = scan_state(ecr, FakeInspector({"top": 0}), "repo", "latest")

    assert not state["ready"]
    assert "count" not in state
