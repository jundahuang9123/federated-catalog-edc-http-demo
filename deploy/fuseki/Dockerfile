# Apache Jena Fuseki built from the official release jar on Maven Central.
# Replaces the unmaintained stain/jena-fuseki image (last release 5.1.0).
FROM eclipse-temurin:21-jre-noble

ARG FUSEKI_VERSION=6.3.0
ARG FUSEKI_SHA512=9381800dd5644abbb6a347424229d2f0cfbf721a7afebe33a19c812a1196c3f6d558c34c854a96c671ea7d7b23141ccb163d0673c69e99236f04a2e51ca82505

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 fuseki \
    && useradd --system --uid 10001 --gid fuseki --home-dir /fuseki --no-create-home fuseki \
    && mkdir -p /opt/fuseki \
    && curl -fsSL -o /opt/fuseki/fuseki-server.jar \
       "https://repo1.maven.org/maven2/org/apache/jena/jena-fuseki-server/${FUSEKI_VERSION}/jena-fuseki-server-${FUSEKI_VERSION}.jar" \
    && echo "${FUSEKI_SHA512}  /opt/fuseki/fuseki-server.jar" | sha512sum -c -

COPY --chmod=0755 entrypoint.sh /usr/local/bin/fuseki-entrypoint

ENV FUSEKI_BASE=/fuseki/run
WORKDIR /fuseki
EXPOSE 3030
ENTRYPOINT ["/usr/local/bin/fuseki-entrypoint"]
