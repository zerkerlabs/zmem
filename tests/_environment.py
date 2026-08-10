import atexit
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional


_TEST_STATE_DIR: Optional[Path] = None


def ensure_test_environment() -> None:
    global _TEST_STATE_DIR
    if os.environ.get("ZMEM_WORKSPACE_REGISTRY"):
        return
    _TEST_STATE_DIR = Path(tempfile.mkdtemp(prefix="zmem-test-state-"))
    os.environ["ZMEM_WORKSPACE_REGISTRY"] = str(_TEST_STATE_DIR / "workspaces.json")
    atexit.register(shutil.rmtree, _TEST_STATE_DIR, True)
