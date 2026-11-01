"""Scan state of the image behind a tag (lessons 2, 3 and 9 of docs/manual-run.md)."""

import json

from remediation_agent.cleanup import INDEX_MEDIA_TYPES


def scanned_manifests(ecr, repository: str, tag: str) -> list[str]:
    """Digests Inspector scans for a tag: the image itself, or the children of an index."""
    detail = ecr.describe_images(repositoryName=repository, imageIds=[{"imageTag": tag}])[
        "imageDetails"
    ][0]
    if detail.get("imageManifestMediaType") not in INDEX_MEDIA_TYPES:
        return [detail["imageDigest"]]

    fetched = ecr.batch_get_image(
        repositoryName=repository,
        imageIds=[{"imageDigest": detail["imageDigest"]}],
        acceptedMediaTypes=sorted(INDEX_MEDIA_TYPES),
    )
    manifest = json.loads(fetched["images"][0]["imageManifest"])
    return [
        m["digest"]
        for m in manifest.get("manifests", [])
        if m.get("annotations", {}).get("vnd.docker.reference.type") != "attestation-manifest"
    ]


def _scan_status(ecr, repository: str, digest: str) -> str:
    try:
        response = ecr.describe_image_scan_findings(
            repositoryName=repository, imageId={"imageDigest": digest}, maxResults=1
        )
    except ecr.exceptions.ScanNotFoundException:
        # Right after a push the scan does not exist yet.
        return "PENDING"
    return response["imageScanStatus"]["status"]


def scan_state(ecr, inspector, repository: str, tag: str) -> dict:
    """`ready` once every scanned manifest is ACTIVE; `count` only then.

    One ready result is not final: findings can still arrive shortly after ACTIVE,
    so the caller compares two results a few minutes apart.
    """
    digests = scanned_manifests(ecr, repository, tag)
    statuses = {d: _scan_status(ecr, repository, d) for d in digests}
    ready = all(s == "ACTIVE" for s in statuses.values())
    state = {"repository": repository, "tag": tag, "digests": digests, "statuses": statuses}
    if not ready:
        return state | {"ready": False}

    paginator = inspector.get_paginator("list_findings")
    count = 0
    for digest in digests:
        criteria = {
            "findingStatus": [{"comparison": "EQUALS", "value": "ACTIVE"}],
            "ecrImageRepositoryName": [{"comparison": "EQUALS", "value": repository}],
            "ecrImageHash": [{"comparison": "EQUALS", "value": digest}],
        }
        count += sum(
            len(page.get("findings", [])) for page in paginator.paginate(filterCriteria=criteria)
        )
    return state | {"ready": True, "count": count}
