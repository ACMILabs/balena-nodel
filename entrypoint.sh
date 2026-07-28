#!/bin/bash
set -euo pipefail

# Balena host-network containers do not always receive an /etc/hosts entry for
# their runtime hostname. Java's InetAddress.getLocalHost() needs one for
# Nodel's topology discovery.
runtime_hostname="$(hostname)"
if ! getent hosts "$runtime_hostname" >/dev/null 2>&1; then
    printf '\n127.0.1.1\t%s\n' "$runtime_hostname" >> /etc/hosts
fi

# This node belongs to the image and is refreshed on every start. Everything
# else under /var/lib/nodel remains persistent.
node_name="${NODEL_NODE_NAME:-${BALENA_DEVICE_NAME_AT_INIT:-$runtime_hostname}}"
node_name="${node_name//\//_}"
node_dir="/var/lib/nodel/nodes/$node_name"
install -d -o nodel -g nodel "$node_dir/content"
install -o nodel -g nodel -m 0644 \
    /opt/nodel/managed-node/script.py "$node_dir/script.py"

export NODEL_MANAGED_NODE_NAME="$node_name"

nodel_args=("$@")
if [[ -n "${NODEL_INTERFACE:-}" ]]; then
    nodel_args+=(--interface "$NODEL_INTERFACE")
fi

# Nodel treats EOF on stdin as a shutdown request. Supply an idle, open stream
# while replacing this shell with Java so it receives container stop signals.
# Both long-running processes run as the unprivileged nodel user.
exec setpriv --reuid=nodel --regid=nodel --init-groups \
    java -jar /opt/nodel/nodel.jar "${nodel_args[@]}" \
    < <(setpriv --reuid=nodel --regid=nodel --init-groups tail -f /dev/null)
