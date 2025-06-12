# Allow `from client.xxx` imports to work even when the working directory is the
# `client/` folder itself (e.g. when running `pytest` there). This appends the
# project root to `sys.path` exactly once.

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.append(str(_root))
