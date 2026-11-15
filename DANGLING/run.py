# -*- coding: utf-8 -*-
"""启动《悬垂》DANGLING。

    python run.py            全屏
    python run.py --windowed 窗口
    python run.py --room 3   直接从第 4 关开始
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dangle.app import main

if __name__ == "__main__":
    main()
