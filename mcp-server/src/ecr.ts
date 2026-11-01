import { BatchGetImageCommand, type ECRClient } from "@aws-sdk/client-ecr";

export const INDEX_MEDIA_TYPES = [
  "application/vnd.oci.image.index.v1+json",
  "application/vnd.docker.distribution.manifest.list.v2+json",
];

export type IndexChild = { digest: string; platform: string; isAttestation: boolean };

type IndexManifest = {
  manifests?: {
    digest: string;
    platform?: { os?: string; architecture?: string };
    annotations?: Record<string, string>;
  }[];
};

export function isIndex(mediaType: string | undefined): boolean {
  return INDEX_MEDIA_TYPES.includes(mediaType ?? "");
}

// Reads an image index and returns the manifests it references (images and attestations).
export async function getIndexChildren(
  ecr: ECRClient,
  repositoryName: string,
  indexDigest: string,
): Promise<IndexChild[]> {
  const fetched = await ecr.send(
    new BatchGetImageCommand({
      repositoryName,
      imageIds: [{ imageDigest: indexDigest }],
      acceptedMediaTypes: INDEX_MEDIA_TYPES,
    }),
  );
  const index = JSON.parse(fetched.images?.[0]?.imageManifest ?? "{}") as IndexManifest;
  return (index.manifests ?? []).map((m) => ({
    digest: m.digest,
    platform: `${m.platform?.os ?? "unknown"}/${m.platform?.architecture ?? "unknown"}`,
    isAttestation: m.annotations?.["vnd.docker.reference.type"] === "attestation-manifest",
  }));
}
