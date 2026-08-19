#!/bin/bash
set -euo pipefail

die() {
    echo "$*" >&2
    exit 1
}

sanitise_node_name() {
    local name="$1"
    name="${name//\//_}"
    name="${name//$'\n'/_}"
    name="${name//$'\r'/_}"
    if [[ "$name" == "." || "$name" == ".." ]]; then
        name="${name//./_}"
    fi
    printf '%s' "$name"
}

is_safe_node_name() {
    local name="$1"
    [[ -n "$name" &&
        "$name" != "." &&
        "$name" != ".." &&
        "$name" != */* &&
        "$name" != *$'\n'* &&
        "$name" != *$'\r'* ]]
}

ensure_real_directory() {
    local path="$1"
    if [[ -L "$path" ]]; then
        die "Refusing to use symlink as a Nodel directory: $path"
    fi
    if [[ -e "$path" && ! -d "$path" ]]; then
        die "Expected a Nodel directory but found another file type: $path"
    fi
}

ensure_safe_file_destination() {
    local path="$1"
    if [[ -L "$path" ]]; then
        die "Refusing to replace symlink during Nodel startup: $path"
    fi
    if [[ -e "$path" && ! -f "$path" ]]; then
        die "Expected a regular Nodel file but found another file type: $path"
    fi
}

install_file_safely() {
    local source="$1"
    local destination="$2"
    local temporary_file

    ensure_safe_file_destination "$destination"
    temporary_file="$(mktemp "${destination%/*}/.balena-nodel-install.XXXXXX")"
    install -o nodel -g nodel -m 0644 "$source" "$temporary_file"
    mv -f "$temporary_file" "$destination"
}

discover_legacy_node() {
    local nodes_dir="$1"
    local node_name="$2"
    shift 2
    local candidate
    local candidate_name
    local candidate_recipe
    local known_recipe
    local recipe_matches
    local previous_node_name=""

    # Releases before the state files were introduced can still have an
    # image-managed recipe in a persistent volume. Compare it with every recipe
    # previously shipped by the image to identify it for one-time migration.
    for candidate in \
        "$nodes_dir"/* \
        "$nodes_dir"/.[!.]* \
        "$nodes_dir"/..?*; do
        [[ -d "$candidate" && ! -L "$candidate" ]] || continue
        candidate_name="${candidate##*/}"
        [[ "$candidate_name" != "$node_name" ]] || continue
        is_safe_node_name "$candidate_name" || continue
        candidate_recipe="$candidate/script.py"
        [[ -f "$candidate_recipe" && ! -L "$candidate_recipe" ]] || continue

        recipe_matches=false
        for known_recipe in "$@"; do
            if cmp -s "$known_recipe" "$candidate_recipe"; then
                recipe_matches=true
                break
            fi
        done
        [[ "$recipe_matches" == true ]] || continue

        if [[ -n "$previous_node_name" ]]; then
            echo "Multiple legacy image-managed nodes found; refusing migration" >&2
            return 1
        fi
        previous_node_name="$candidate_name"
    done

    printf '%s' "$previous_node_name"
}

read_node_state() {
    local state_file="$1"
    local state_description="$2"
    local node_name

    ensure_safe_file_destination "$state_file"
    if [[ ! -e "$state_file" ]]; then
        return
    fi

    IFS= read -r node_name < "$state_file" || true
    if ! is_safe_node_name "$node_name"; then
        echo "Invalid $state_description state in $state_file" >&2
        return 1
    fi
    printf '%s' "$node_name"
}

stage_tracked_node() {
    local nodes_dir="$1"
    local migration_dir="$2"
    local role="$3"
    local previous_node_name="$4"
    local node_name="$5"
    local previous_node_dir
    local staged_node_dir="$migration_dir/$role"

    ensure_real_directory "$staged_node_dir"
    if [[ -d "$staged_node_dir" ||
        -z "$previous_node_name" ||
        "$previous_node_name" == "$node_name" ]]; then
        return
    fi

    previous_node_dir="$nodes_dir/$previous_node_name"
    ensure_real_directory "$previous_node_dir"
    if [[ ! -d "$previous_node_dir" ]]; then
        return
    fi

    mv "$previous_node_dir" "$staged_node_dir"
}

place_staged_node() {
    local nodes_dir="$1"
    local migration_dir="$2"
    local role="$3"
    local node_name="$4"
    local staged_node_dir="$migration_dir/$role"
    local node_dir

    ensure_real_directory "$staged_node_dir"
    if [[ ! -d "$staged_node_dir" ]]; then
        return
    fi

    if [[ -z "$node_name" ]]; then
        rm -rf "$staged_node_dir"
        return
    fi

    node_dir="$nodes_dir/$node_name"
    ensure_real_directory "$node_dir"
    if [[ -e "$node_dir" ]]; then
        if [[ "$role" == "managed" ]]; then
            # A managed destination can exist after an interrupted prior start;
            # its image recipe will be refreshed below.
            rm -rf "$staged_node_dir"
            return
        fi
        echo "Cannot migrate Wake-on-LAN node: destination exists: $node_dir" >&2
        return 1
    fi

    mv "$staged_node_dir" "$node_dir"
}

reconcile_tracked_nodes() {
    local nodes_dir="$1"
    local migration_dir="$2"
    local managed_state_file="$3"
    local managed_node_name="$4"
    local wol_state_file="$5"
    local wol_node_name="$6"
    local previous_managed_node_name
    local previous_wol_node_name

    previous_managed_node_name="$(read_node_state \
        "$managed_state_file" "managed-node")"
    previous_wol_node_name="$(read_node_state \
        "$wol_state_file" "Wake-on-LAN node")"
    if [[ -n "$previous_managed_node_name" &&
        "$previous_managed_node_name" == "$previous_wol_node_name" ]]; then
        echo "Managed and Wake-on-LAN state refer to the same node" >&2
        return 1
    fi

    ensure_real_directory "$migration_dir"
    install -d -m 0700 "$migration_dir"
    stage_tracked_node \
        "$nodes_dir" "$migration_dir" managed \
        "$previous_managed_node_name" "$managed_node_name"
    stage_tracked_node \
        "$nodes_dir" "$migration_dir" wol \
        "$previous_wol_node_name" "$wol_node_name"

    # Both sources are now outside Nodel's active nodes directory, so crossed
    # names and swaps cannot make one role delete the other role's state.
    place_staged_node \
        "$nodes_dir" "$migration_dir" managed "$managed_node_name"
    place_staged_node \
        "$nodes_dir" "$migration_dir" wol "$wol_node_name"
    rmdir "$migration_dir" 2>/dev/null || true
}

write_node_state() {
    local state_file="$1"
    local node_name="$2"
    local temporary_file

    ensure_safe_file_destination "$state_file"
    temporary_file="$(mktemp "${state_file%/*}/.node-name.XXXXXX")"
    printf '%s\n' "$node_name" > "$temporary_file"
    chown root:root "$temporary_file"
    chmod 0600 "$temporary_file"
    mv -f "$temporary_file" "$state_file"
}

remove_node_state() {
    local state_file="$1"

    ensure_safe_file_destination "$state_file"
    rm -f "$state_file"
}

main() {
    local runtime_hostname
    local data_dir="/var/lib/nodel"
    local nodes_dir="$data_dir/nodes"
    local migration_dir="$data_dir/.node-migration"
    local managed_node_state="$data_dir/.managed-node-name"
    local wol_node_state="$data_dir/.wol-node-name"
    local node_name
    local node_dir
    local previous_node_name
    local wol_node_name
    local wol_node_dir
    local -a nodel_args

    # Balena host-network containers do not always receive an /etc/hosts entry
    # for their runtime hostname. Java's InetAddress.getLocalHost() needs one
    # for Nodel's topology discovery.
    runtime_hostname="$(hostname)"
    if ! getent hosts "$runtime_hostname" >/dev/null 2>&1; then
        printf '\n127.0.1.1\t%s\n' "$runtime_hostname" >> /etc/hosts
    fi

    # Older images ran Java as root. Reconcile existing volumes without
    # dereferencing links left by editable recipes, then create the nodes
    # parent explicitly so a fresh volume is immediately writable by Nodel.
    ensure_real_directory "$data_dir"
    ensure_real_directory "$nodes_dir"
    chown -Rh nodel:nodel "$data_dir"
    install -d -o nodel -g nodel "$nodes_dir"

    # This node belongs to the image and is refreshed on every start.
    node_name="$(sanitise_node_name \
        "${NODEL_NODE_NAME:-${BALENA_DEVICE_NAME_AT_INIT:-$runtime_hostname}}")"
    is_safe_node_name "$node_name" || die "The managed Nodel node name is invalid"
    wol_node_name=""
    if [[ -n "${NODEL_WOL_NODE_NAME:-}" ]]; then
        wol_node_name="$(sanitise_node_name "$NODEL_WOL_NODE_NAME")"
        is_safe_node_name "$wol_node_name" ||
            die "The Wake-on-LAN Nodel node name is invalid"
        if [[ "$wol_node_name" == "$node_name" ]]; then
            die "NODEL_WOL_NODE_NAME must differ from the managed node name"
        fi
    fi

    # Discover nodes installed before name tracking was introduced.
    if [[ ! -e "$wol_node_state" && ! -L "$wol_node_state" ]]; then
        previous_node_name="$(discover_legacy_node \
            "$nodes_dir" "$wol_node_name" \
            /opt/nodel/wake-on-lan-node/script.py)"
        if [[ -n "$previous_node_name" ]]; then
            write_node_state "$wol_node_state" "$previous_node_name"
        fi
    fi

    node_dir="$nodes_dir/$node_name"
    ensure_real_directory "$node_dir"
    if [[ ! -e "$managed_node_state" && ! -L "$managed_node_state" ]]; then
        previous_node_name="$(discover_legacy_node \
            "$nodes_dir" "$node_name" \
            /opt/nodel/managed-node/script.py \
            /opt/nodel/migration/master-managed-node.py)"
        if [[ -n "$previous_node_name" ]]; then
            write_node_state \
                "$managed_node_state" "$previous_node_name"
        fi
    fi

    reconcile_tracked_nodes \
        "$nodes_dir" "$migration_dir" \
        "$managed_node_state" "$node_name" \
        "$wol_node_state" "$wol_node_name"
    ensure_real_directory "$node_dir"
    ensure_real_directory "$node_dir/content"
    install -d -o nodel -g nodel "$node_dir" "$node_dir/content"
    install_file_safely \
        /opt/nodel/managed-node/script.py "$node_dir/script.py"
    write_node_state "$managed_node_state" "$node_name"

    export NODEL_MANAGED_NODE_NAME="$node_name"

    # Wake-on-LAN controls another computer, so it is opt-in and installed as a
    # separate node. It cannot wake this Balena device after it has powered off.
    if [[ -n "$wol_node_name" ]]; then
        wol_node_dir="$nodes_dir/$wol_node_name"
        ensure_real_directory "$wol_node_dir"
        install -d -o nodel -g nodel "$wol_node_dir"
        install_file_safely \
            /opt/nodel/wake-on-lan-node/script.py "$wol_node_dir/script.py"
        write_node_state "$wol_node_state" "$wol_node_name"
    else
        remove_node_state "$wol_node_state"
    fi

    nodel_args=("$@")
    if [[ -n "${NODEL_INTERFACE:-}" ]]; then
        nodel_args+=(--interface "$NODEL_INTERFACE")
    fi

    # Nodel treats EOF on stdin as a shutdown request. Supply an idle, open
    # stream while replacing this shell with Java so it receives stop signals.
    # Both long-running processes run as the unprivileged nodel user.
    exec setpriv --reuid=nodel --regid=nodel --init-groups \
        java -jar /opt/nodel/nodel.jar "${nodel_args[@]}" \
        < <(setpriv --reuid=nodel --regid=nodel --init-groups tail -f /dev/null)
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
