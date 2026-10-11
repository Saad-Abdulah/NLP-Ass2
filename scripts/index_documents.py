#!/usr/bin/env python3
"""Convenience runner for the offline indexing pipeline."""
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.rag.indexer import run_indexer

if __name__ == "__main__":
    run_indexer()
