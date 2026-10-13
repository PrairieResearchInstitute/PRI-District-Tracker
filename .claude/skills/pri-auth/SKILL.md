---
name: pri-auth
description: Use when a PRI project needs login, user accounts, permissions, roles or access control, or when deciding who can see or change data.
---

# PRI authentication and authorization

Never build a username and password table, password reset flow or custom login.

## Authentication: who the user is

- University-only apps: campus Active Directory.
- Wider audiences, such as collaborators at other institutions: CILogon.
- Both are handled by an authenticating proxy (for example oauth2-proxy) in front of the app. The proxy passes the verified identity to the API in a header. See `api/app/auth.py`, which reads `X-Forwarded-Email`.
- The API may trust that header only if it is reachable exclusively through the proxy. Do not publish the API port.
- `DEV_USER` is a local development shortcut. It must be empty in production.
- The user needs an OIDC client registration for AD or CILogon. Tell them to ask ODSC; do not invent client IDs or secrets.

## Authorization: what the user may do

Authorization belongs in the API, never in the frontend. Check permissions in
each endpoint (as `list_jobs` filters by `submitted_by`). Hiding a button in
the page is not access control.
