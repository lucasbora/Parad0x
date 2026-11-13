import os
import tempfile

# Hermetic tests: no network, empty cache → deterministic seed data.
os.environ["TMBG_OFFLINE"] = "1"
os.environ["TMBG_CACHE_DIR"] = tempfile.mkdtemp(prefix="tmbg-test-cache-")
