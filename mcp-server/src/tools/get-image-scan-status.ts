import {
  DescribeImageScanFindingsCommand,
  DescribeImagesCommand,
  type ECRClient,
} from "@aws-sdk/client-ecr";
import type { McpServer } from "@modelcontextprotocol/server";
import * as z from "zod/v4";
import { getIndexChildren, isIndex } from "../ecr.js";

const inputSchema = z
  .object({
    repositoryName: z.string().min(1).describe("ECR repository name, e.g. demo-service"),
    imageTag: z.string().min(1).optional().describe("Image tag, e.g. 1.0.2"),
    imageDigest: z
      .string()
      .regex(/^sha256:[0-9a-f]{64}$/)
      .optional()
      .describe("Image digest, used instead of imageTag"),
  })
  .refine((input) => Boolean(input.imageTag) !== Boolean(input.imageDigest), {
    message: "Provide exactly one of imageTag or imageDigest",
  });

const outputSchema = z.object({
  digest: z.string(),
  mediaType: z.string(),
  isIndex: z.boolean(),
  images: z.array(
    z.object({
      digest: z.string(),
      platform: z.string(),
      scanStatus: z.string(),
      description: z.string(),
      readyForComparison: z.boolean(),
    }),
  ),
});

// Lessons 3 and 9 of docs/manual-run.md: an image index is never scanned itself,
// and findings keep arriving until the scan status is ACTIVE.
export function registerGetImageScanStatus(server: McpServer, ecr: ECRClient): void {
  server.registerTool(
    "get_image_scan_status",
    {
      title: "Get image scan status",
      description:
        "Get the Amazon Inspector scan status of an ECR image. If the tag points to an image index, " +
        "the status of each child image manifest is returned instead (attestations are skipped), " +
        "because Inspector scans the child manifests, not the index. " +
        "Only compare findings when readyForComparison is true: findings may still arrive while the status is COMPLETE.",
      inputSchema,
      outputSchema,
      annotations: { readOnlyHint: true },
    },
    async ({ repositoryName, imageTag, imageDigest }) => {
      const imageId = imageDigest ? { imageDigest } : { imageTag };
      const described = await ecr.send(
        new DescribeImagesCommand({ repositoryName, imageIds: [imageId] }),
      );
      const detail = described.imageDetails?.[0];
      if (!detail?.imageDigest) {
        return { content: [{ type: "text", text: "Image not found" }], isError: true };
      }

      const mediaType = detail.imageManifestMediaType ?? "unknown";
      const index = isIndex(mediaType);
      const targets = index
        ? (await getIndexChildren(ecr, repositoryName, detail.imageDigest)).filter(
            (child) => !child.isAttestation,
          )
        : [{ digest: detail.imageDigest, platform: "unknown" }];

      const images = await Promise.all(
        targets.map(async ({ digest, platform }) => {
          const scan = await ecr.send(
            new DescribeImageScanFindingsCommand({
              repositoryName,
              imageId: { imageDigest: digest },
              maxResults: 1,
            }),
          );
          const scanStatus = scan.imageScanStatus?.status ?? "UNKNOWN";
          return {
            digest,
            platform,
            scanStatus,
            description: scan.imageScanStatus?.description ?? "",
            readyForComparison: scanStatus === "ACTIVE",
          };
        }),
      );

      const result = { digest: detail.imageDigest, mediaType, isIndex: index, images };
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        structuredContent: result,
      };
    },
  );
}
