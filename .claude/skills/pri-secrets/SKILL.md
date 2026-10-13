---
name: pri-secrets
description: Use whenever code needs a password, API key, token, connection string or any credential in a PRI project, and before every commit that touches configuration.
---

# PRI credentials and secrets

AI assistants tend to paste credentials into code to make things run. Do not.

- Read every secret from an environment variable. Locally they live in `.env`, which is in `.gitignore`.
- When you add a variable, add its name with a placeholder value to `.env.example`.
- Never put a secret in the frontend, in a committed file or in a desktop app. Anything shipped to a browser or installer can be read by its user. The API holds credentials; the frontend never does.
- Give each credential the least access it needs. The app uses the `app` database role, not the admin. A read-only dashboard gets a read-only account.
- Use different credentials for development and production.
- On a Radiant VM, keep the production `.env` outside the repository, readable only by the account that runs the service. On commercial cloud, use the provider's secret manager.

## If a secret was committed

Deleting the line is not enough; it stays in Git history. Tell the user
plainly that the credential must be revoked and a new one issued, then move
the value to `.env`.

## Before committing

Check the diff for anything that looks like a key, token or password. Suggest
enabling GitHub secret scanning or running `gitleaks`.
