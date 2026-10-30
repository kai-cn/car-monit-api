# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.RepeatUtil

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/RepeatUtil.java

【Java→Python】整体说明
1) Java 用 ``IntStream.range(0, n).mapToObj(i -> s).collect(Collectors.joining())``
   做重复拼接；Python 的 ``s * n`` 是等价且更直接的高效写法。
2) 边界语义一致：n <= 0 时 IntStream 为空 → 返回空串；Python ``s * 0``/``s * 负数``
   同样返回空串，因此无需额外判断。
3) ``main`` 方法 → ``if __name__ == "__main__":`` 代码块（Python 没有入口方法约定）。
"""
from __future__ import annotations

from typing import Optional


class RepeatUtil:

    @staticmethod
    def repeat(s: Optional[str], n: int) -> str:
        """重复生成一个字符串。"""
        # 【Java→Python】Collectors.joining() 无分隔符 → Python 用空串乘法
        if s is None:
            # Java 中 mapToObj 返回 null 元素时 Collectors.joining 会写入 "null"
            return "null" * max(n, 0)
        return s * n


if __name__ == "__main__":
    mess = "jd_vdccfwrfeppe"
    length = len(mess)
    if length % 8 != 0:
        mess += RepeatUtil.repeat("X", 8 - length % 8)
    print(mess)
