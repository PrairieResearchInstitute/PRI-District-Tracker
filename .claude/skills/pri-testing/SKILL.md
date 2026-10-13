---
name: pri-testing
description: Use when adding or changing API endpoints or compute code in a PRI project, before telling the user a change is done, or when something that worked before breaks.
---

# PRI testing

Keep testing light but always present.

- Add or update a test for each API endpoint and each compute function you change. A few tests are enough; aim for the main path and one failure.
- Tests use invented data only, never real records.
- API tests live in `api/tests/` and run with `docker compose run --rm api pytest`.
- Test compute functions in `compute/science.py` directly, without the worker or the API.
- Run the tests before telling the user a change is finished, and report the result. If you cannot run them, say so.
