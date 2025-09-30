#!/bin/bash
#
# Connects the measurement, dns and matrix services
#

# sanity check
# set -e
set -o errexit
set -o pipefail
set -o nounset

# make sure the script is executed with root privileges
if (($UID != 0)); then
    echo "$0 needs to be run as root"
    exit 1
fi

# print the usage if not enough arguments are provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi


DIRECTORY=$(readlink -f $1)
source "${DIRECTORY}"/config/variables.sh
source "${DIRECTORY}"/config/subnet_config.sh
source "${DIRECTORY}"/setup/_parallel_helper.sh
source "${DIRECTORY}"/groups/docker_pid.map
source "${DIRECTORY}"/setup/_connect_utils.sh
readarray ASConfig < "${DIRECTORY}"/config/AS_config.txt
GroupNumber=${#ASConfig[@]}

MatrixConfigDir="${DIRECTORY}"/groups/matrix/

for ((k = 0; k < GroupNumber; k++)); do
    GroupK=(${ASConfig[$k]})         # group config file array
    GroupAS="${GroupK[0]}"           # AS number
    GroupType="${GroupK[1]}"         # IXP/AS
    GroupRouterConfig="${GroupK[3]}" # L3 router config file

    if [ "${GroupType}" != "IXP" ]; then

        readarray Routers < "${DIRECTORY}"/config/$GroupRouterConfig
        RouterNumber=${#Routers[@]}

        for ((i = 0; i < RouterNumber; i++)); do
            RouterI=(${Routers[$i]})      # router config file array
            RouterRegion="${RouterI[0]}"  # region name
            RouterService="${RouterI[1]}" # measurement/matrix/dns

            # record the destination IP
            if [[ "$RouterService" == "MATRIX_TARGET" ]]; then
                TargetSubnet="$(subnet_host_router ${GroupAS} ${i} "host")"
                echo $GroupAS" "${TargetSubnet%/*} >> "${MatrixConfigDir}"/destination_ips.txt
            fi

            # connect the matrix container to each group
            if [[ "$RouterService" == "MATRIX" ]]; then
                # connect_one_matrix "${GroupAS}" "${RouterRegion}"
                echo "${GroupAS}: connected MATRIX"
            fi

        done

        echo "Group ${GroupAS} connected to services."
    fi
done
