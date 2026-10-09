import csv
import io
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from lotto_model.ingestion.contracts import Observation, validate_source_url
from lotto_model.ingestion.evidence import EvidenceStore
from lotto_model.ingestion.parsers import parse_archive, parse_detail, parse_operator
from lotto_model.ingestion.repository import Repository


def parse_csv(body, url):
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig")))
    required = {"date", *(f"n{i}" for i in range(1, 7))}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Expected date,n1..n6 CSV columns")
    rows = []
    for record in reader:
        if None in record or any(v is None for v in record.values()):
            raise ValueError("Truncated or extra CSV fields")
        winners = record.get("jackpotWinners", "").strip()
        if winners and int(winners) < 0:
            raise ValueError("Negative jackpot winner count")
        rows.append(
            Observation(
                draw_date=record["date"],
                mains=[int(record[f"n{i}"]) for i in range(1, 7)],
                bonus=int(record["bonus"]) if record.get("bonus") else None,
                source_url=url,
                jackpot=record.get("jackpot") or None,
                currency=record.get("currency") or None,
                outcome=("Won" if int(winners) > 0 else "Roll") if winners else None,
            )
        )
    if not rows:
        raise ValueError("No CSV records")
    return rows


def parse_saved(body, url, adapter):
    validate_source_url(url)
    if adapter == "csv":
        return parse_csv(body, url)
    if adapter == "observations":
        data = json.loads(body)
        rows = [Observation.model_validate(r) for r in data["observations"]]
        if not rows:
            raise ValueError("No observation records")
        if any(
            urlparse(r.source_url).hostname != urlparse(url).hostname
            or (urlparse(url).scheme == "file" and r.source_url != url)
            for r in rows
        ):
            raise ValueError("Observation source differs from artifact host")
        return rows
    if adapter == "auto":
        host = urlparse(url).hostname
        if host == "www.lottery.ie":
            if urlparse(url).path != "/draw-games/results/view" or parse_qs(
                urlparse(url).query
            ).get("game") != ["lotto"]:
                raise ValueError("Unsupported operator game/path")
            return parse_operator(body, url)
        if host == "irish.national-lottery.com":
            if not re.fullmatch(
                r"/irish-lotto/results-(?:archive-\d{4}|\d{2}-\d{2}-\d{4})",
                urlparse(url).path,
            ):
                raise ValueError("Unsupported archive path")
            return (
                parse_archive(body, url)
                if "results-archive-" in url
                else [parse_detail(body, url)]
            )
        if host == "www.irishlottery.com":
            if not re.fullmatch(
                r"/(?:results/irish-lotto-)?results?-\d{2}-\d{2}-\d{4}",
                urlparse(url).path,
            ):
                raise ValueError("Unsupported detail path")
            return [parse_detail(body, url)]
        raise ValueError("Unsupported source adapter; use an explicit CSV import")
    raise ValueError("Unsupported adapter")


def import_manifest(engine, manifest: Path, store: EvidenceStore, adapter="auto"):
    if adapter not in ("auto", "csv", "observations"):
        raise ValueError("Unsupported adapter")
    artifacts = store.load_manifest(manifest)
    # Validate all bytes and source records before opening the write transaction.
    parsed = []
    for artifact in artifacts:
        if artifact.status != "valid":
            parsed.append((artifact, []))
            continue
        parsed.append(
            (
                artifact,
                parse_saved(
                    store.read(artifact, manifest.parent), artifact.final_url, adapter
                ),
            )
        )
    counts = Counter()
    with engine.begin() as conn:
        run = Repository(conn).start_run(
            {"manifest": str(manifest), "adapter": adapter}
        )
    try:
        for artifact, rows in parsed:
            artifact = store.write(
                store.read(artifact, manifest.parent),
                **artifact.model_dump(exclude={"sha256", "body_path"}),
            )
            # One artifact is atomic; committed prior pages survive interruption.
            with engine.begin() as conn:
                repo = Repository(conn)
                identifier = repo.record_artifact(
                    artifact,
                    run,
                    "import:" + str(urlparse(artifact.url).hostname),
                    "manual",
                    evidence_root=store.root,
                )
                if artifact.status != "valid":
                    counts[artifact.status] += 1
                for row in rows:
                    counts[repo.ingest(row, identifier)] += 1
                repo.checkpoint(
                    artifact, identifier, run, "parsed" if rows else artifact.status
                )
        with engine.begin() as conn:
            Repository(conn).finish_run(run, "completed", json.dumps(counts))
    except Exception:
        with engine.begin() as conn:
            Repository(conn).finish_run(
                run, "failed", "Import failed; inspect preserved artifact checkpoints"
            )
        raise
    return dict(counts)
