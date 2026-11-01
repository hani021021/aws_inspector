"""Deletes outdated ECR images after a deployment - only with explicit approval (--apply).

The plan is fixed code, not a model decision: every image except the one carrying a
protected tag (default "latest") and the manifests it references. Same rules as
list_images in the MCP server (mcp-server/src/deletion-plan.ts).
"""

import json
from dataclasses import dataclass, field

import boto3

INDEX_MEDIA_TYPES = {
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
}


@dataclass
class RepoImage:
    digest: str
    tags: list[str]
    children: list[str] = field(default_factory=list)


@dataclass
class DeletionPlan:
    protected: list[str]
    first: list[str]  # image indexes and single-manifest images
    then: list[str]  # child manifests of the indexes deleted first
    reason: str = ""

    @property
    def empty(self) -> bool:
        return not (self.first or self.then)


def build_plan(images: list[RepoImage], protected_tags: list[str]) -> DeletionPlan:
    def has_protected_tag(image: RepoImage) -> bool:
        return any(tag in protected_tags for tag in image.tags)

    parents: dict[str, list[RepoImage]] = {}
    for image in images:
        for child in image.children:
            parents.setdefault(child, []).append(image)

    protected = [
        i.digest
        for i in images
        if has_protected_tag(i) or any(has_protected_tag(p) for p in parents.get(i.digest, []))
    ]
    if not protected:
        return DeletionPlan([], [], [], reason="no image carries a protected tag")

    deletable = [i for i in images if i.digest not in protected]
    return DeletionPlan(
        protected=protected,
        first=[i.digest for i in deletable if i.digest not in parents],
        then=[i.digest for i in deletable if i.digest in parents],
    )


def load_images(ecr, repository: str) -> list[RepoImage]:
    images = []
    for page in ecr.get_paginator("describe_images").paginate(repositoryName=repository):
        for detail in page.get("imageDetails", []):
            image = RepoImage(detail["imageDigest"], detail.get("imageTags", []))
            if detail.get("imageManifestMediaType") in INDEX_MEDIA_TYPES:
                fetched = ecr.batch_get_image(
                    repositoryName=repository,
                    imageIds=[{"imageDigest": image.digest}],
                    acceptedMediaTypes=sorted(INDEX_MEDIA_TYPES),
                )
                manifest = json.loads(fetched["images"][0]["imageManifest"])
                image.children = [m["digest"] for m in manifest.get("manifests", [])]
            images.append(image)
    return images


def protected_scans_ready(
    ecr, repository: str, images: list[RepoImage], plan: DeletionPlan
) -> bool:
    """The new image must be fully scanned before old ones go (lesson 9)."""
    by_digest = {i.digest: i for i in images}
    for digest in plan.protected:
        image = by_digest[digest]
        if image.children:  # an index is never scanned itself
            continue
        status = ecr.describe_image_scan_findings(
            repositoryName=repository, imageId={"imageDigest": digest}, maxResults=1
        )["imageScanStatus"]["status"]
        # Attestation manifests are not scannable and report UNSUPPORTED_IMAGE.
        if status not in ("ACTIVE", "UNSUPPORTED_IMAGE"):
            return False
    return True


def delete(ecr, repository: str, plan: DeletionPlan) -> list[dict]:
    """Deletes indexes first, then their children; stops on the first failure."""
    deleted = []
    for batch in (plan.first, plan.then):
        if not batch:
            continue
        response = ecr.batch_delete_image(
            repositoryName=repository, imageIds=[{"imageDigest": d} for d in batch]
        )
        deleted += response.get("imageIds", [])
        if response.get("failures"):
            raise RuntimeError(f"ECR refused to delete: {response['failures']}")
    return deleted


def ecr_client():
    return boto3.client("ecr")
