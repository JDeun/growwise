from __future__ import annotations

import threading

# Background-only serialization. Interactive chat/search calls intentionally do not acquire this
# lock; they should not be forced behind a long photo or material generation job. Photo analysis,
# observation enrichment, and material enhancement do acquire it so consumer GPUs/unified memory
# are not saturated by multiple slow background generations at once.
BACKGROUND_AI_LOCK = threading.Lock()
