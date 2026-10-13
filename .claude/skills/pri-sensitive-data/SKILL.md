---
name: pri-sensitive-data
description: Use when a PRI project involves personnel, HR, student or personal records, restricted or controlled datasets, or when the user offers to share real data, a real file or a database dump.
---

# PRI sensitive data and AI assistants

Everything you read, including files in the project folder, is sent to the
AI provider. So real sensitive data must never reach you.

## What you do

- Do not ask for, open or load real sensitive data: personnel and HR records, personal information, or data under a data use agreement or other restriction.
- If the user offers a real file or pastes real records, stop and explain why, then ask for the structure instead: field names, types and a few invented example rows.
- Generate mock data that matches the structure, with clearly fake names and values. Use it for development and tests.
- Do not read files outside this repository. Real data belongs on Taiga, outside the project folder.
- Write the code so the user can run it against real data themselves, without you.

## When an AI model must process sensitive data

Point the user to Lumen, where files stay on Taiga, compute runs on Radiant
and models run on Lumen, all inside the university. Tell them to check with
ODSC first, because some data has restrictions beyond where it is processed.
