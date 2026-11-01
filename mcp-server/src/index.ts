import { ECRClient } from "@aws-sdk/client-ecr";
import { Inspector2Client } from "@aws-sdk/client-inspector2";
import { McpServer } from "@modelcontextprotocol/server";
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { registerCheckPackageVersion } from "./tools/check-package-version.js";
import { registerGetImageScanStatus } from "./tools/get-image-scan-status.js";
import { registerListActiveFindings } from "./tools/list-active-findings.js";

// AWS_PROFILE and AWS_REGION come from the environment; the default credential
// chain also resolves `aws login` profiles, so no access keys are stored anywhere.
const inspector = new Inspector2Client({});
const ecr = new ECRClient({});

// stdout carries the MCP protocol – log to stderr only.
const server = new McpServer({ name: "aws-inspector", version: "0.1.0" });

registerCheckPackageVersion(server);
registerListActiveFindings(server, inspector);
registerGetImageScanStatus(server, ecr);

await server.connect(new StdioServerTransport());
console.error("aws-inspector MCP server running on stdio");
