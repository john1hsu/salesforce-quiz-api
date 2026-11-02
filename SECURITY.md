# Security policy

Please report vulnerabilities privately through
[GitHub private vulnerability reporting](https://github.com/john1hsu/salesforce-quiz-api/security/advisories/new),
not in a public issue.

If you find a leaked API key, report it the same way and it will be revoked.

This repository contains no secrets: deployments use short-lived AWS credentials via GitHub OIDC, and API keys
are issued out of band.
