#!/bin/bash
set -euo pipefail

# Balena host-network containers do not always receive an /etc/hosts entry for
# their runtime hostname. Java's InetAddress.getLocalHost() needs one for
# Nodel's topology discovery.
runtime_hostname="$(hostname)"
if ! getent hosts "$runtime_hostname" >/dev/null 2>&1; then
    printf '\n127.0.1.1\t%s\n' "$runtime_hostname" >> /etc/hosts
fi

# Older balena-nodel images ran Java as root, so existing persistent volumes can
# contain root-owned nodes that the unprivileged Nodel process cannot update.
# Reconcile the volume on every start so restores and copied-in recipes are also
# usable; chown does not follow symlinks found during recursive traversal.
chown -R nodel:nodel /var/lib/nodel

# This node belongs to the image and is refreshed on every start. Everything
# else under /var/lib/nodel remains persistent.
node_name="${NODEL_NODE_NAME:-${BALENA_DEVICE_NAME_AT_INIT:-$runtime_hostname}}"
node_name="${node_name//\//_}"
node_dir="/var/lib/nodel/nodes/$node_name"
install -d -o nodel -g nodel "$node_dir" "$node_dir/content"
install -o nodel -g nodel -m 0644 \
    /opt/nodel/managed-node/script.py "$node_dir/script.py"

export NODEL_MANAGED_NODE_NAME="$node_name"

# Wake-on-LAN controls another computer, so it is opt-in and installed as a
# separate node. It cannot wake the Balena device hosting this container after
# that device has powered off.
if [[ -n "${NODEL_WOL_NODE_NAME:-}" ]]; then
    wol_node_name="${NODEL_WOL_NODE_NAME//\//_}"
    if [[ "$wol_node_name" == "$node_name" ]]; then
        echo "NODEL_WOL_NODE_NAME must differ from the managed node name" >&2
        exit 1
    fi
    wol_node_dir="/var/lib/nodel/nodes/$wol_node_name"
    install -d -o nodel -g nodel "$wol_node_dir"
    install -o nodel -g nodel -m 0644 \
        /opt/nodel/wake-on-lan-node/script.py "$wol_node_dir/script.py"
fi

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
