import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from .config import DATA_DIR


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


_ID_PREFIX = {"datasets": "ds", "contexts": "ctx", "analyses": "an",
              "findings": "f", "uploads": "up"}


class Store:
    """JSON 文件存储。单用户场景：无锁，原子写（tmp + os.replace）。"""

    def __init__(self, root: Path = DATA_DIR):
        self.root = Path(root)
        for sub in ("datasets", "contexts", "analyses", "findings", "uploads"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _path(self, kind: str, id: str) -> Path:
        if "/" in id or ".." in id:
            raise ValueError(f"非法 id: {id!r}")
        return self.root / kind / f"{id}.json"

    def _write_atomic(self, path: Path, data: dict) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def put(self, kind: str, data: dict, id: str | None = None) -> dict:
        data["id"] = id or data.get("id") or new_id(_ID_PREFIX.get(kind, "obj"))
        self._write_atomic(self._path(kind, data["id"]), data)
        return data

    def get(self, kind: str, id: str) -> dict | None:
        p = self._path(kind, id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    # 便捷方法
    def put_dataset(self, ds: dict) -> dict:
        return self.put("datasets", ds)

    def get_dataset(self, id: str) -> dict | None:
        return self.get("datasets", id)

    def put_context(self, ctx: dict) -> dict:
        return self.put("contexts", ctx)

    def get_context(self, id: str) -> dict | None:
        return self.get("contexts", id)

    def put_analysis(self, ctx_id: str, result: dict) -> dict:
        self._write_atomic(self._path("analyses", ctx_id), result)
        return result

    def get_analysis(self, ctx_id: str) -> dict | None:
        return self.get("analyses", ctx_id)

    def put_findings(self, ctx_id: str, findings: list[dict]) -> list[dict]:
        self._write_atomic(self._path("findings", ctx_id), findings)
        return findings

    def get_findings(self, ctx_id: str) -> list[dict] | None:
        return self.get("findings", ctx_id)

    def save_upload(self, data: bytes, suffix: str = "") -> Path:
        p = self.root / "uploads" / f"{uuid.uuid4().hex}{suffix}"
        p.write_bytes(data)
        return p


store = Store()
