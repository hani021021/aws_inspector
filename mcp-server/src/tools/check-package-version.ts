import type { McpServer } from "@modelcontextprotocol/server";
import * as z from "zod/v4";

const OSV_QUERY_URL = "https://api.osv.dev/v1/query";

const inputSchema = z.object({
  name: z.string().min(1).describe("npm package name, e.g. axios"),
  version: z.string().min(1).describe("Exact version to check, e.g. 1.20.0"),
});

const outputSchema = z.object({
  name: z.string(),
  version: z.string(),
  vulnerable: z.boolean(),
  vulnerabilities: z.array(
    z.object({
      id: z.string(),
      aliases: z.array(z.string()),
      summary: z.string(),
    }),
  ),
});

type OsvResponse = {
  vulns?: { id: string; aliases?: string[]; summary?: string }[];
  next_page_token?: string;
};

// Lesson 6 of docs/manual-run.md: a fix version can bring its own CVEs.
export function registerCheckPackageVersion(server: McpServer): void {
  server.registerTool(
    "check_package_version",
    {
      title: "Check npm package version",
      description:
        "Look up known vulnerabilities of an exact npm package version in the OSV database. " +
        "Use it before proposing a fix version: pick the lowest version without known vulnerabilities.",
      inputSchema,
      outputSchema,
      annotations: { readOnlyHint: true, openWorldHint: true },
    },
    async ({ name, version }) => {
      const vulns: NonNullable<OsvResponse["vulns"]> = [];
      let pageToken: string | undefined;

      do {
        const response = await fetch(OSV_QUERY_URL, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            package: { name, ecosystem: "npm" },
            version,
            page_token: pageToken,
          }),
        });
        if (!response.ok) {
          return {
            content: [{ type: "text", text: `OSV request failed: HTTP ${response.status}` }],
            isError: true,
          };
        }
        const page = (await response.json()) as OsvResponse;
        vulns.push(...(page.vulns ?? []));
        pageToken = page.next_page_token;
      } while (pageToken);

      const result = {
        name,
        version,
        vulnerable: vulns.length > 0,
        vulnerabilities: vulns.map((v) => ({
          id: v.id,
          aliases: v.aliases ?? [],
          summary: v.summary ?? "",
        })),
      };
      return {
        content: [{ type: "text", text: JSON.stringify(result) }],
        structuredContent: result,
      };
    },
  );
}
