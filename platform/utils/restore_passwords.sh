#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Check for root privileges
if (($UID != 0)); then
    echo "$0 needs to be run as root"
    exit 1
fi

# Check for correct usage
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <path_to_passwords.txt>"
    exit 1
fi

PASSWORDS_FILE=$1
# Assuming the script is run from the platform directory
DIRECTORY=$(pwd)

if [ ! -f "$PASSWORDS_FILE" ]; then
    echo "Error: Passwords file not found at $PASSWORDS_FILE"
    exit 1
fi

# --- SSH Password Restoration ---
echo "--- Restoring SSH passwords ---"
while read -r group_number passwd; do
    if [ -z "$group_number" ] || [ -z "$passwd" ]; then
        continue
    fi
    SSH_CONTAINER="${group_number}_ssh"
    if docker inspect -f '{{.State.Running}}' "$SSH_CONTAINER" >/dev/null 2>&1; then
        echo -e "${passwd}\n${passwd}" | docker exec -i "$SSH_CONTAINER" passwd root > /dev/null
        echo "  - SSH password for group ${group_number} restored."
    else
        echo "  - SSH container for group ${group_number} not found. Skipping."
    fi
done < "$PASSWORDS_FILE"
echo "--- SSH password restoration complete ---"


# --- Krill Password Restoration ---
echo ""
echo "--- Restoring Krill passwords ---"

KRILL_CONTAINERS_FILE="${DIRECTORY}/groups/rpki/krill_containers.txt"
if [ ! -f "$KRILL_CONTAINERS_FILE" ]; then
    echo "Warning: Krill containers list not found. Skipping Krill password restoration."
    exit 0
fi

# The file contains group_number and container_name per line
while read -r krill_group_number krill_container_name; do
    if [ -z "$krill_group_number" ]; then
        continue
    fi

    if ! docker inspect -f '{{.State.Running}}' "$krill_container_name" >/dev/null 2>&1; then
        echo "  - Krill container ${krill_container_name} not found or not running. Skipping."
        continue
    fi

    echo "  - Rebuilding Krill config for container ${krill_container_name}"

    # Dynamically find the host path of the krill.conf file from the container mount
    HOST_CONF_PATH=$(docker inspect -f '{{ range .Mounts }}{{ if eq .Destination "/var/krill/krill.conf" }}{{ .Source }}{{ end }}{{ end }}' "$krill_container_name")

    if [ -z "$HOST_CONF_PATH" ] || [ ! -f "$HOST_CONF_PATH" ]; then
        echo "    - ERROR: Could not dynamically find krill.conf on the host for container ${krill_container_name}. Skipping."
        continue
    fi
    
    echo "    - Found host config at: ${HOST_CONF_PATH}"

    TMP_CONF_NEW=$(mktemp)
    trap 'rm -f "$TMP_CONF_NEW"' EXIT

    # Backup original config on host
    cp "$HOST_CONF_PATH" "${HOST_CONF_PATH}.bak.$(date +%Y%m%d%H%M%S)"

    # Copy content before [auth_users]
    awk '/^\\\[auth_users\\\\]/ { exit } { print }' "$HOST_CONF_PATH" > "$TMP_CONF_NEW"

    # Start the [auth_users] section
    echo "" >> "$TMP_CONF_NEW"
    echo "[auth_users]" >> "$TMP_CONF_NEW"

    # Preserve admin/readonly users from old config
    grep -E '"(admin|readonly)@' "$HOST_CONF_PATH" >> "$TMP_CONF_NEW"

    # Generate and add new group user entries
    while read -r group_number passwd; do
        if [ -z "$group_number" ] || [ -z "$passwd" ]; then
            continue
        fi
        
        user_id="group${group_number}@netsyn.princeton.edu"
        
        # Use krillc to GENERATE the user entry with new hash and salt
        entry=$(printf "%s\n" "$passwd" | docker exec -i "$krill_container_name" krillc config user --id "$user_id" -a "role=readwrite" -a "inc_cas=group${group_number}")
        user_line=$(echo "$entry" | grep "$user_id" | tr -d '\r')

        if [[ -z "$user_line" ]]; then
            echo "    - ERROR: Failed to generate hash for user $user_id. Skipping this user." >&2
            continue
        fi
        
        echo "$user_line" >> "$TMP_CONF_NEW"
    done < "$PASSWORDS_FILE"

    # Copy content after [auth_users] section
    awk '
      BEGIN { in_auth = 0 }
      /^\\\[auth_users\\\\]/ { in_auth = 1; next }
      {
        if (!in_auth) next
        if ($0 ~ /^\\\[/ && $0 != "[auth_users]") {
          in_auth = 2
        }
      }
      in_auth == 2 { print }
    ' "$HOST_CONF_PATH" >> "$TMP_CONF_NEW"

    # Replace the original config on the host
    mv "$TMP_CONF_NEW" "$HOST_CONF_PATH"
    echo "    - Host config file ${HOST_CONF_PATH} has been updated."

done < "$KRILL_CONTAINERS_FILE"

# Restart all Krill containers to apply changes
echo "Restarting Krill containers to apply changes..."
while read -r krill_group_number krill_container_name; do
    if [ -z "$krill_container_name" ]; then
        continue
    fi
    if docker inspect -f '{{.State.Running}}' "$krill_container_name" >/dev/null 2>&1; then
        # docker restart "$krill_container_name" > /dev/null
        # docker exec "$krill_container_name" bash -c 'supervisorctl restart krill'
        ${DIRECTORY}/setup/restart_container.sh l3-host 1 PHY host1
        echo "  - Restarted krill on ${krill_container_name}"
    fi
done < "$KRILL_CONTAINERS_FILE"

echo "--- Krill password restoration complete ---"

echo "Done."