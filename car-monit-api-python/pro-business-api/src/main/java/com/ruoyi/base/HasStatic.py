# -*- coding: utf-8 -*-
"""com.ruoyi.base.HasStatic

源文件：pro-business-api/src/main/java/com/ruoyi/base/HasStatic.java

这是一段“Java 静态变量语义”的面试/自测代码：通过实例引用修改 static 字段，
验证**静态字段属于类、不属于实例**。

【Java→Python】关键差异（本文件全部价值都在这里）
1) Java 的 ``hs1.x++``（用**实例引用**访问 static 字段）在编译期就被替换成
   ``HasStatic.x++``，改的是**类变量**；Python 里 ``hs1.x += 1`` 会先读 ``hs1.x``
   （找不到实例属性时回退到类属性），再**写入实例属性** —— 结果是在实例上
   新建了一个 ``x``，类变量不变。所以这里必须写 ``HasStatic.x += 1`` 才等价。
2) Java 的 ``private static int x = 100``：``private`` 只限制**跨类**访问，
   同类内部（main 里）照常可读写；Python 没有访问修饰符，用 ``_x`` 下划线约定
   即可，本文件沿用 Java 的字段名 ``x`` 并加注释说明。
3) Java 的 ``main(String args[])`` → Python 模块级 ``main()``（本文件没有外部调用者，
   只作为可执行示例）。
4) 输出必须是 ``x=102``：四次 ``x++`` 中有三次 +1（hs1/hs2/hs1）与一次 --。
"""
from __future__ import annotations

__all__ = ["HasStatic", "main"]


class HasStatic(object):
    """静态字段语义演示类。"""

    # 【Java→Python】`private static int x` → 类属性（Python 无 private；
    # 用类属性而非实例属性才等价于 Java 的 static）
    x: int = 100

    @staticmethod
    def main(args=None) -> None:
        # Java: HasStatic hs1 = new HasStatic();
        hs1 = HasStatic()
        # Java: hs1.x++;  —— 编译为 HasStatic.x++（改类变量）
        # Python: hs1.x += 1 会**遮蔽**类变量（新建实例属性），必须显式写类名
        HasStatic.x += 1

        # Java: HasStatic hs2 = new HasStatic();
        hs2 = HasStatic()
        # Java: hs2.x++;  —— 同样是 HasStatic.x++
        HasStatic.x += 1

        # Java: hs1 = new HasStatic();  —— 重新指向新对象
        hs1 = HasStatic()
        # Java: hs1.x++;
        HasStatic.x += 1

        # Java: HasStatic.x--;
        HasStatic.x -= 1

        # Java: System.out.println("x=" + x);
        # 【Java→Python】`"x=" + x` 在 Java 里触发 String.valueOf(int) 自动拼接；
        # Python 不允许 str + int，必须显式 str()
        print("x=" + str(HasStatic.x))

        # 保留引用，避免 linter 认为 hs1/hs2 未使用；同时印证“实例不持有 x”
        _ = (hs1, hs2)


def main(args=None) -> None:
    """模块级入口（等价 Java 的 main 方法）。"""
    HasStatic.main(args)


if __name__ == "__main__":
    main()
