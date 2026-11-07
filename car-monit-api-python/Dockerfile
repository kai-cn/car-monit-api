# P1-8（docs/迁移审阅报告.md）：生产镜像。
# 构建上下文 = 本目录（car-monit-api-python）：
#   docker build -t car-monit-api:v2 .
# 运行（中间件适配器落地前，prod 模式会拒绝替身假成功操作——见 app/runtime.py）：
#   docker run -p 9901:9901 \
#     -e SPRING_DATASOURCE_DYNAMIC_DATASOURCE_MASTER_PASSWORD=... \
#     car-monit-api:v2
FROM python:3.12-slim

# 非 root 运行（P0-6 生产收敛）
RUN useradd --create-home --uid 10001 carmonit
WORKDIR /app

# 依赖：按锁文件精确安装（可复现构建）
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

# 应用：Mapper XML 已随包发布（P0-1），无需 Java 源码树
COPY --chown=carmonit:carmonit . /app

USER carmonit
ENV PYTHONUNBUFFERED=1 \
    CAR_MONIT_RUNTIME=prod \
    CAR_MONIT_HOST=0.0.0.0
EXPOSE 9901

# liveness 只探进程（/health/ready 才做依赖检查，见 P0-6）
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:9901/health/live', timeout=4)"

CMD ["python", "run.py"]
