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
