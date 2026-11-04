# -*- coding: utf-8 -*-
"""给阶段 02/04/05 文档追加「后续更新」说明（幂等：已有该节则替换）。

阶段9/10 把当时记为「可接受」的容器级差异做到了逐字节一致，历史正文不改，
只在文末补一条口径更新，避免读者按旧结论理解现状。
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(ROOT, 'docs', 'verify')

MARK = '## 后续更新（阶段9/10 口径）'

NOTES = {
    '02-契约层校验.md': """
@MARK@

阶段9 把当时列为「可接受」的容器级差异做到了**逐字节一致**，本阶段的最新口径是：

- 契约层 134 例 = **126 通过 + 8 已知可接受 + 0 不一致**（数量不变）；
- 剩下的 8 例只有一类：`Accept: application/cbor` / `application/x-jackson-smile`
  时 Java 输出二进制编码（见 `09-已知差异与根因.md` 的 D2）；
- 原文 §2 表格里「Tomcat HTML 错误页 vs Spring JSON 错误体」这一行**已失效**：
  `middleware.rs::tomcat_bad_request()` 现在复刻 Tomcat 那 435 字节的容器页
  （含 en-dash、`text/html;charset=utf-8`、不看 Accept），实测两侧字节相同。
  同时钉准了一条边界：`%2f` / `%00` 的拒绝**只看 path**，query 里出现 `%2F` 不触发
  （`plateimage=http%3A%2F%2F…` 必须 200）—— 这条是改完之后跑 filters 才发现的回归。
""",

    '04-过滤矩阵校验.md': """
@MARK@

阶段9 之后本阶段的最新口径：**2349 例全部逐字节一致（0 可接受、0 不一致）**。

- 原文「最终结论」与 §4 里那 1 例「已知可接受」（`trailPoints` 超长真值 → Tomcat 400 HTML）
  现在也已做到逐字节一致，原因同上（F36）；
- 同一轮还消除了 10 例新暴露的差异：列表型参数（`cidList`/`codeList`/`sectionList`/`uuidList`）
  传纯空白时 Java 是 `IN (' ')` 过滤成 0 行，Rust 曾按「空值不传」处理成整表（F34）；
- 扩展矩阵 `filters2`（通配 / 纯空白 / 大小写 / 超长 / 重复键 / 8 种注入串，8894 例）
  与 `dates`（日期写法矩阵，1353 例）见 `09-已知差异与根因.md` §6。
""",

    '05-高级查询与缓存.md': """
@MARK@

阶段9/10 之后本阶段的最新口径：

- query **112/112 逐字节一致**（原文那 1 例「编码穿越的 Tomcat HTML 400」已随 F36 收敛）；
- sysutil **59/59 一致**，且耗时从「Rust 5.9–6.4s」降到「Rust 0.13–0.27s」，
  同批 Java 0.17–0.38s（阶段5 记录的性能差异项已关闭，见 `10-性能与稳定性.md`）；
- 缓存隔离实验的结论不变，但补一条事实：**Java 写的缓存 blob 不是合法 JSON**
  （FastJSON 的 `@type` + `157L` 数字后缀），所以「同输入公平比对」这条路对
  `DATE_BorderWeighingCapture:*` 走不通，两侧只能各读各写的缓存 ——
  这正是 `vehicleweight/map` 差一天的根因（`09` 的 D1）。
""",
}


def main():
    for name, note in NOTES.items():
        p = os.path.join(DOCS, name)
        src = io.open(p, encoding='utf-8').read()
        i = src.find(MARK)
        if i >= 0:
            src = src[:i].rstrip('\n')
        else:
            src = src.rstrip('\n')
        io.open(p, 'w', encoding='utf-8', newline='\n').write(src + '\n' + note.replace('@MARK@', MARK))
        print('已更新 %s' % name)


if __name__ == '__main__':
    main()
