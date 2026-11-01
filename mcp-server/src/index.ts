import { McpServer } from "@modelcontextprotocol/server";
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import { registerCheckPackageVersion } from "./tools/check-package-version.js";

// stdout carries the MCP protocol – log to stderr only.
const server = new McpServer({ name: "aws-inspector", version: "0.1.0" });

registerCheckPackageVersion(server);

await server.connect(new StdioServerTransport());
console.error("aws-inspector MCP server running on stdio");
