# Agent instructions

## Delivery workflow (per phase)

1. Work on a named feature branch; follow the phase spec and plan in `docs/superpowers/`.
2. Verify before declaring a phase complete. Start the isolated test database (`docker compose --profile test up -d --wait`), then run:
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run pytest -q`
   - `git diff --check`
   - the phase's CLI runtime checks.
3. Merge into local `main` and repeat every check on the merged state.
4. **Once the phase is complete and verified, push `main` and the phase branch to `origin` immediately** (standing authorization from the repository owner). Never push failing or unverified work.
5. Never commit or push `data/`, evidence bodies, snapshots, experiment outputs, backups or `.env`.
6. Record decisions in `docs/implementation-decisions.md` and keep the README status current.

## Environment notes

- On Windows, if `uv run` reports a broken Python minor-version link, use the existing `.venv/Scripts/python` (created with `uv sync --locked --extra research --python <path to uv's cpython-3.12.15 python.exe>`).
- Integration tests require `LOTTO_TEST_DATABASE_URL` pointing at a database whose name ends in `_test`.

## Research integrity

- Never tune parameters or select models on evaluation/holdout draws; use chronological development folds only.
- Use only permitted data sources; sites whose terms prohibit harvesting stay excluded.
- Report "no demonstrated advantage" honestly; the target is 3+ main matches, not jackpots.
