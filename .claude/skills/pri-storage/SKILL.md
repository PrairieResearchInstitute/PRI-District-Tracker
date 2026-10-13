---
name: pri-storage
description: Use when a PRI project reads or writes files, images, rasters, PDFs or large datasets, or uses S3, Taiga or object storage.
---

# PRI storage

- Files belong in storage, not in the database. The database holds paths and metadata.
- In this template, storage is `/data` inside the containers, mapped to `./data` locally. In production, Taiga is mounted at `/data`.
- Taiga can also expose data as a native S3 object store. When code needs object storage, write it against the S3 interface with `boto3`, reading the endpoint, bucket and keys from environment variables. The same code then runs on Taiga, AWS S3 or Google Cloud Storage.
- Never hardcode a bucket key or endpoint. Add the variable names to `.env.example`.
- `data/` is in `.gitignore`. Never commit data files, real or large.
- Large transfers into or out of Taiga use Globus. Point the user to it instead of writing custom copy scripts.
