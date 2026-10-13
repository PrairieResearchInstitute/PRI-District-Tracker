---
name: pri-database
description: Use when choosing a database, changing the schema, writing queries, handling several users or setting up backups in a PRI project. Explains SQLite versus Postgres, least-privilege accounts and pg_dump backups.
---

# PRI database practice

## Choosing

- **One user:** SQLite for records, DuckDB for analysis of large tables, Parquet or CSV.
- **More than one user:** Postgres. Always.

Never place a SQLite or DuckDB file on a network share (SMB, NFS, a mapped
drive) for several people. SQLite locks the whole file for each write, so at
best one person writes at a time. Over a share the lock itself is unreliable
and the file can corrupt silently. WAL mode does not work over a share. If
the user proposes this, explain it and use Postgres.

## Postgres in this template

- Runs in the `db` container. Schema in `db/init/01_schema.sql`.
- The API connects as the `app` role, created in `db/init/02_app_role.sh`, with only the grants it needs. Never connect the application as the admin account.
- When you add a table, add its grants to `02_app_role.sh` and `COMMENT ON` statements for the table and every column.
- Init scripts run only on an empty volume. For an existing database, write a numbered migration script in `db/` and tell the user how to apply it.

## Queries

- Use parameters (`%s` with psycopg). Never build SQL with string formatting.
- Use `FOR UPDATE SKIP LOCKED` when several workers take items from a queue.

## Backups

The project owns its data, so it owns its backups. `db/backup.sh` runs
`pg_dump` to `BACKUP_DIR`, which should be on Taiga. Remind the user to
schedule it with cron and to test a restore once.

## Outgrowing the container

ODSC expects to offer a managed Postgres on Radiant. Suggest the user talk to
ODSC if the app is large, has heavy queries, shares a database with other
apps or holds data whose loss would be serious. Large pipelines that need to
write many rows should also be discussed with ODSC rather than solved ad hoc.
