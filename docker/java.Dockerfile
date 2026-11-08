# Java 服务镜像（Spring Boot 2.4.5 / source-target 1.8）
# 构建上下文 = 仓库根目录：
#   docker build -f docker/java.Dockerfile -t car-monit-api .
#
# 基础镜像选择：
#   * 构建阶段 maven:3.9-eclipse-temurin-8 —— 项目 pom 锁 source/target=1.8，
#     必须用 JDK 8 编译；Maven 3.9 与 Spring Boot 2.4.5 插件链兼容。
#   * 运行阶段 eclipse-temurin:8-jre-jammy —— 只要 JRE，Ubuntu Jammy 提供 glibc，
#     避免 Alpine/musl 与 Spring Boot 2.4.5 原生依赖的兼容风险。
# 运行期配置：application.yml 已打入 jar；口令/连接串由 Spring 环境变量覆盖，
# 镜像内不写入任何真实凭据。
FROM maven:3.9.9-eclipse-temurin-8 AS build

WORKDIR /build

# 先拷 pom，利用 Docker 层缓存固定依赖解析阶段
COPY pom.xml ./
COPY pro-base-common/pom.xml pro-base-common/
COPY pro-business-api/pom.xml pro-business-api/

COPY pro-base-common/src pro-base-common/src
COPY pro-business-api/src pro-business-api/src

RUN mvn -B -ntp -DskipTests package

FROM eclipse-temurin:8-jre-jammy

RUN groupadd --system carmonit \
 && useradd --system --gid carmonit --no-create-home carmonit

WORKDIR /app
COPY --from=build /build/pro-business-api/target/pro-business-api-1.0.jar /app/app.jar

USER carmonit
EXPOSE 9901

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
