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

# Get the list of krill containers
KRILL_CONTAINERS_FILE="${DIRECTORY}/groups/rpki/krill_containers.txt"
if [ ! -f "$KRILL_CONTAINERS_FILE" ]; then
    echo "Warning: Krill containers list not found at $KRILL_CONTAINERS_FILE. Skipping Krill password restoration."
    KRILL_CONTAINERS=()
else
    readarray -t KRILL_CONTAINERS < <(awk '/./{print $2}' "$KRILL_CONTAINERS_FILE")
fi


while read -r group_number passwd; do
    if [ -z "$group_number" ] || [ -z "$passwd" ]; then
        continue
    fi

    echo "Restoring password for group ${group_number}"

    # Restore SSH password
    SSH_CONTAINER="${group_number}_ssh"
    if docker inspect -f '{{.State.Running}}' "$SSH_CONTAINER" >/dev/null 2>&1; then
        echo -e "${passwd}\n${passwd}" | docker exec -i "$SSH_CONTAINER" passwd root > /dev/null
        echo "  - SSH password restored for ${SSH_CONTAINER}"
    else
        echo "  - SSH container ${SSH_CONTAINER} not found or not running. Skipping."
    fi

    # Restore Krill password
    if [ ${#KRILL_CONTAINERS[@]} -gt 0 ]; then
        for krill_container in "${KRILL_CONTAINERS[@]}"; do
             if [ -z "$krill_container" ]; then
                continue
             fi
             if docker inspect -f '{{.State.Running}}' "$krill_container" >/dev/null 2>&1; then
                echo "  - Restoring Krill password in ${krill_container}"
                user_id="group${group_number}@netsyn.princeton.edu"
                
                echo "${passwd}" | docker exec -i "$krill_container" krillc config user --id "$user_id" \
                    -a "role=readwrite" -a "inc_cas=group${group_number}" > /dev/null
                echo "    - Krill password for user ${user_id} restored."
             else
                echo "  - Krill container ${krill_container} not found or not running. Skipping."
             fi
        done
    fi

done < "$PASSWORDS_FILE"

echo "Password restoration complete."

# After updating passwords in krill, the daemon needs to be reloaded.
if [ ${#KRILL_CONTAINERS[@]} -gt 0 ]; then
    echo "Reloading Krill daemons..."
    for krill_container in "${KRILL_CONTAINERS[@]}"; do
        if docker inspect -f '{{.State.Running}}' "$krill_container" >/dev/null 2>&1; then
            docker exec "$krill_container" bash -c "kill -3 \
$(cat /var/run/krill.pid)"
            echo "  - Reloaded ${krill_container}"
        fi
    done
fi

echo "Done."
