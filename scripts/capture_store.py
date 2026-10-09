"""Owned temporary screenshots: explicit release, session cleanup and expiry."""
import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(tempfile.gettempdir()) / ("computer-use-" + getpass.getuser()) / "captures"
TTL = 300
_workers = []


def allocate():
    ROOT.mkdir(parents=True, exist_ok=True)
    return ROOT / (uuid.uuid4().hex + ".png")


def release(path):
    target = Path(path).resolve()
    if target.parent != ROOT.resolve() or target.suffix != ".png" or len(target.stem) != 32:
        raise ValueError("Only owned temporary screenshots may be deleted")
    int(target.stem, 16)
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False


def expire_later(path, ttl=TTL):
    # A separate lightweight process survives the capture CLI exiting/crashing.
    _workers[:] = [worker for worker in _workers if worker.poll() is None]
    worker = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), str(path), str(ttl)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), close_fds=True,
        cwd=ROOT.parent,
    )
    _workers.append(worker)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("ttl", type=float)
    args = parser.parse_args()
    deadline = time.monotonic() + max(0, args.ttl)
    while Path(args.path).exists() and time.monotonic() < deadline:
        time.sleep(min(1, max(0, deadline - time.monotonic())))
    # A viewer/antivirus may still have the file open when its TTL expires.
    while Path(args.path).exists():
        try:
            release(args.path)
        except PermissionError:
            time.sleep(1)
