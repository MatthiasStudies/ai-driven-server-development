# tcg-card-stack
A TCG card collection management server.

- FastAPI backend
- Datamodell can be found in `postgres-data/init.sql`.
- It should be possible to create a new `Card`, a new `Binder` and add a grading certificate to an existing card
- Cards and binders must be accessible via a GET request and maybe edited using PUT
- Every API request must be validated (e.g. with Pydantic)
- ruff should be used for formatting / static analysis
- ty should be used for typechecking
- SQLAlchemy for DB access
- A running postgres DB can be found at `localhost:5432` with the following credentials:
  - user: `tcg_user`
  - password: `tcg_password`
  - database: `tcg_tracker`
- When retrieving cards/binders, filter/ordering operators may be added
- Tests are written in pytest (integration tests; unit tests if possible)
- Commit early, commit often
- Add a bruno collection for easy testing/demonstration
- Add a Makefile for common macros