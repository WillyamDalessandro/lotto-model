import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from lotto_model.ingestion.contracts import Artifact


class EvidenceStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest = self.root / "manifest.json"

    def write(
        self,
        body: bytes,
        *,
        url,
        http_status,
        content_type,
        status,
        final_url=None,
        retrieved_at=None,
    ):
        digest = hashlib.sha256(body).hexdigest()
        path = self.root / (digest + ".body")
        if path.exists() and path.read_bytes() != body:
            raise ValueError("Existing evidence hash mismatch")
        if not path.exists():
            path.write_bytes(body)
        artifact = Artifact(
            url=url,
            final_url=final_url or url,
            retrieved_at=retrieved_at or datetime.now(timezone.utc),
            http_status=http_status,
            content_type=content_type,
            sha256=digest,
            body_path=path.name,
            status=status,
        )
        data = (
            json.loads(self.manifest.read_text(encoding="utf8"))
            if self.manifest.exists()
            else {"version": 1, "artifacts": []}
        )
        data["artifacts"].append(artifact.model_dump(mode="json"))
        temporary = self.manifest.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf8")
        temporary.replace(self.manifest)
        return artifact

    def read(self, artifact: Artifact, root: Path | None = None):
        base = (root or self.root).resolve()
        relative = Path(artifact.body_path)
        path = (base / relative).resolve()
        if relative.is_absolute() or not path.is_relative_to(base):
            raise ValueError("Evidence path escapes manifest directory")
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != artifact.sha256:
            raise ValueError("Evidence hash mismatch")
        return body

    def load_manifest(self, path: Path) -> list[Artifact]:
        data = json.loads(path.read_text(encoding="utf8"))
        if data.get("version") != 1:
            raise ValueError("Unsupported manifest version")
        artifacts = [Artifact.model_validate(a) for a in data["artifacts"]]
        for artifact in artifacts:
            self.read(artifact, path.parent)
        return artifacts

    def cached(self, url):
        if not self.manifest.exists():
            return None
        for artifact in reversed(self.load_manifest(self.manifest)):
            if artifact.url == url and artifact.status == "valid":
                return artifact
        return None
