#!/bin/bash

set -o errexit
set -o pipefail
set -o nounset

create_netns_link () {
    PID="$1"
    if [ ! -e /var/run/netns ]; then
        mkdir -p /var/run/netns
    fi
    if [ ! -e /var/run/netns/"$PID" ]; then
        ln -s /proc/"$PID"/ns/net /var/run/netns/"$PID"
        trap "delete_netns_link ${PID}" 0
        for signal in 1 2 3 13 14 15; do
            trap "delete_netns_link ${PID}; trap - $signal; kill -$signal $$" $signal
        done
    fi
}

delete_netns_link () {
    PID="$1"
    rm -f /var/run/netns/"$PID"
}

get_port_name () {
    CONTAINER="$1"
    INTERFACE="$2"

    if [[ $(lsb_release -rs) == ^16* ]]; then
        ID=`echo "${INTERFACE}_${CONTAINER}" | sha1sum | sed 's/-//g'`
    else
        ID=`uuidgen -s --namespace @url --name "${INTERFACE}_${CONTAINER}" | sed 's/-//g'`
    fi
    echo "${ID:0:13}"
}

get_ctn_pid () {
    CONTAINER="$1"
    PID=$(docker inspect -f '{{.State.Pid}}' "$1")
    echo "$PID"
}

add_veth_pair () {
    CONTAINER1="$1"
    INTERFACE1="$2"
    CONTAINER2="$3"
    INTERFACE2="$4"

    PORTNAME1=$(get_port_name $CONTAINER1 $INTERFACE1)
    PORTNAME2=$(get_port_name $CONTAINER2 $INTERFACE2)

    ip link add "${PORTNAME1}_c" type veth peer name "${PORTNAME2}_c"

    PID1=$(get_ctn_pid ${CONTAINER1})
    PID2=$(get_ctn_pid ${CONTAINER2})

    # move veth interface to each container's network namespace
    ip link set netns "${PID1}" dev "${PORTNAME1}_c"
    ip link set netns "${PID2}" dev "${PORTNAME2}_c"

    create_netns_link "$PID1"
    create_netns_link "$PID2"

    ip netns exec "$PID1" ip link set dev "${PORTNAME1}_c" name "$INTERFACE1"
    ip netns exec "$PID1" ip link set "$INTERFACE1" up
    ip netns exec "$PID2" ip link set dev "${PORTNAME2}_c" name "$INTERFACE2"
    ip netns exec "$PID2" ip link set "$INTERFACE2" up
}

add_vlan_link () {
    CONTAINER="$1"
    ROUTER="$2"
    VLAN="$3"

    PID=$(get_ctn_pid ${CONTAINER})

    create_netns_link "$PID"

    ip netns exec "$PID" ip link add link "${ROUTER}-L2" name "${ROUTER}-L2.${VLAN}" type vlan id "$VLAN"
}

add_intf_addr () {
    CONTAINER="$1"
    ADDRESS="$2"
    INTERFACE="$3"

    PID=$(get_ctn_pid ${CONTAINER})

    create_netns_link "$PID"

    ip netns exec "$PID" ip addr add "$ADDRESS"/24 dev "$INTERFACE"
}

delete_veth_pair() {
    CONTAINER="$1"
    INTERFACE="$2"

    PORTNAME=$(get_port_name $CONTAINER $INTERFACE)
    ip link delete "${PORTNAME}_c" > /dev/null 2>&1
}


if [ "$1" == "add_link" ]; then
    shift
    add_veth_pair "$@"
elif [ "$1" == "delete_link" ]; then
    shift
    delete_veth_pair "$@"
elif [ "$1" == "add_addr" ]; then
    shift
    add_intf_addr "$@"
elif [ "$1" == "add_vlan" ]; then
    shift
    add_vlan_link "$@"
fi
