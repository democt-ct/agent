"""兼容层 -- 所有 import 自动转发到 src.tools.db 包.

过渡期保留,后续可直接删除此文件并把调用方 import 改为 from src.tools.db import ....
"""

from src.tools.db import *  # noqa: F401, F403
