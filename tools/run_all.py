# -*- coding: utf-8 -*-
"""一键回归：所有无头测试串行执行，任一失败立即返回非零。"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = [
    "architecture_test.py",
    "events_test.py",
    "feedback_test.py",
    "mechanics_test.py",
    "rooms_test.py",
    "flow_test.py",
    "tutorial_test.py",
    "screens_test.py",
    "drag_test.py",
    "tool_test.py",
    "audio_test.py",
]


def main():
    env = dict(os.environ)
    env["SDL_VIDEODRIVER"] = "dummy"
    env["SDL_AUDIODRIVER"] = "dummy"
    env["PYTHONIOENCODING"] = "utf-8"
    failed = []
    for name in TESTS:
        path = ROOT / "tools" / name
        if not path.exists():
            print(f"[missing] {name}")
            failed.append(name)
            continue
        print(f"\n=== {name} ===", flush=True)
        proc = subprocess.run([sys.executable, str(path)],
                              cwd=str(ROOT), env=env)
        if proc.returncode != 0:
            failed.append(name)
            print(f"[FAIL] {name}", flush=True)
        else:
            print(f"[ok] {name}", flush=True)
    if failed:
        print("\nFAILED:", ", ".join(failed))
        return 1
    print("\nALL TESTS OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
