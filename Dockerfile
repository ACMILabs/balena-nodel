FROM eclipse-temurin:21-jre-jammy

ARG NODEL_VERSION=2.2.1.542
ARG NODEL_SHA256=5cc89df736006e48dc7044691ae7a4ea44353b57ddf8ae7bcfcccc62963a13f1

LABEL org.opencontainers.image.source="https://github.com/ACMILabs/balena-nodel"

COPY entrypoint.sh /usr/local/bin/nodel-entrypoint
COPY managed-node/script.py /opt/nodel/managed-node/script.py
COPY migration/master-managed-node.py /opt/nodel/migration/master-managed-node.py
COPY wake-on-lan-node/script.py /opt/nodel/wake-on-lan-node/script.py

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl; \
    release="${NODEL_VERSION%.*}"; \
    revision="${NODEL_VERSION##*.}"; \
    curl -fL \
        "https://github.com/museumsvictoria/nodel/releases/download/v${NODEL_VERSION}/nodelhost-release-${release}-rev${revision}.jar" \
        -o /opt/nodel/nodel.jar; \
    echo "${NODEL_SHA256}  /opt/nodel/nodel.jar" | sha256sum -c -; \
    apt-get purge -y --auto-remove curl; \
    rm -rf /var/lib/apt/lists/*; \
    useradd --system --home-dir /var/lib/nodel --shell /usr/sbin/nologin nodel; \
    install -d -o nodel -g nodel /var/lib/nodel; \
    chmod 0755 /usr/local/bin/nodel-entrypoint

WORKDIR /var/lib/nodel

EXPOSE 8085/tcp
EXPOSE 5354/udp

ENTRYPOINT ["/usr/local/bin/nodel-entrypoint"]
