import { App } from "aws-cdk-lib";
import { RemediationStack } from "../lib/remediation-stack.js";

// Deploys only into the sandbox account: CDK refuses to deploy when the
// credentials belong to a different account than `env.account`.
const account = process.env.EXPECTED_AWS_ACCOUNT_ID;
if (!account || !/^\d{12}$/.test(account)) {
  throw new Error("Set EXPECTED_AWS_ACCOUNT_ID to the 12-digit sandbox account ID");
}

const app = new App();
new RemediationStack(app, "InspectorRemediation", {
  env: { account, region: process.env.AWS_REGION ?? "eu-north-1" },
  repositoryName: "demo-service",
});
