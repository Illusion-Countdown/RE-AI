"""RUNTIME 4.0 demo 启动入口。"""

from __future__ import annotations

try:
    from app import App
except ModuleNotFoundError as exc:
    if exc.name == "pygame":
        raise SystemExit(
            "未找到 pygame。请用虚拟环境运行：\n"
            "  D:\\Pygame\\.venv\\Scripts\\python.exe D:\\Pygame\\RE-AI-demo\\main.py"
        ) from exc
    raise


if __name__ == "__main__":
    App().loop()
