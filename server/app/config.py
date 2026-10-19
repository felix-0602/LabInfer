import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("LABINFER_DATA", BASE_DIR / "data"))
DEMO_CACHE_DIR = Path(os.environ.get("LABINFER_DEMO_CACHE", BASE_DIR / "demo_cache"))
RUNTIME_CACHE_DIR = Path(os.environ.get("LABINFER_RUNTIME_CACHE", BASE_DIR / "data" / "runtime_cache"))
CONTRACT_VERSION = "0.8.0"


class Settings:
    glm_base_url = os.environ.get("LABINFER_GLM_BASE_URL", "")
    glm_api_key = os.environ.get("LABINFER_GLM_API_KEY", "")
    llm_model = os.environ.get("LABINFER_LLM_MODEL", "glm-5.3")
    vlm_model = os.environ.get("LABINFER_VLM_MODEL", "glm-5.3-flash")


settings = Settings()
