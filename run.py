# -*- coding: utf-8 -*-
"""启动《悬垂：内存远征》DANGLING RUN。

    python run.py            全屏
    python run.py --windowed 窗口
    python run.py --shots    无头生成截图
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_run.app import main

if __name__ == "__main__":
    main()
