#!/bin/sh
# Writes a Shiro configuration that requires HTTP Basic auth for every path,
# fixes ownership of the data volume, then runs Fuseki as the unprivileged user.
set -eu

: "${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set}"
case "$ADMIN_PASSWORD" in
  *[!A-Za-z0-9_.-]*) echo "ADMIN_PASSWORD may only contain A-Z a-z 0-9 _ . -" >&2; exit 1 ;;
esac

mkdir -p /fuseki/databases "$FUSEKI_BASE" /run/fuseki
umask 077
cat > /run/fuseki/shiro.ini <<INI
[users]
admin = ${ADMIN_PASSWORD}

[urls]
/** = authcBasic, user
INI

# Volumes created by the previous image are owned by root.
chown -R fuseki:fuseki /fuseki/databases "$FUSEKI_BASE" /run/fuseki

# JVM_ARGS is intentionally word-split.
# shellcheck disable=SC2086
exec setpriv --reuid=fuseki --regid=fuseki --init-groups \
  java ${JVM_ARGS:-} -jar /opt/fuseki/fuseki-server.jar \
  --shiro=/run/fuseki/shiro.ini --config=/fuseki/config.ttl
