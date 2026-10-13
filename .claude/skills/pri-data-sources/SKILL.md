---
name: pri-data-sources
description: Use when a PRI project reads data from somewhere, creates records, produces outputs, copies a spreadsheet or dataset, or when data-sources.yaml needs updating.
---

# PRI sources of truth

`data-sources.yaml` at the repository root declares what the project depends
on and what it is responsible for. Keep it current with every change.

Three sections:

- **inputs:** data the project reads but does not own. For each: name, location, owner, access (with the credential's environment variable name, never its value), how often it changes, and mode (read live, or a copy and how it is refreshed).
- **owned:** data created here that exists nowhere else. These must be backed up.
- **outputs:** files or records the project produces, and what produces them.

## Silent copying

Do not quietly copy a spreadsheet, CSV or someone else's table into this
project's database. If a copy is really needed, say so to the user, record it
under inputs with how it is refreshed, and state that the original stays
authoritative. Prefer reading the source live.
