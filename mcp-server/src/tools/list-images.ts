import { paginateDescribeImages, type ECRClient } from "@aws-sdk/client-ecr";
import type { McpServer } from "@modelcontextprotocol/server";
import * as z from "zod/v4";
import { buildDeletionPlan } from "../deletion-plan.js";
import { getIndexChildren, isIndex } from "../ecr.js";

const inputSchema = z.object({
  repositoryName: z.string().min(1).describe("ECR repository name, e.g. demo-service"),
});

const outputSchema = z.object({
  protectedTags: z.array(z.string()),
  protectedTagFound: z.boolean(),
  images: z.array(
    z.object({
      digest: z.string(),
      tags: z.array(z.string()),
      mediaType: z.string(),
      pushedAt: z.string().optional(),
      isIndex: z.boolean(),
      children: z.array(z.string()),
      protected: z.boolean(),
    }),
  ),
  deletionPlan: z.object({
    first: z.array(z.string()).describe("Image indexes and single-manifest images"),
    then: z.array(z.string()).describe("Child manifests of the indexes deleted first"),
  }),
});

// Lesson 8 of docs/manual-run.md and the production rule: the image tagged with a
// protected tag (default "latest") is running in production and is never deleted.
// Protected tags come from configuration, not from the model.
export function registerListImages(server: McpServer, ecr: ECRClient, protectedTags: string[]): void {
  server.registerTool(
    "list_images",
    {
      title: "List images and deletion plan",
      description:
        "List all images in an ECR repository, grouping image indexes with their child manifests, " +
        `and propose a deletion plan. Images tagged with ${protectedTags.join(", ")} are protected and never part of the plan. ` +
        "If no image carries a protected tag, the plan is empty because it is unclear what runs in production. " +
        "This tool only proposes; deleting requires human approval.",
      inputSchema,
      outputSchema,
      annotations: { readOnlyHint: true },
    },
    async ({ repositoryName }) => {
      const details = [];
      for await (const page of paginateDescribeImages({ client: ecr }, { repositoryName })) {
        details.push(...(page.imageDetails ?? []));
      }

      const images = [];
      for (const d of details) {
        if (!d.imageDigest) continue;
        const index = isIndex(d.imageManifestMediaType);
        images.push({
          digest: d.imageDigest,
          tags: d.imageTags ?? [],
          mediaType: d.imageManifestMediaType ?? "unknown",
          pushedAt: d.imagePushedAt?.toISOString(),
          isIndex: index,
          children: index
            ? (await getIndexChildren(ecr, repositoryName, d.imageDigest)).map((c) => c.digest)
            : [],
        });
      }

      const plan = buildDeletionPlan(images, protectedTags);
      const result = {
        protectedTags,
        protectedTagFound: plan.protectedTagFound,
        images: images.map((image, i) => ({ ...image, protected: plan.images[i]?.protected ?? true })),
        deletionPlan: { first: plan.first, then: plan.then },
      };
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        structuredContent: result,
      };
    },
  );
}
