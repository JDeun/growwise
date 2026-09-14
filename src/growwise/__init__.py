"""GrowWise application core."""

import os

# LangGraph recommends strict msgpack for persisted checkpoints. Set this before any
# checkpoint serializer is imported so compromised local checkpoint data cannot request
# arbitrary Python module reconstruction.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

__version__ = "0.1.0a0"
