#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

# Periodic network state logging for all devices.
# It creates a cron job that runs every 5 minutes.

DIRECTORY=$(cd "$(dirname "$0")"/.. && pwd)

# 1. Create the logging directory
LOGGING_DIR="${DIRECTORY}/logging"
mkdir -p "${LOGGING_DIR}"
LOGS_DIR="${DIRECTORY}/logs"
mkdir -p "${LOGS_DIR}"

# 2. Create the network logger script
NETWORK_LOGGER_SCRIPT="${LOGGING_DIR}/network_logger.sh"
cat << 'EOF' > "${NETWORK_LOGGER_SCRIPT}"
#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <container_name> <logs_dir>"
    exit 1
fi

CONTAINER_NAME=$1
LOGS_DIR=$2
LOG_DIR="${LOGS_DIR}/${CONTAINER_NAME}"
mkdir -p "${LOG_DIR}"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG_FILE_PREFIX="${LOG_DIR}/${TIMESTAMP}"

echo "Logging for ${CONTAINER_NAME} at ${TIMESTAMP}"

# Default linux commands for all devices
sudo docker exec "${CONTAINER_NAME}" ip addr > "${LOG_FILE_PREFIX}_ip_addr.log" 2>/dev/null || true
sudo docker exec "${CONTAINER_NAME}" ip route > "${LOG_FILE_PREFIX}_ip_route.log" 2>/dev/null || true
sudo docker exec "${CONTAINER_NAME}" ip -s link > "${LOG_FILE_PREFIX}_ip_link.log" 2>/dev/null || true
sudo docker exec "${CONTAINER_NAME}" ip neigh > "${LOG_FILE_PREFIX}_ip_neigh.log" 2>/dev/null || true

if [[ "${CONTAINER_NAME}" == *"router"* || "${CONTAINER_NAME}" == *"IXP"* ]]; then
    # Router specific commands
    echo "Device type: Router"
    sudo docker exec "${CONTAINER_NAME}" iptables-save > "${LOG_FILE_PREFIX}_iptables.log" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" ip6tables-save > "${LOG_FILE_PREFIX}_ip6tables.log" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" cat /etc/frr/frr.conf > "${LOG_FILE_PREFIX}_frr.conf" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" vtysh -c 'show ip route' > "${LOG_FILE_PREFIX}_vtysh_show_ip_route.log" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" vtysh -c 'show bgp summary' > "${LOG_FILE_PREFIX}_vtysh_show_bgp_summary.log" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" vtysh -c 'show running-config' > "${LOG_FILE_PREFIX}_vtysh_show_running-config.log" 2>/dev/null || true
elif [[ "${CONTAINER_NAME}" == *"_L2_"* && "${CONTAINER_NAME}" == *"_S"* ]]; then
    # Switch specific commands
    echo "Device type: Switch"
    sudo docker exec "${CONTAINER_NAME}" ovs-vsctl show > "${LOG_FILE_PREFIX}_ovs-vsctl_show.log" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" ovs-ofctl show br0 > "${LOG_FILE_PREFIX}_ovs-ofctl_show_br0.log" 2>/dev/null || true
    sudo docker exec "${CONTAINER_NAME}" ovs-appctl fdb/show br0 > "${LOG_FILE_PREFIX}_ovs-appctl_fdb_show_br0.log" 2>/dev/null || true
else
    # Host specific commands (L3 and L2 hosts)
    echo "Device type: Host"
    # No extra commands for now, default linux commands are sufficient
fi
EOF
chmod +x "${NETWORK_LOGGER_SCRIPT}"

# 3. Create the script to start logging on all devices
START_LOGGING_SCRIPT="${LOGGING_DIR}/start_logging.sh"
cat << 'EOF' > "${START_LOGGING_SCRIPT}"
#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

DIRECTORY=$(cd "$(dirname "$0")"/.. && pwd)
LOGGER_SCRIPT="${DIRECTORY}/logging/network_logger.sh"
LOGS_DIR="${DIRECTORY}/logs"

CONTAINER_LIST_FILE="${DIRECTORY}/groups/docker_containers.txt"
if [ ! -f "${CONTAINER_LIST_FILE}" ]; then
    echo "Container list not found at ${CONTAINER_LIST_FILE}"
    # Fallback to docker ps if file not found
    CONTAINER_LIST=$(sudo docker ps --format '{{.Names}}' | grep -E "router|IXP|host|_L2_")
    if [ -z "${CONTAINER_LIST}" ]; then
        echo "No router, IXP, host or L2 containers found."
        exit 1
    fi
    echo "${CONTAINER_LIST}" | grep -v "_ssh" | while read -r CONTAINER_NAME; do
        bash "${LOGGER_SCRIPT}" "${CONTAINER_NAME}" "${LOGS_DIR}"
    done
else
    # Grep for router, ixp, host and L2 containers, but exclude ssh proxies
    grep -E "router|IXP|host|_L2_" "${CONTAINER_LIST_FILE}" | grep -v "_ssh" | while read -r CONTAINER_NAME; do
        bash "${LOGGER_SCRIPT}" "${CONTAINER_NAME}" "${LOGS_DIR}"
    done
fi
EOF
chmod +x "${START_LOGGING_SCRIPT}"

# 4. Create and install the cron job
CRON_FILE="${LOGGING_DIR}/crontab.txt"
CRON_CMD="/bin/bash ${START_LOGGING_SCRIPT} >> ${LOGS_DIR}/cron.log 2>&1"

echo "*/5 * * * * ${CRON_CMD}" > "${CRON_FILE}"

echo "Setting up cron job..."
sudo crontab "${CRON_FILE}"

echo "Network logging setup complete."
echo "A cron job has been installed to log network state every 5 minutes."
echo "Logs will be stored in: ${LOGS_DIR}"
echo "You can check the cron job execution log at: ${LOGS_DIR}/cron.log"
echo "To run the logging manually, execute: sudo ${START_LOGGING_SCRIPT}"
