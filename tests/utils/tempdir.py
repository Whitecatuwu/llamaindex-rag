from contextlib import contextmanager
from pathlib import Path
import shutil
import uuid


@contextmanager
def managed_temp_dir(prefix: str, root: str = "tests/tmp"):
    base_tmp = Path(root)
    base_tmp.mkdir(parents=True, exist_ok=True)
    tmp_path = base_tmp / f"{prefix}_{uuid.uuid4().hex}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    try:
        yield tmp_path
    finally:
        try:
            shutil.rmtree(tmp_path, ignore_errors=True)
        except Exception as e:
            print(f"Error cleaning up temporary directory {tmp_path}: {e}")

