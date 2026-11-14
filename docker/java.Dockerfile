# Java service image (Spring Boot 4.1.2 / JDK 25, bytecode --release 25)
# Build context = repo root:
#   docker build -f docker/java.Dockerfile -t car-monit-api .
# Boot 4.1.2 / Spring Framework 7 require JDK 17+; this branch builds and runs on JDK 25.
# Credentials/URLs are injected via Spring environment variables, never baked into the image.
# Orika 1.5.4 needs --add-opens=java.base/java.lang=ALL-UNNAMED on JDK 17+ (Object#clone reflection).
FROM maven:3.9.9-eclipse-temurin-25 AS build

WORKDIR /build

COPY pom.xml ./
COPY pro-base-common/pom.xml pro-base-common/
COPY pro-business-api/pom.xml pro-business-api/

COPY pro-base-common/src pro-base-common/src
COPY pro-business-api/src pro-business-api/src

RUN mvn -B -ntp -DskipTests package

FROM eclipse-temurin:25-jre-jammy

RUN groupadd --system carmonit \
 && useradd --system --gid carmonit --no-create-home carmonit

WORKDIR /app
COPY --from=build /build/pro-business-api/target/pro-business-api-1.0.jar /app/app.jar

USER carmonit
EXPOSE 9902

ENV JAVA_OPTS="-Xms256m -Xmx512m"
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS --add-opens=java.base/java.lang=ALL-UNNAMED -jar /app/app.jar"]