from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
for path in (str(APP_DIR), str(PROJECT_ROOT / "src")):
    if path not in sys.path:
        sys.path.insert(0, path)

from ui.main import run

run()
