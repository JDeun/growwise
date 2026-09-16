"""Minimal PyInstaller entry point for the authenticated GrowWise desktop Core sidecar."""

from growwise.api.secure_entry import run

if __name__ == "__main__":
    run()
