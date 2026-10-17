import hashlib
import json
from pathlib import Path

from .config import DEMO_CACHE_DIR


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def cache_path(kind: str, key: str) -> Path:
    return DEMO_CACHE_DIR / kind / f"{key}.json"


def cache_get(kind: str, key: str) -> dict | None:
    p = cache_path(kind, key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def cache_put(kind: str, key: str, payload: dict) -> None:
    p = cache_path(kind, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def cached_call(kind: str, key: str, fn):
    """演示缓存：命中返回缓存副本，未命中执行 fn 并可回填（bake 脚本用）。"""
    hit = cache_get(kind, key)
    if hit is not None:
        out = json.loads(json.dumps(hit))
        if isinstance(out, dict):
            out["cached"] = True
        return out
    return fn()
