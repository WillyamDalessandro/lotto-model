# Local development

Phase 1 supplies database infrastructure and contracts. Historical collection starts in phase 2; the database is initially empty. Migrations create tables but do not seed unverified rules or results.

## Windows setup

Prerequisites: Git, Docker Desktop with a running Linux-container engine, and uv. If uv is absent, install it with `python -m pip install uv`; use `python -m uv` in place of `uv` if Scripts is not on PATH. Python 3.12 is managed by uv independently of system Python.

```powershell
Copy-Item .env.example .env
# Edit .env: replace BOTH passwords with distinct random URL-safe strings.
# Update each URL to match its password; do not commit this file.
uv sync --locked
docker compose config --quiet
docker compose up -d --wait db
uv run lotto db migrate
uv run lotto db health
uv run lotto --help
```

Research PostgreSQL uses localhost port 5433; tests use 5434. Both are configurable in .env, including the corresponding URLs. The pinned image is PostgreSQL 18.6. It mounts `/var/lib/postgresql`, the parent directory used by the [PostgreSQL 18 Docker image](https://hub.docker.com/_/postgres).

If uv reports a broken Windows minor-version link after downloading Python, find the installed executable with `uv python dir` and create the environment with `uv sync --python <absolute-path-to-python.exe>`. Subsequent runs use .venv. This workstation was verified using the explicit Python 3.12.15 executable.

## Tests and checks

```powershell
docker compose --profile test up -d --wait
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
git diff --check
```

Integration tests are mandatory and fail if LOTTO_TEST_DATABASE_URL is missing. They upgrade the isolated database to the latest schema, rerun the migration, verify constraints and roll back synthetic rows. They reject database names that do not end in `_test`. Use a dedicated test server/user as shown in Compose, never a URL pointing at research data. Run CI with its own ephemeral PostgreSQL service.

Runtime dependencies are installed by default. `uv sync --locked --extra research` additionally installs the notebook and modelling tools when those phases begin.

## Storage, shutdown and credentials

Named volumes `lotto-model_postgres-data` and `lotto-model_postgres-test-data` persist through restarts and `docker compose down`. Stop services with `docker compose --profile test stop`; start them again with the commands above. Do not use `down -v` as a routine reset. The image reads initial user/password settings only on first initialisation; editing .env does not change an existing database password.

Raw source evidence will live under data/raw with hashes referenced by the database. Back up both the database and raw files once collection begins. `.env`, data, artefacts and local caches are ignored by Git. Database URLs remain masked in settings representations and CLI failures print sanitised messages.

## Backup and restore verification

Use PostgreSQL's custom dump format. Write the binary file inside the container and copy it to the host; avoid PowerShell binary redirection.

```powershell
New-Item -ItemType Directory -Force data/backups | Out-Null
docker compose exec -T db pg_dump -U lotto -d lotto -Fc -f /tmp/lotto.dump
docker compose cp db:/tmp/lotto.dump data/backups/lotto.dump
```

Restore into a NEW database on the isolated test server, never over the research database. The destination below must not already exist. Keep the archive private because it may contain collected records.

```powershell
docker compose --profile test up -d --wait db-test
docker compose cp data/backups/lotto.dump db-test:/tmp/lotto-restore.dump
docker compose exec -T db-test createdb -U lotto_test lotto_restore_test
docker compose exec -T db-test pg_restore -U lotto_test -d lotto_restore_test --no-owner --no-acl --exit-on-error /tmp/lotto-restore.dump
docker compose exec -T db-test psql -U lotto_test -d lotto_restore_test -c "SELECT version_num FROM alembic_version;"
```

Compare table counts and raw-artifact references with the source before treating the backup as usable. Phase 1 verification demonstrated a synthetic marker surviving a service restart and a dump/restore round trip in the isolated test server. No lottery results were used for that check.

## Schema responsibilities

Tables cover sources, ingestion runs, raw artifacts, observations, games, rule regimes, draws, numbers and prizes. Unique keys and foreign keys protect identity and game/rule linkage; monetary and winner-count constraints reject negatives. DrawInput validates six distinct in-pool mains and a distinct bonus. Application contracts must be used by phase 2's ingestion transaction to enforce counts and effective rule dates before accepting a draw. Direct SQL can store incomplete pending draws; the database alone does not enforce complete draw cardinality or temporal eligibility.

Accepted draws require an observation reference. Missing prize values remain null; corrections will append observations and explicitly reconcile them during ingestion. The CLI migration command requires an editable source checkout with its migrations directory.
