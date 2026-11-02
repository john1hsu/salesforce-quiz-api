from __future__ import annotations

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

SRC = Path(__file__).resolve().parents[1] / "src"


class QuizApiStack(Stack):
    """One stage (staging or prod): DynamoDB table, Lambda, REST API with API keys and a usage plan."""

    def __init__(self, scope: Construct, construct_id: str, *, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        prod = stage == "prod"

        table = ddb.Table(
            self, "Questions",
            table_name=f"quiz-api-{stage}",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=ddb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=prod),
            removal_policy=RemovalPolicy.RETAIN if prod else RemovalPolicy.DESTROY,
        )

        log_group = logs.LogGroup(
            self, "ApiLogs",
            log_group_name=f"/aws/lambda/quiz-api-{stage}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        fn = lambda_.Function(
            self, "Api",
            function_name=f"quiz-api-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="quizapi.api.handler.handler",
            code=lambda_.Code.from_asset(str(SRC), exclude=["**/__pycache__", "quizapi/dataset.py"]),
            memory_size=512,
            timeout=Duration.seconds(10),
            environment={"QUIZ_TABLE": table.table_name, "CACHE_SECONDS": "300"},
            log_group=log_group,
        )
        table.grant_read_data(fn)

        api = apigw.RestApi(
            self, "RestApi",
            rest_api_name=f"salesforce-quiz-api-{stage}",
            description="Salesforce Quiz API (community)",
            deploy_options=apigw.StageOptions(
                stage_name=stage,
                throttling_rate_limit=50,
                throttling_burst_limit=100,
                metrics_enabled=True,
            ),
        )
        integration = apigw.LambdaIntegration(fn)
        v1 = api.root.add_resource("v1")
        proxy = v1.add_resource("{proxy+}")
        for resource in (v1, proxy):
            for method in ("GET", "POST"):
                resource.add_method(method, integration, api_key_required=True)
            # CORS preflight must work without a key, so it's a mock integration with no key required.
            resource.add_cors_preflight(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "X-Api-Key"],
                max_age=Duration.hours(1),
            )

        # Rejections that never reach Lambda (bad key, throttling) still need CORS headers for browsers.
        for kind in (apigw.ResponseType.DEFAULT_4_XX, apigw.ResponseType.DEFAULT_5_XX):
            api.add_gateway_response(f"Cors{kind.response_type}", type=kind,
                                     response_headers={"Access-Control-Allow-Origin": "'*'"})

        community = api.add_usage_plan(
            "CommunityPlan",
            name=f"quiz-api-{stage}-community",
            description="Default tier for community API keys",
            throttle=apigw.ThrottleSettings(rate_limit=5, burst_limit=10),
            quota=apigw.QuotaSettings(limit=5000, period=apigw.Period.DAY),
        )
        community.add_api_stage(stage=api.deployment_stage)

        # Key used only by the deploy pipeline's smoke test.
        smoke_key = api.add_api_key("SmokeTestKey", api_key_name=f"quiz-api-{stage}-smoke-test")
        community.add_api_key(smoke_key)

        CfnOutput(self, "ApiUrl", value=api.url)
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "UsagePlanId", value=community.usage_plan_id)
        CfnOutput(self, "SmokeTestKeyId", value=smoke_key.key_id)
