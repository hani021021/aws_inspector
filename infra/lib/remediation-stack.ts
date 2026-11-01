import { fileURLToPath } from "node:url";
import { Duration, RemovalPolicy, Stack, Tags, type StackProps } from "aws-cdk-lib";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Repository } from "aws-cdk-lib/aws-ecr";
import { PolicyStatement } from "aws-cdk-lib/aws-iam";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { LogGroup, RetentionDays } from "aws-cdk-lib/aws-logs";
import type { Construct } from "constructs";

export interface RemediationStackProps extends StackProps {
  /** ECR repository whose pushes start the workflow. */
  repositoryName: string;
}

// The Python package in agent/src is the code of every Lambda; boto3 comes with the runtime.
const AGENT_SOURCE = fileURLToPath(new URL("../../agent/src", import.meta.url));

export class RemediationStack extends Stack {
  constructor(scope: Construct, id: string, props: RemediationStackProps) {
    super(scope, id, props);
    Tags.of(this).add("project", "aws-inspector-remediation");

    // One item per workflow run and step: who approved what, which images were deleted.
    new Table(this, "AuditLog", {
      partitionKey: { name: "runId", type: AttributeType.STRING },
      sortKey: { name: "step", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      // Sandbox: `cdk destroy` removes everything, so nothing keeps costing money.
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const repository = Repository.fromRepositoryName(this, "Repository", props.repositoryName);

    // Read-only: scan status of the image behind a tag and its active findings.
    const checkScan = this.pythonFunction("CheckScan", "remediation_agent.handlers.check_scan");
    checkScan.addToRolePolicy(
      new PolicyStatement({
        actions: ["ecr:DescribeImages", "ecr:BatchGetImage", "ecr:DescribeImageScanFindings"],
        resources: [repository.repositoryArn],
      }),
    );
    checkScan.addToRolePolicy(
      // No resource-level permissions for these. With enhanced scanning, ECR's
      // DescribeImageScanFindings reads the scan status from Inspector (ListCoverage).
      new PolicyStatement({
        actions: ["inspector2:ListFindings", "inspector2:ListCoverage"],
        resources: ["*"],
      }),
    );
  }

  private pythonFunction(id: string, handler: string): Function {
    return new Function(this, id, {
      runtime: Runtime.PYTHON_3_13,
      handler,
      code: Code.fromAsset(AGENT_SOURCE, { exclude: ["**/__pycache__"] }),
      timeout: Duration.minutes(1),
      memorySize: 256,
      logGroup: new LogGroup(this, `${id}Logs`, {
        retention: RetentionDays.ONE_WEEK,
        removalPolicy: RemovalPolicy.DESTROY,
      }),
    });
  }
}
