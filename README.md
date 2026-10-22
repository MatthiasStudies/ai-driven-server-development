# tcg-card-stack

A TCG card collection management server — binders, cards and grading
certificates. Built with **FastAPI** and **SQLAlchemy** on **PostgreSQL**.

The API serves interactive documentation out of the box:
**http://localhost:8000/docs** (Swagger UI), `/redoc` and the raw spec at
`/openapi.json`.

## Quickstart

```bash
make install   # create .env from .env.example + uv sync
make db-up     # start the PostgreSQL container
make run       # serve on http://localhost:8000
```

## Configuration

Database credentials are read from environment variables or a `.env` file
(`make env` copies `.env.example` to `.env`). The same variable names
configure the docker-compose service, so one file drives both.

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_USER` | `tcg_user` | Database user |
| `POSTGRES_PASSWORD` | `tcg_password` | Database password |
| `POSTGRES_HOST` | `localhost` | Host the app connects to |
| `POSTGRES_PORT` | `5432` | Host port (also used for the port mapping) |
| `POSTGRES_DB` | `tcg_tracker` | Database name |
| `DATABASE_URL` | – | Optional full override of the app database URL |
| `TEST_DATABASE_URL` | – | Optional full override of the test database URL |

## API overview

| Area | Endpoints |
|---|---|
| Binders | `POST/GET /binders`, `GET/PUT/DELETE /binders/{id}` |
| Cards | `POST/GET /cards`, `GET/PUT/DELETE /cards/{id}` |
| Certificates | `POST/GET /certificates`, `GET/DELETE /certificates/{id}` |
| Quicksearch | `GET /search?q=…` (fuzzy, powered by rapidfuzz) |
| Health | `GET /health` |

List endpoints support filtering (`name`, `set_name`, `rarity`, `variant`,
`grading_company`, date/grade ranges), whitelisted `order_by` + `order`, and
`limit`/`offset` pagination — see `/docs` for details.

- `PUT` endpoints are **partial updates** (omitted fields keep their values)
- Certificates are **immutable**; a card can hold at most one (`409` on conflicts)
- `DELETE /binders/{id}` cascades to cards and certificates

## Conditional requests & optimistic locking

Every read endpoint returns an `ETag` derived from the optimistic-locking
`version` counters (binder detail also covers the versions of its nested
cards). Two flows build on it:

**Conditional GET (saves bandwidth)** — send the stored ETag back and get a
`304 Not Modified` with no body when nothing changed:

```bash
curl -i -H 'If-None-Match: "card-1-v1"' http://localhost:8000/cards/1
```

Responses carry `Cache-Control: no-cache`: clients may store them but must
revalidate. `If-None-Match` uses weak comparison, so `W/"…"` validators match
too.

**Safe updates and deletes** — every `PUT`/`DELETE` on binders and cards must
send the ETag from the last GET in `If-Match`, so concurrent writers cannot
silently overwrite each other:

```bash
curl -X PUT http://localhost:8000/cards/9 \
  -H 'Content-Type: application/json' \
  -H 'If-Match: "card-9-v1"' \
  -d '{"name": "New name"}'
```

- Missing `If-Match` → `428 Precondition Required`
- Stale ETag → `412 Precondition Failed` (the detail names the current ETag)
- `If-Match: *` matches any existing resource; weak validators never match
- Recovery: re-GET the resource, merge your changes, retry
- Successful PUT responses include the new `ETag`, so requests can be chained
  without another GET
- Attaching or removing a grading certificate bumps the card's version, so the
  card's ETag changes as well

## Database schema changes

The schema lives in `postgres-data/init.sql` and is applied on first container
start only. After a schema change, reset the local volume (seed data only):

```bash
make db-reset
```

or apply the change manually, e.g. for the `version` columns:

```sql
ALTER TABLE binders ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 1;
ALTER TABLE cards   ADD COLUMN IF NOT EXISTS version INT NOT NULL DEFAULT 1;
```

## Testing

```bash
make db-up   # tests need the PostgreSQL container
make test
```

Integration tests run against a dedicated `tcg_tracker_test` database that is
recreated from `postgres-data/init.sql` once per session; every test starts
from the seed data. Set `TEST_DATABASE_URL` to point somewhere else.

## Code quality

```bash
make format      # ruff format + autofix
make lint        # ruff check + format check
make typecheck   # ty
make check       # lint + typecheck + test
```

## Continuous integration

Every pull request runs the static quality gates via GitHub Actions
(`.github/workflows/qa.yml`): `ruff check` (static analysis),
`ruff format --check` (code style) and `ty` (typechecking).

## Bruno collection

Open the `bruno/` folder in [Bruno](https://www.usebruno.com/) and pick the
`dev` environment (`baseUrl: http://localhost:8000`). The collection covers
every endpoint, including filtered list queries, the quicksearch and the
create → update → delete flow.

## Project structure

```
app/
  main.py        # FastAPI app, router registration, /health
  config.py      # settings from env vars / .env
  db.py          # engine, session factory, get_db dependency
  models.py      # SQLAlchemy models (mirrors postgres-data/init.sql)
  schemas.py     # Pydantic request/response schemas
  crud.py        # query, filter and search logic
  routers/       # binders, cards, certificates, search
tests/           # pytest integration + unit tests
bruno/           # Bruno API collection
postgres-data/   # database schema + seed data
```
