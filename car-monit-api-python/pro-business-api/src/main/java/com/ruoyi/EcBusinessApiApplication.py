# -*- coding: utf-8 -*-
"""com.ruoyi.EcBusinessApiApplication

源文件：pro-business-api/src/main/java/com/ruoyi/EcBusinessApiApplication.java

【Java→Python】整体说明
1) ``@SpringBootApplication`` 是 Spring Boot 的**组合注解**（= @Configuration +
   @EnableAutoConfiguration + @ComponentScan），启动时由 `SpringApplication.run()`
   创建容器、扫描 Bean、启动内嵌 Tomcat。Python 没有容器/自动装配：
   本模块退化为**启动入口**，只做「读配置 → 打印访问地址」，
   各 Bean 的装配改由显式构造（见各 Service/Controller 的构造器默认参数）。
2) ``@MapperScan(value={"com.ruoyi.base.**.mapper*"})`` 让 MyBatis 扫描并注册
   Mapper 接口代理；Python 的 Mapper 是普通类（见 com.ruoyi.base.mapper.*），
   无需扫描，这一行在 Python 侧**语义丢失**，仅在注释中保留。
3) ``@Slf4j``（lombok）→ 模块级 ``logging.getLogger(__name__)``。
4) ``ConfigurableApplicationContext`` → ``_ApplicationContext`` 最小替身，
   只保留 `getEnvironment()` / `close()`，用来承载“容器已启动”的状态。
5) ``InetAddress.getLocalHost().getHostAddress()`` → ``socket.gethostbyname(socket.gethostname())``。
   注意：Java 在无法解析主机名时抛 ``UnknownHostException``（受检异常，main 声明 throws）；
   Python 抛 ``socket.gaierror``，本文件按 Java 语义**直接向上抛**，不做兜底。
6) Java 的 ``main(String[] args)`` → Python 模块级 ``main(args)`` + ``if __name__ == "__main__"``；
   另外保留 ``EcBusinessApiApplication.main(...)`` 静态方法，保证调用点与 Java 一致。
7) 最关键的差异：Java 启动后**进程常驻**（Tomcat + 定时任务线程池）；
   Python 侧 ``main()`` 执行完就返回 —— 需要常驻时由外部进程管理器或
   ``time.sleep`` 保持，替身不擅自起无限循环。
"""
from __future__ import annotations

import logging
import socket
from typing import Any, List, Optional

from org.springframework.core.env.Environment import Environment

log = logging.getLogger(__name__)

__all__ = ["EcBusinessApiApplication", "main"]


class _ApplicationContext(object):
    """``ConfigurableApplicationContext`` 的最小替身。

    【Java→Python】Spring 的上下文持有 BeanFactory、Environment、生命周期回调；
    这里只保留 Environment 与“是否已启动”的标记，足以支撑 main() 的日志逻辑。
    """

    def __init__(self, environment: Environment) -> None:
        self._environment = environment
        self._active = True

    def getEnvironment(self) -> Environment:
        return self._environment

    def isActive(self) -> bool:
        return self._active

    def close(self) -> None:
        self._active = False

    def __enter__(self) -> "_ApplicationContext":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        # 对应 Java 的 try-with-resources / registerShutdownHook
        self.close()


class EcBusinessApiApplication(object):
    """Spring Boot 启动类的 Python 替身。"""

    @staticmethod
    def main(args: Optional[List[str]] = None) -> _ApplicationContext:
        """等价 ``public static void main(String[] args)``。

        【Java→Python】Java 的 `SpringApplication.run(...)` 会阻塞式完成容器 refresh
        并返回 ``ConfigurableApplicationContext``；这里返回一个**已启动**的轻量上下文，
        不做 Bean 扫描（Python 侧由调用方显式构造需要启动的服务）。
        """
        # 【Java→Python】`args` 在 Java 里是命令行参数（--key=value 会覆盖配置）；
        # Python 侧保留参数但暂不解析，占位以便后续按需实现。
        application = _ApplicationContext(Environment())

        env = application.getEnvironment()
        ip = EcBusinessApiApplication._localHostAddress()
        port = env.getProperty("server.port")
        path = env.getProperty("server.servlet.context-path")
        # 【Java→Python】Java 把 path 直接拼在 URL 里：context-path="/" 时会出现
        # "http://host:port//doc.html" 的双斜杠，原工程如此，忠实保留不做归一化。
        log.info("\n----------------------------------------------------------\n\t"
                 "Application ammeter-workorder is running! Access URLs:\n\t"
                 "Local: \t\thttp://localhost:" + str(port) + str(path) + "doc.html\n\t"
                 "External: \thttp://" + str(ip) + ":" + str(port) + str(path) + "\n\t"
                 "Doc: \t\thttp://" + str(ip) + ":" + str(port) + str(path) + "doc.html\n"
                 "----------------------------------------------------------")
        return application

    @staticmethod
    def _localHostAddress() -> str:
        """等价 ``InetAddress.getLocalHost().getHostAddress()``。

        【Java→Python】Java 的 getLocalHost() 取**本机 hostname 对应的地址**，
        在多网卡机器上可能返回非业务网卡地址；这里用同样的 hostname 解析方式，
        保持“结果可能与预期网卡不一致”的原工程特性。
        Java 解析失败抛 UnknownHostException（受检）→ Python 抛 socket.gaierror，直接上抛。
        """
        return socket.gethostbyname(socket.gethostname())


def main(args: Optional[List[str]] = None) -> _ApplicationContext:
    """模块级入口（对应 Java 的 main 方法，便于 ``python -m`` 调用）。"""
    return EcBusinessApiApplication.main(args)


if __name__ == "__main__":
    # 【Java→Python】Java 由 JVM 调 main 后进程常驻（Tomcat 线程）；
    # Python 脚本执行完 main() 就退出，这里显式提示，避免误以为“服务已监听端口”。
    _context = main()
    print("Spring 容器替身已启动（无内嵌 Web 容器，进程不会常驻监听端口）。")
