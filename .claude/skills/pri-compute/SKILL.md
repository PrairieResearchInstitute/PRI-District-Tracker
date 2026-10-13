---
name: pri-compute
description: Use when adding a pipeline, data ingestion, image processing, calibration, machine learning, a model or any long-running scientific code to a PRI project, or when a request is slow.
---

# PRI compute layer

Scientific and processing work lives in `compute/`, separate from the API.

## Pattern

1. The user starts a job through the frontend. The API records it as `pending` and returns immediately.
2. The worker (`compute/worker.py`) claims the job from the API, runs it and reports the result back to the API.
3. The frontend polls the API for status.

Never run slow work inside an API request. It stalls the app and fails on timeouts.

## Rules

- Put the science in plain functions (`compute/science.py`) with no web or database code, so it can be tested alone and moved to a bigger machine.
- Read inputs from storage and write outputs to storage (`/data`, Taiga in production). Do not write large outputs to the database.
- Report results and status through the API. Do not open a database connection from compute.
- Record what ran: code version (`CODE_VERSION`, set from `git rev-parse --short HEAD`), inputs and parameters, including random seeds. Save them with the output and in the job record.
- Package the code in a container with pinned dependencies.

## Sizing

- Light jobs: the Radiant VM that hosts the app. The VM can be resized as jobs grow.
- Heavy jobs (large calibrations, model training, big image sets): the Illinois Campus Cluster. Because the science is plain functions in a container, the same code can run there as a batch job. Help the user write the batch script and keep reporting through the API or storage.
