#!/usr/bin/env python3
"""Vendor the content pipeline into the Vercel app.

Vercel deploys `web/` as a self-contained project (Root Directory =
``web``), so the pipeline package is copied here rather than imported
across the repo boundary. Run after changing anything under
``src/content_pipeline/``:

    python web/sync_vendor.py

``tests/test_content_pipeline.py::test_vendored_copy_in_sync`` fails if
you forget, so drift can't reach CI green.
"""

import filecmp
import shutil
import sys
from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parent
REPO_ROOT = WEB_ROOT.parent
SRC = REPO_ROOT / "src" / "content_pipeline"
DEST = WEB_ROOT / "_vendor" / "content_pipeline"
CONFIG_SRC = REPO_ROOT / "content_pipeline.yaml"
CONFIG_DEST = WEB_ROOT / "content_pipeline.yaml"


def sync() -> None:
    if DEST.exists():
        shutil.rmtree(DEST)
    shutil.copytree(
        SRC, DEST, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copy2(CONFIG_SRC, CONFIG_DEST)
    print(f"Vendored {SRC} -> {DEST}")
    print(f"Copied {CONFIG_SRC.name} -> {CONFIG_DEST}")


def check() -> bool:
    """True when the vendored copy matches the source exactly."""
    if not DEST.exists() or not CONFIG_DEST.exists():
        return False
    if not filecmp.cmp(CONFIG_SRC, CONFIG_DEST, shallow=False):
        return False
    src_files = {
        p.relative_to(SRC): p
        for p in SRC.rglob("*.py")
        if "__pycache__" not in p.parts
    }
    dest_files = {
        p.relative_to(DEST): p
        for p in DEST.rglob("*.py")
        if "__pycache__" not in p.parts
    }
    if set(src_files) != set(dest_files):
        return False
    return all(
        filecmp.cmp(src_files[rel], dest_files[rel], shallow=False)
        for rel in src_files
    )


if __name__ == "__main__":
    if "--check" in sys.argv:
        if check():
            print("Vendored copy is in sync.")
        else:
            print("OUT OF SYNC — run: python web/sync_vendor.py")
            sys.exit(1)
    else:
        sync()
