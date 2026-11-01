import { ECRClient } from "@aws-sdk/client-ecr";
import { Inspector2Client } from "@aws-sdk/client-inspector2";
import { McpServer } from "@modelcontextprotocol/server";
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { checkAccount, currentAccount } from "./account.js";
import { registerCheckPackageVersion } from "./tools/check-package-version.js";
import { registerGetImageScanStatus } from "./tools/get-image-scan-status.js";
import { registerListActiveFindings } from "./tools/list-active-findings.js";
import { registerListImages } from "./tools/list-images.js";

// AWS_PROFILE and AWS_REGION come from the environment; the default credential
// chain also resolves `aws login` profiles, so no access keys are stored anywhere.
const account = await currentAccount();
const accountError = checkAccount(account, process.env.EXPECTED_AWS_ACCOUNT_ID);
if (accountError) {
  console.error(`aws-inspector MCP server refuses to start: ${accountError}`);
  process.exit(1);
}

const inspector = new Inspector2Client({});
const ecr = new ECRClient({});

// The image running in production carries one of these tags (comma-separated).
const protectedTags = (process.env.PROTECTED_TAGS ?? "latest")
  .split(",")
  .map((tag) => tag.trim())
  .filter(Boolean);

// stdout carries the MCP protocol – log to stderr only.
const server = new McpServer({ name: "aws-inspector", version: "0.1.0" });

registerCheckPackageVersion(server);
registerListActiveFindings(server, inspector);
registerGetImageScanStatus(server, ecr);
registerListImages(server, ecr, protectedTags);

await server.connect(new StdioServerTransport());
console.error(`aws-inspector MCP server running on stdio (AWS account ${account})`);
