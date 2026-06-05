from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def send(proc: subprocess.Popen, request: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    return json.loads(proc.stdout.readline())


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "memory.sqlite"
        proc = subprocess.Popen(
            [sys.executable, "-m", "zerker_memory", "--db", str(db), "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            print(send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
            print(send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
            print(
                send(
                    proc,
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "memory.remember",
                            "arguments": {
                                "content": "Production deploys require approval",
                                "type": "policy",
                                "scope": "project",
                            },
                        },
                    },
                )
            )
        finally:
            proc.terminate()
            proc.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
