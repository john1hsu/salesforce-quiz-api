#!/usr/bin/env python3
import os

import aws_cdk as cdk
from stack import QuizApiStack

app = cdk.App()
env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("AWS_REGION", os.environ.get("CDK_DEFAULT_REGION", "us-east-1")),
)
for stage in ("staging", "prod"):
    stack = QuizApiStack(app, f"SalesforceQuizApi-{stage}", stage=stage, env=env)
    cdk.Tags.of(stack).add("project", "salesforce-quiz-api")
    cdk.Tags.of(stack).add("stage", stage)
app.synth()
