#!/usr/bin/env python3
"""Issue a community API key and attach it to the stage's usage plan.

  python3 scripts/issue_key.py --stage prod --name "my-quiz-app" --issue 12

Run it with your own AWS credentials (the CI deploy role cannot create keys). Send the printed key to the
requester privately (for example by email), never in the public issue.
"""
from __future__ import annotations

import argparse
import sys

import boto3


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=["staging", "prod"], default="prod")
    p.add_argument("--name", required=True, help="App name from the request issue")
    p.add_argument("--issue", required=True, help="GitHub issue number, recorded on the key")
    args = p.parse_args()

    cfn = boto3.client("cloudformation")
    outputs = cfn.describe_stacks(StackName=f"SalesforceQuizApi-{args.stage}")["Stacks"][0]["Outputs"]
    plan_id = next(o["OutputValue"] for o in outputs if o["OutputKey"] == "UsagePlanId")

    apigw = boto3.client("apigateway")
    key = apigw.create_api_key(
        name=f"{args.stage}-{args.name}"[:128],
        description=f"Community key, GitHub issue #{args.issue}",
        enabled=True,
        tags={"issue": str(args.issue), "project": "salesforce-quiz-api"},
    )
    apigw.create_usage_plan_key(usagePlanId=plan_id, keyId=key["id"], keyType="API_KEY")
    print(f"key id: {key['id']}")
    print(f"key value: {key['value']}")
    print("To revoke: aws apigateway update-api-key --api-key", key["id"],
          "--patch-operations op=replace,path=/enabled,value=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
