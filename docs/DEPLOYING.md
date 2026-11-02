# Deploying

Everything after the one-time setup is automatic: merges to `main` deploy staging, run the smoke test, then
wait for your approval before production.

## One-time setup

You need an AWS account and the AWS CLI signed in as an administrator.

1. **Bootstrap CDK** in the region you'll use (default `us-east-1`):

   ```bash
   npx aws-cdk@2 bootstrap aws://<ACCOUNT_ID>/us-east-1
   ```

2. **Create the GitHub deploy role** (OIDC, no stored AWS keys):

   ```bash
   aws cloudformation deploy --stack-name salesforce-quiz-api-github-oidc \
     --template-file infra/bootstrap/github-oidc.yaml --capabilities CAPABILITY_NAMED_IAM
   # If the account already has the GitHub OIDC provider, add:
   #   --parameter-overrides CreateOidcProvider=false
   aws cloudformation describe-stacks --stack-name salesforce-quiz-api-github-oidc \
     --query "Stacks[0].Outputs[0].OutputValue" --output text
   ```

3. **Configure the GitHub repo** (Settings):

   | Where | Name | Value |
   |---|---|---|
   | Secrets and variables → Actions → Variables | `AWS_DEPLOY_ROLE_ARN` | The role ARN from step 2 |
   | Variables (optional) | `AWS_REGION` | Defaults to `us-east-1` |
   | Environments | `staging` | No protection rules |
   | Environments | `production` | Required reviewer: you. Deployment branches: `main` only |
   | Environments | `production-data` | Deployment branches: `main` only (daily data refresh, no approval) |
   | Pages | Source | GitHub Actions |

   Until `AWS_DEPLOY_ROLE_ARN` is set, the deploy and sync jobs skip themselves, so CI stays green.

4. **Optional: weekly AI question drafts.** Add an `ANTHROPIC_API_KEY` secret and set the `GENERATE_ENABLED`
   variable to `true`. Optionally set `QUIZ_MODEL`. Drafts arrive as pull requests for your review.

5. **Branch protection** on `main` (Settings → Rules → Rulesets): require a pull request, require review from
   code owners, require the `test` and `synth` checks, block force pushes.

6. **First deploy:** Actions → Deploy → Run workflow. Copy the prod `ApiUrl` from the job summary into the
   `servers` block of `openapi/openapi.yaml` and the README.

## Issuing API keys

When someone opens an API key request issue:

```bash
python3 scripts/issue_key.py --stage prod --name "<app name>" --issue <number>
```

Send the key privately, never in the issue. To revoke, disable the key in API Gateway (the script prints the
command).

## What runs when

| Workflow | Trigger | Does |
|---|---|---|
| CI | Every PR and push | Lint, validate questions against the graph and `main` (permanent ids), build, tests, OpenAPI check, CDK synth |
| Deploy | Merge to `main` | Staging deploy + load + smoke test, then prod after approval |
| Sync | Daily | Re-validate against the latest graph; reload both stages; opens an issue if something broke |
| Draft new questions | Weekly (if enabled) | Opens a PR of AI-drafted questions for articles with none |
| Docs site | Merge to `main`, daily | Publishes docs, OpenAPI spec and bulk download to GitHub Pages |

## Costs

At community scale this sits mostly in free tiers: DynamoDB on-demand, Lambda (512 MB, ARM), API Gateway REST
(about $3.50 per million requests after the free tier), and CloudWatch logs kept 30 days. The Lambda caches the
dataset for 5 minutes, so DynamoDB reads stay tiny.
