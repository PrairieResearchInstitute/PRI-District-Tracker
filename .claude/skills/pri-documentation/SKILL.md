---
name: pri-documentation
description: Use after any change to a PRI project's components, workflows, database schema, API endpoints or data, and when the user asks for documentation or a README.
---

# PRI documentation

Every shared system keeps five documents, and you update them with each change:

1. `README.md`: what the system does, who it is for, how to run it from a fresh clone.
2. `docs/architecture.md`: components, how they connect and the main workflows. One page. Keep the Mermaid diagram current.
3. `docs/schema.md`: every table and field and its meaning. Regenerate from the database; keep `COMMENT ON` statements in the schema current.
4. `docs/api.md`: every endpoint, what it takes and returns, and how it reads from or writes to the database. FastAPI also generates `/api/docs`.
5. `data-sources.yaml`: inputs, owned records and outputs.

Write for a colleague who has never seen the project. Plain language, short
sentences. When you finish a change, tell the user which documents you updated.
