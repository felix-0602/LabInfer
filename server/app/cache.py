import hashlib
import json
from pathlib import Path

from .config import DEMO_CACHE_DIR, RUNTIME_CACHE_DIR


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
        return runtime_cache_get(kind, key)
    return json.loads(p.read_text(encoding="utf-8"))


def cache_put(kind: str, key: str, payload: dict) -> None:
    p = cache_path(kind, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---- 演示缓存白名单（docs 见 server/README.md 环境变量一节） ----
# 只有 manifest 登记的图片（design/assets/ 下的演示图）的识别结果才烘焙进
# 入库的 demo_cache；其余识别写不入库的 runtime_cache。读取两处都查。

_demo_digests: set[str] | None = None


def demo_whitelist() -> set[str]:
    global _demo_digests
    if _demo_digests is None:
        digests: set[str] = set()
        manifest = DEMO_CACHE_DIR / "manifest.json"
        if manifest.exists():
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except ValueError:
                data = {}
            for rel in data.get("images", []):
                p = (DEMO_CACHE_DIR / rel)
                if p.exists():
                    digests.add(sha256_file(p))
        _demo_digests = digests
    return _demo_digests


def is_demo_image(digest: str) -> bool:
    return digest in demo_whitelist()


def runtime_cache_path(kind: str, key: str) -> Path:
    return RUNTIME_CACHE_DIR / kind / f"{key}.json"


def runtime_cache_get(kind: str, key: str) -> dict | None:
    p = runtime_cache_path(kind, key)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def runtime_cache_put(kind: str, key: str, payload: dict) -> None:
    p = runtime_cache_path(kind, key)
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
