import { fileURLToPath } from "node:url";
import { CfnOutput, Duration, RemovalPolicy, Stack, Tags, type StackProps } from "aws-cdk-lib";
import { HttpApi, HttpMethod } from "aws-cdk-lib/aws-apigatewayv2";
import { HttpLambdaIntegration } from "aws-cdk-lib/aws-apigatewayv2-integrations";
import { AttributeType, BillingMode, Table } from "aws-cdk-lib/aws-dynamodb";
import { Repository } from "aws-cdk-lib/aws-ecr";
import { Rule } from "aws-cdk-lib/aws-events";
import { SfnStateMachine } from "aws-cdk-lib/aws-events-targets";
import { OidcProviderNative, PolicyStatement, Role, WebIdentityPrincipal } from "aws-cdk-lib/aws-iam";
import { Code, Function, Runtime } from "aws-cdk-lib/aws-lambda";
import { LogGroup, RetentionDays } from "aws-cdk-lib/aws-logs";
import { Topic } from "aws-cdk-lib/aws-sns";
import { EmailSubscription } from "aws-cdk-lib/aws-sns-subscriptions";
import {
  Choice,
  Condition,
  DefinitionBody,
  IntegrationPattern,
  JsonPath,
  Pass,
  StateMachine,
  Succeed,
  TaskInput,
  Wait,
  WaitTime,
} from "aws-cdk-lib/aws-stepfunctions";
import { DynamoAttributeValue, DynamoPutItem, LambdaInvoke, SnsPublish } from "aws-cdk-lib/aws-stepfunctions-tasks";
import type { Construct } from "constructs";

export interface RemediationStackProps extends StackProps {
  /** ECR repository whose pushes start the workflow. */
  repositoryName: string;
  /** Receives approval requests and results. */
  notifyEmail: string;
  /** GitHub repository ("owner/name") whose main branch may push images. */
  githubRepository: string;
}

// The Python package in agent/src is the code of every Lambda; boto3 comes with the runtime.
const AGENT_SOURCE = fileURLToPath(new URL("../../agent/src", import.meta.url));

export class RemediationStack extends Stack {
  constructor(scope: Construct, id: string, props: RemediationStackProps) {
    super(scope, id, props);
    Tags.of(this).add("project", "aws-inspector-remediation");

    // One item per workflow run and step: who approved what, which images were deleted.
    const auditLog = new Table(this, "AuditLog", {
      partitionKey: { name: "runId", type: AttributeType.STRING },
      sortKey: { name: "step", type: AttributeType.STRING },
      billingMode: BillingMode.PAY_PER_REQUEST,
      // Sandbox: `cdk destroy` removes everything, so nothing keeps costing money.
      removalPolicy: RemovalPolicy.DESTROY,
    });

    const repository = Repository.fromRepositoryName(this, "Repository", props.repositoryName);
    const readImages = new PolicyStatement({
      actions: ["ecr:DescribeImages", "ecr:BatchGetImage"],
      resources: [repository.repositoryArn],
    });

    const topic = new Topic(this, "Notifications");
    topic.addSubscription(new EmailSubscription(props.notifyEmail));

    // --- Lambdas, each with only the permissions it needs ---

    const checkScan = this.pythonFunction("CheckScan", "check_scan");
    checkScan.addToRolePolicy(readImages);
    checkScan.addToRolePolicy(
      new PolicyStatement({
        actions: ["ecr:DescribeImageScanFindings"],
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

    const planCleanup = this.pythonFunction("PlanCleanup", "plan_cleanup");
    planCleanup.addToRolePolicy(readImages);

    const deleteImages = this.pythonFunction("DeleteImages", "delete_images");
    deleteImages.addToRolePolicy(readImages);
    deleteImages.addToRolePolicy(
      new PolicyStatement({ actions: ["ecr:BatchDeleteImage"], resources: [repository.repositoryArn] }),
    );

    const approvalPage = this.pythonFunction("ApprovalPage", "approval_page");
    const api = new HttpApi(this, "ApprovalApi");
    api.addRoutes({
      path: "/approval",
      methods: [HttpMethod.GET, HttpMethod.POST],
      integration: new HttpLambdaIntegration("ApprovalIntegration", approvalPage),
    });

    const requestApproval = this.pythonFunction("RequestApproval", "request_approval", {
      APPROVAL_URL: `${api.apiEndpoint}/approval`,
      TOPIC_ARN: topic.topicArn,
    });
    topic.grantPublish(requestApproval);

    // --- Workflow ---

    const firstCheck = new LambdaInvoke(this, "Check scan", {
      lambdaFunction: checkScan,
      payload: TaskInput.fromObject({ repository: props.repositoryName, tag: "latest" }),
      payloadResponseOnly: true,
      resultPath: "$.first",
    });
    const secondCheck = new LambdaInvoke(this, "Check scan again", {
      lambdaFunction: checkScan,
      payload: TaskInput.fromObject({ repository: props.repositoryName, tag: "latest" }),
      payloadResponseOnly: true,
      resultPath: "$.second",
    });
    const waitForScan = new Wait(this, "Wait for scan", { time: WaitTime.duration(Duration.minutes(2)) });
    const waitBeforeRecount = new Wait(this, "Wait before recount", {
      time: WaitTime.duration(Duration.minutes(3)),
    });
    const keepLatestCount = new Pass(this, "Keep latest count", { inputPath: "$.second", resultPath: "$.first" });

    const plan = new LambdaInvoke(this, "Plan cleanup", {
      lambdaFunction: planCleanup,
      payload: TaskInput.fromObject({ repository: props.repositoryName }),
      payloadResponseOnly: true,
      resultPath: "$.cleanup",
    });
    const askForApproval = new LambdaInvoke(this, "Ask for approval", {
      lambdaFunction: requestApproval,
      integrationPattern: IntegrationPattern.WAIT_FOR_TASK_TOKEN,
      payload: TaskInput.fromObject({ taskToken: JsonPath.taskToken, plan: JsonPath.objectAt("$.cleanup") }),
      resultPath: "$.decision",
    });
    const audit = new DynamoPutItem(this, "Record decision", {
      table: auditLog,
      item: {
        runId: DynamoAttributeValue.fromString(JsonPath.executionName),
        step: DynamoAttributeValue.fromString("decision"),
        approved: DynamoAttributeValue.booleanFromJsonPath(JsonPath.stringAt("$.decision.approved")),
        plan: DynamoAttributeValue.fromString(JsonPath.jsonToString(JsonPath.objectAt("$.cleanup.plan"))),
      },
      resultPath: JsonPath.DISCARD,
    });
    const remove = new LambdaInvoke(this, "Delete old images", {
      lambdaFunction: deleteImages,
      payload: TaskInput.fromObject({ plan: JsonPath.objectAt("$.cleanup") }),
      payloadResponseOnly: true,
      resultPath: "$.deletion",
    });
    const report = new SnsPublish(this, "Report", {
      topic,
      subject: `Cleanup of ${props.repositoryName} done`,
      message: TaskInput.fromJsonPathAt("$.deletion.summary"),
    });

    const definition = firstCheck.next(
      new Choice(this, "Scan ready?")
        .when(Condition.booleanEquals("$.first.ready", false), waitForScan.next(firstCheck))
        .otherwise(
          waitBeforeRecount.next(secondCheck).next(
            new Choice(this, "Count stable?")
              .when(
                Condition.numberEqualsJsonPath("$.second.count", "$.first.count"),
                plan.next(
                  new Choice(this, "Anything to delete?")
                    .when(Condition.booleanEquals("$.cleanup.empty", true), new Succeed(this, "Nothing to delete"))
                    .otherwise(
                      askForApproval.next(audit).next(
                        new Choice(this, "Approved?")
                          .when(Condition.booleanEquals("$.decision.approved", true), remove.next(report))
                          .otherwise(new Succeed(this, "Rejected")),
                      ),
                    ),
                ),
              )
              .otherwise(keepLatestCount.next(waitBeforeRecount)),
          ),
        ),
    );

    const stateMachine = new StateMachine(this, "Workflow", {
      definitionBody: DefinitionBody.fromChainable(definition),
      // An unanswered approval request expires after a week.
      timeout: Duration.days(7),
    });
    stateMachine.grantTaskResponse(approvalPage);

    // Every successful push of the protected tag starts a run.
    new Rule(this, "LatestPushed", {
      eventPattern: {
        source: ["aws.ecr"],
        detailType: ["ECR Image Action"],
        detail: {
          "action-type": ["PUSH"],
          result: ["SUCCESS"],
          "repository-name": [props.repositoryName],
          "image-tag": ["latest"],
        },
      },
      targets: [new SfnStateMachine(stateMachine)],
    });

    new CfnOutput(this, "WorkflowArn", { value: stateMachine.stateMachineArn });

    // --- CI: GitHub Actions pushes images without stored AWS keys (OIDC) ---

    const github = new OidcProviderNative(this, "GitHubOidc", {
      url: "https://token.actions.githubusercontent.com",
      clientIds: ["sts.amazonaws.com"],
    });
    const pushRole = new Role(this, "GitHubPushRole", {
      description: `GitHub Actions on ${props.githubRepository}@main pushes ${props.repositoryName} images`,
      maxSessionDuration: Duration.hours(1),
      assumedBy: new WebIdentityPrincipal(github.oidcProviderArn, {
        StringEquals: {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          // Only workflow runs on the main branch of this repository, never forks or pull requests.
          "token.actions.githubusercontent.com:sub": `repo:${props.githubRepository}:ref:refs/heads/main`,
        },
      }),
    });
    repository.grantPullPush(pushRole);

    new CfnOutput(this, "GitHubPushRoleArn", { value: pushRole.roleArn });
  }

  private pythonFunction(id: string, handler: string, environment?: Record<string, string>): Function {
    return new Function(this, id, {
      runtime: Runtime.PYTHON_3_13,
      handler: `remediation_agent.handlers.${handler}`,
      code: Code.fromAsset(AGENT_SOURCE, { exclude: ["**/__pycache__"] }),
      timeout: Duration.minutes(1),
      memorySize: 256,
      environment,
      logGroup: new LogGroup(this, `${id}Logs`, {
        retention: RetentionDays.ONE_WEEK,
        removalPolicy: RemovalPolicy.DESTROY,
      }),
    });
  }
}
