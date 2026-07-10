"""pytest 根設定：把 repo 根加入 sys.path，讓 tests/ 能 import cjkfolio。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
