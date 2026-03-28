import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from rejeki.server import mcp  # noqa: F401 — re-exported for Horizon entrypoint
