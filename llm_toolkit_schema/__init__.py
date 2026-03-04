from __future__ import annotations

import warnings

warnings.warn(
    "llm_toolkit_schema has been renamed to tracium. "
    "Please update your imports: `from tracium import ...`. "
    "The llm_toolkit_schema name will be removed in a future release.",
    DeprecationWarning,
    stacklevel=2,
)

from tracium import *  # noqa: F401 F403
from tracium import __all__, __version__  # noqa: F401
