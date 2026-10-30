# -*- coding: utf-8 -*-
"""com.ruoyi.base.Test

源文件：pro-business-api/src/main/java/com/ruoyi/base/Test.java

这是一段“Java 字符串常量池 + intern”的自测代码：
    String s1 = "Hello";              // 常量池对象
    String s2 = new String("Hello");  // 堆上新对象
    String s3 = s2.intern();          // 返回常量池中的那个对象
    s1 == s2  → false（引用不同）
    s1 == s3  → true （同一引用）

【Java→Python】关键差异（本文件全部价值都在这里）
1) Java 的 ``==`` 比较**引用**（对象地址），字符串内容比较必须用 ``equals``；
   Python 的 ``==`` 比较**值**（调用 ``__eq__``），比较引用要用 ``is``。
   因此这里的 ``s1 == s2`` 必须翻成 ``s1 is s2``，否则会得到 True（值相等）。
2) Java 的常量池是 JVM 规范行为：字面量 "Hello" 全局唯一；``intern()`` 返回池内实例。
   Python 的等价物是 ``sys.intern()``（对 str 返回驻留后的对象），
   但 Python 的驻留是**实现相关优化**（短标识符字面量在编译期自动驻留），
   语义强度弱于 Java 常量池 —— 这是最需要注意的差异。
3) ``new String("Hello")`` 在 Python 没有直接对应：``str("Hello")`` 对已存在的 str
   返回**同一个对象**（不会复制），所以必须用 ``"".join(["Hel", "lo"])`` /
   ``("Hel" + "lo")[0:]`` 之类方式造一个“等值但不同身份”的字符串；
   本文件用 ``"".join([...])`` 并在注释里标出。
4) ``System.out.println(boolean)`` → Python 的 ``print(True/False)``，
   注意 Java 输出小写 ``true``/``false``，Python 输出 ``True``/``False``
   （若必须完全一致的输出，需要 ``str(x).lower()``）。
5) ``intern()`` 是**实例方法**且影响常量池；Python 的 ``sys.intern`` 是**模块函数**。
"""
from __future__ import annotations

import sys

__all__ = ["Test", "main"]


class Test(object):
    """字符串驻留演示类。"""

    @staticmethod
    def main(args=None) -> None:
        # Java: String s1 = "Hello";
        s1 = "Hello"

        # Java: String s2 = new String("Hello");
        # 【Java→Python】Python 的 str(...) 对 str 入参直接返回同一对象，
        # 无法模拟 `new String(...)` 的“新对象但内容相同”，故用 join 造一个新 str。
        s2 = "".join(["Hel", "lo"])

        # Java: String s3 = s2.intern();
        # 【Java→Python】intern() 实例方法 → sys.intern(str) 模块函数
        s3 = sys.intern(s2)

        # Java: System.out.println(s1 == s2);   // Line 1 → false（引用不同）
        # 【Java→Python】Java 的 `==` 是引用比较 → Python 的 `is`
        print(s1 is s2)  # Line 1

        # Java: System.out.println(s1 == s3);   // Line 2 → true（都指向常量池对象）
        print(s1 is s3)  # Line 2

        # 【Java→Python】若按 Python 习惯写 `s1 == s2`，结果是 True（值比较），
        # 与 Java 输出相反 —— 这是把 Java 代码直译成 Python 时最容易踩的坑。


def main(args=None) -> None:
    """模块级入口（等价 Java 的 main 方法）。"""
    Test.main(args)


if __name__ == "__main__":
    main()
