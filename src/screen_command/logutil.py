"""日志与耗时统计。

只记录时间与错误元信息，绝不记录截图内容或 OCR 文本（隐私要求）。
"""

from __future__ import annotations

import logging
import os
import sys
import time


def get_logger(name: str = "screen_command") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-5s %(name)s: %(message)s", "%H:%M:%S")
        )
        logger.addHandler(handler)
        logger.setLevel(os.environ.get("SC_LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger


class Timer:
    """上下文管理器：记录耗时（毫秒），供性能日志与 ActionResult.elapsed_ms 使用。"""

    def __init__(self) -> None:
        self.ms: float = 0.0

    def __enter__(self) -> "Timer":
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc) -> None:
        self.ms = (time.perf_counter() - self._t0) * 1000.0
