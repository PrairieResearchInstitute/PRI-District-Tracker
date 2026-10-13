---
name: pri-architecture
description: Use when starting a PRI project, adding a feature, choosing a technology or deciding where code belongs. Covers the four layers (frontend, API, database, compute), the default stack and why Electron desktop apps are prototypes only.
---

# PRI architecture

Every PRI system has four layers, each in its own folder and container:

| Layer | Folder | Rule |
|:---|:---|:---|
| Frontend | `frontend/` | Web page. Talks only to the API. |
| API | `api/` | FastAPI. Holds the logic and authorization. Only layer that talks to the database. |
| Database | `db/` | Postgres for several users. SQLite or DuckDB for one user. |
| Compute | `compute/` | Background jobs: pipelines, ingestion, calibration, ML, scientific code. |

They run on a platform: a Radiant VM with Taiga storage mounted at `/data`.
Commercial cloud (AWS, Google Cloud) is for special projects only.

## Why the API seam matters

With the API in the middle, each layer can be replaced alone. A different
frontend, a notebook or a script can use the same API. The database can move
from SQLite to Postgres, or to a managed service, by changing `DATABASE_URL`.
Never let the frontend or the compute code open a database connection.

## Electron and desktop apps

Do not build Electron or other desktop apps by default. They are acceptable
only for a throwaway prototype the user explicitly asks for. If you build one,
tell the user it cannot be shared as is, because it:

- ships its own Chromium, which falls behind on security patches
- needs code signing, notarization and installation on every machine
- exposes any credential inside the installer
- keeps data on the local disk, with no backup or access control

Even in a prototype, keep the API separate from the interface so the work
survives the move to a web app.

## When adding something

Before writing code, decide which layer it belongs in. If it runs longer
than a second or two, it belongs in compute. If it touches the database, it
goes through the API. If it stores a file, the file goes to `/data`.
