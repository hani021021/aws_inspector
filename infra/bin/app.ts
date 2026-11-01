import { App } from "aws-cdk-lib";
import { RemediationStack } from "../lib/remediation-stack.js";

// Deploys only into the sandbox account: CDK refuses to deploy when the
// credentials belong to a different account than `env.account`.
const account = process.env.EXPECTED_AWS_ACCOUNT_ID;
if (!account || !/^\d{12}$/.test(account)) {
  throw new Error("Set EXPECTED_AWS_ACCOUNT_ID to the 12-digit sandbox account ID");
}

// Kept out of the repository; pass it on deploy: cdk deploy -c notifyEmail=you@example.com
const app = new App();
const notifyEmail = app.node.tryGetContext("notifyEmail") as string | undefined;
if (!notifyEmail) {
  throw new Error("Pass the notification address: cdk deploy -c notifyEmail=you@example.com");
}

new RemediationStack(app, "InspectorRemediation", {
  env: { account, region: process.env.AWS_REGION ?? "eu-north-1" },
  repositoryName: "demo-service",
  notifyEmail,
  githubRepository: "hani021021/aws_inspector",
});
