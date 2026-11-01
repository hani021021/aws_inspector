import { RemovalPolicy, Stack, Tags, type StackProps } from "aws-cdk-lib";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import type { Construct } from "constructs";

export interface RemediationStackProps extends StackProps {
  /** ECR repository whose pushes start the workflow. */
  repositoryName: string;
}

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
  }
}
