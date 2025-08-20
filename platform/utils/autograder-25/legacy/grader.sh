#!/usr/bin/env sh

# TODO exception handling, e.g., null ip address
# TODO how to check students' understanding of results, e.g., traceroute?
# TODO make sure pwd is grader/
# set -x

set -o errexit  # exit the script whenever there is an error code
set -o pipefail # prevent error code in pipeline from being masked
# set -o nounset  # treat attempt to an undefined variable as an error

ASN=3
echo "ASN = $ASN"
echo -e

# Q1.1
echo "########## Q1.1 ##########"
echo -e
# get host IPs
FIFA_1_IP=$(docker exec -i -w /root $ASN\_L2_DCN_FIFA_1 bash -c "ifconfig ${ASN}-S1 | awk -F' *|:' '/inet addr/{print \$4}'")
FIFA_2_IP=$(docker exec -i -w /root $ASN\_L2_DCN_FIFA_2 bash -c "ifconfig ${ASN}-S2 | awk -F' *|:' '/inet addr/{print \$4}'")
FIFA_3_IP=$(docker exec -i -w /root $ASN\_L2_DCN_FIFA_3 bash -c "ifconfig ${ASN}-S3 | awk -F' *|:' '/inet addr/{print \$4}'")
UEFA_1_IP=$(docker exec -i -w /root $ASN\_L2_DCN_UEFA_1 bash -c "ifconfig ${ASN}-S1 | awk -F' *|:' '/inet addr/{print \$4}'")
UEFA_2_IP=$(docker exec -i -w /root $ASN\_L2_DCN_UEFA_2 bash -c "ifconfig ${ASN}-S2 | awk -F' *|:' '/inet addr/{print \$4}'")
UEFA_3_IP=$(docker exec -i -w /root $ASN\_L2_DCN_UEFA_3 bash -c "ifconfig ${ASN}-S3 | awk -F' *|:' '/inet addr/{print \$4}'")

echo "IP(FIFA_1)=$FIFA_1_IP"
echo "IP(FIFA_2)=$FIFA_2_IP"
echo "IP(FIFA_3)=$FIFA_3_IP"
echo "IP(UEFA_1)=$UEFA_1_IP"
echo "IP(UEFA_2)=$UEFA_2_IP"
echo "IP(UEFA_3)=$UEFA_3_IP"
echo -e

# get host gateways
FIFA_1_GW=$(docker exec -i -w /root ${ASN}_L2_DCN_FIFA_1 bash -c "ip r | awk '/default/{print \$3}'")
FIFA_2_GW=$(docker exec -i -w /root ${ASN}_L2_DCN_FIFA_2 bash -c "ip r | awk '/default/{print \$3}'")
FIFA_3_GW=$(docker exec -i -w /root ${ASN}_L2_DCN_FIFA_3 bash -c "ip r | awk '/default/{print \$3}'")
UEFA_1_GW=$(docker exec -i -w /root ${ASN}_L2_DCN_UEFA_1 bash -c "ip r | awk '/default/{print \$3}'")
UEFA_2_GW=$(docker exec -i -w /root ${ASN}_L2_DCN_UEFA_2 bash -c "ip r | awk '/default/{print \$3}'")
UEFA_3_GW=$(docker exec -i -w /root ${ASN}_L2_DCN_UEFA_3 bash -c "ip r | awk '/default/{print \$3}'")

echo "GateWay(FIFA_1)=$FIFA_1_GW"
echo "GateWay(FIFA_2)=$FIFA_2_GW"
echo "GateWay(FIFA_3)=$FIFA_3_GW"
echo "GateWay(UEFA_1)=$UEFA_1_GW"
echo "GateWay(UEFA_2)=$UEFA_2_GW"
echo "GateWay(UEFA_3)=$UEFA_3_GW"
echo -e

# get ZURI interface to DCN
# the mask is not present as the ip address is used in inter_company_ping()
ZURI_10=$(docker exec -i -w /etc/frr ${ASN}_ZURIrouter bash -c "awk '/ZURI-L2.10/,/exit/' frr.conf | awk -F ' *|/' '/ ip address/{print \$4}'")
ZURI_20=$(docker exec -i -w /etc/frr ${ASN}_ZURIrouter bash -c "awk '/ZURI-L2.20/,/exit/' frr.conf | awk -F ' *|/' '/ ip address/{print \$4}'")

echo "IP(ZURI-L2.10)=$ZURI_10"
echo "IP(ZURI-L2.20)=$ZURI_20"
echo -e

# TODO check consistent tagging
print_vlan_info () {
    SW=$1
    DC=$2
    echo "$SW VLAN config:"
    readarray -t INPUT < <(docker exec -i -w /root ${ASN}_L2_${DC}_$SW bash -c "ovs-vsctl show | awk '/Port/,/Interface/'")
    for i in "${INPUT[@]}"
    do
        case $i in
            *"Port"*)
                CUR_PORT=$(echo $i | awk '{print $2}' | sed 's/"//g')
                ;;
            *"tag"*)
                CUR_TAG=$(echo $i | awk '{print $2}')
                echo "VLAN($CUR_PORT)=$CUR_TAG"
                ;;
            *"trunks"*)
                CUR_TRUNKS=$(echo $i | awk -F '\[|\]' '{print $2}')
                echo "VLAN($CUR_PORT)=[$CUR_TRUNKS]"
                ;;
            *)
                ;;
        esac
    done
    echo -e
}

print_vlan_info S1 DCN
print_vlan_info S2 DCN
print_vlan_info S3 DCN


PING_COUNT=1
LOSS_TOL=0

intra_company_ping () {
    PROTO=$4  # 4 or 6
    DC=$5  # DCN or DCS
    FROM=${1}_$2
    TO=${1}_$3
    TO_IP=${TO}_IP
    TO_IP6=${TO}_IP6
    # TODO handle network unreachable error
    if [ $PROTO -eq 4 ]; then
        LOSS=$(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "ping -q -c $PING_COUNT ${!TO_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
    elif [ $PROTO -eq 6 ]; then
        LOSS=$(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "ping -6 -q -c $PING_COUNT ${!TO_IP6} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
    fi
    # echo "PingLoss($FROM, $TO)=$LOSS%"
    if [ $LOSS -gt $LOSS_TOL ]; then
        echo "$FROM --> $TO: unreachable"
    else
        # check if traceroute only contains one hop
        if [ $PROTO -eq 4 ]; then
            HOP=$(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "traceroute -n ${!TO_IP} | wc -l")
        elif [ $PROTO -eq 6 ]; then
            HOP=$(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "traceroute -6 -n ${!TO_IP6} | wc -l")
        fi
        if [ $HOP -ne 2 ]; then
            echo "$FROM --> $TO: invalid traceroute"
        else
            echo "$FROM --> $TO: success"
        fi
    fi
}

# TODO refactor ipv4 and ipv6 check
inter_company_ping () {
    PROTO=$5
    DC=$6
    FROM=${1}_$2
    TO=${3}_$4
    TO_IP=${TO}_IP
    TO_IP6=${TO}_IP6
    # TODO handle network unreachable error
    if [ $PROTO -eq 4 ]; then
        LOSS=$(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "ping -q -c $PING_COUNT ${!TO_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
    elif [ $PROTO -eq 6 ]; then
        LOSS=$(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "ping -6 -q -c $PING_COUNT ${!TO_IP6} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
    fi
    # echo "PingLoss($FROM, $TO)=$LOSS%"
    if [ $LOSS -gt $LOSS_TOL ]; then
        echo "$FROM --> $TO: unreachable"
    else
        # check if traceroute only contains 2 hops, and the first hop is a gateway, which equals to ZURI's corresponding interface
        if [ $PROTO -eq 4 ]; then
            HOPS=($(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "traceroute -n ${!TO_IP} | awk '/^ [0-9]+/{print \$2}'"))
        elif [ $PROTO -eq 6 ]; then
            HOPS=($(docker exec -i -w /root ${ASN}_L2_${DC}_$FROM bash -c "traceroute -6 -n ${!TO_IP6} | awk '/^ [0-9]+/{print \$2}'"))
        fi
        if [ ${#HOPS[@]} -ne 2 ]; then
            echo "$FROM --> $TO: invalid traceroute"
        else
            HOP_1=${HOPS[0]}
            if [ "$DC" == "DCN" ]; then
                if [ $PROTO -eq 4 ]; then
                    FROM_GW=${FROM}_GW
                    if [ ${!FROM_GW} != $HOP_1 ] || ([ $HOP_1 != $ZURI_10 ] && [ $HOP_1 != $ZURI_20 ]); then
                        echo "$FROM --> $TO: invalid traceroute"
                    else
                        echo "$FROM --> $TO: success"
                    fi
                elif [ $PROTO -eq 6 ]; then
                    FROM_GW=${FROM}_GW6
                    if [ ${!FROM_GW} != $HOP_1 ] || ([ $HOP_1 != $ZURI_10_6 ] && [ $HOP_1 != $ZURI_20_6 ]); then
                        echo "$FROM --> $TO: invalid traceroute"
                    else
                        echo "$FROM --> $TO: success"
                    fi
                fi
            elif [ "$DC" == "DCS" ]; then
                # assume DCS only has ipv6 address
                FROM_GW=${FROM}_GW6
                if [ ${!FROM_GW} != $HOP_1 ] || ([ $HOP_1 != $GENE_10_6 ] && [ $HOP_1 != $GENE_20_6 ]); then
                    echo "$FROM --> $TO: invalid traceroute"
                else
                    echo "$FROM --> $TO: success"
                fi
            fi
        fi
    fi
}

# TODO only show failure or one-line full connection info
echo "Checking intra-company connection in DCN..."
intra_company_ping FIFA 1 2 4 DCN
intra_company_ping FIFA 1 3 4 DCN
intra_company_ping FIFA 2 1 4 DCN
intra_company_ping FIFA 2 3 4 DCN
intra_company_ping FIFA 3 1 4 DCN
intra_company_ping FIFA 3 2 4 DCN
echo -e

intra_company_ping UEFA 1 2 4 DCN
intra_company_ping UEFA 1 3 4 DCN
intra_company_ping UEFA 2 1 4 DCN
intra_company_ping UEFA 2 3 4 DCN
intra_company_ping UEFA 3 1 4 DCN
intra_company_ping UEFA 3 2 4 DCN
echo -e

echo "Checking inter-company connection in DCN..."
for i in {1..3}
do
    for j in {1..3}
    do
        inter_company_ping FIFA $i UEFA $j 4 DCN
    done
done
echo -e

for i in {1..3}
do
    for j in {1..3}
    do
        inter_company_ping UEFA $i FIFA $j 4 DCN
    done
done
echo -e


# Q1.2
echo "########## Q1.2 ##########"
echo -e
declare -A ROUTERS
# the index indicates the router id
ROUTERS[1]=ZURI
ROUTERS[2]=BASE
ROUTERS[3]=GENE
ROUTERS[4]=LUGA
ROUTERS[5]=MUNI
ROUTERS[6]=LYON
ROUTERS[7]=VIEN
ROUTERS[8]=MILA

# interfaces between routers
declare -A ROUTER_IFS
# initialization
for (( i=1; i<=${#ROUTERS[@]}; i++ ));
do
    for (( j=1; j<=${#ROUTERS[@]}; j++ ));
    do
        ROUTER_IFS[$i,$j]=0
    done
done

# register interfaces between routers
# e.g., ROUTER_IFS[1,2]=1 means ZURI(ROUTERS[1]) and BASE(ROUTERS[2]) are connected
# and the interfaces are ASN.0.1.1/24(port_BASE) and ASN.0.1.2/24(port_ZURI)
# the first dimension always get .1/24 and the second gets .2/24
ROUTER_IFS[1,2]=1
ROUTER_IFS[1,5]=4
ROUTER_IFS[1,3]=2
ROUTER_IFS[1,4]=3
ROUTER_IFS[1,7]=5
ROUTER_IFS[2,5]=7
ROUTER_IFS[2,3]=6
ROUTER_IFS[2,6]=8
ROUTER_IFS[3,4]=9
ROUTER_IFS[3,6]=10
ROUTER_IFS[4,7]=12
ROUTER_IFS[4,8]=11

# store hosts' ips
declare -A HOSTS

L3_IF_CORR=true
echo "Checking L3 interface configuration..."
for (( i=1; i<=${#ROUTERS[@]}; i++ ));
do
    # check router lo and interfaces between hosts and routers
    LO_IF=$(docker exec -i -w /etc/frr $ASN\_${ROUTERS[$i]}router bash -c "awk '/interface lo/,/exit/' frr.conf | awk '/ ip address/{print \$3}'")
    HOST_IF=$(docker exec -i -w /etc/frr $ASN\_${ROUTERS[$i]}router bash -c "awk '/interface host/,/exit/' frr.conf | awk '/ ip address/{print \$3}'")
    # echo "Lo(${ROUTERS[$i]}) = $LO_IF"
    # echo "Host(${ROUTERS[$i]}router) = $HOST_IF"
    if [ "$LO_IF" != "${ASN}.$((150+$i)).0.1/24" ]; then
        echo "incorrect LO(${ROUTERS[$i]}router)"
        L3_IF_CORR=false
    fi
    if [ "$HOST_IF" != "${ASN}.$((100+$i)).0.2/24" ]; then
        echo "incorrect IP(${ROUTERS[$i]}-host)"
        L3_IF_CORR=false
    fi

    HOST_IP=$(docker exec -i -w /root $ASN\_${ROUTERS[$i]}host bash -c "ifconfig ${ROUTERS[$i]}router | awk -F' *|:' '/inet addr/{print \$4}'")
    HOST_MASK=$(docker exec -i -w /root $ASN\_${ROUTERS[$i]}host bash -c "ifconfig ${ROUTERS[$i]}router | awk -F' *|:' '/inet addr/{print \$8}'")
    # echo "Ip(${ROUTERS[$i]}host) = $HOST_IP"
    # echo "Mask(${ROUTERS[$i]}host) = $HOST_MASK"
    if [ "$HOST_IP" != "${ASN}.$((100+$i)).0.1" ] || [ "$HOST_MASK" != "255.255.255.0" ]; then
        echo "incorrect IP(${ROUTERS[$i]}host)"
        L3_IF_CORR=false
    else
        HOSTS[$i]=$HOST_IP
    fi

    # check interfaces between routers
    for (( j=1; j<=${#ROUTERS[@]}; j++ ));
    do
        if [ ${ROUTER_IFS[$i,$j]} -gt 0 ]; then
            PORT_i=port_${ROUTERS[$j]}
            PORT_j=port_${ROUTERS[$i]}
            IF_i=$(docker exec -i -w /etc/frr $ASN\_${ROUTERS[$i]}router bash -c "awk '/interface ${PORT_i}/,/exit/' frr.conf | awk '/ ip address/{print \$3}'")
            IF_j=$(docker exec -i -w /etc/frr $ASN\_${ROUTERS[$j]}router bash -c "awk '/interface ${PORT_j}/,/exit/' frr.conf | awk '/ ip address/{print \$3}'")
            # echo "IP(${ROUTERS[$i]}-$PORT_i) = $IF_i"
            # echo "IP(${ROUTERS[$j]}-$PORT_j) = $IF_j"
            if [ "$IF_i" != "${ASN}.0.${ROUTER_IFS[$i,$j]}.1/24" ] || [ "$IF_j" != "${ASN}.0.${ROUTER_IFS[$i,$j]}.2/24" ]; then
                echo "incorrect IP($ROUTERS[$i]-$PORT_i)"
                L3_IF_CORR=false
            fi
        fi
    done
done

DNS_IP=198.0.0.100
# DNS_CORR=true
# no gateway for MATRIX, no net-tools for MEASUREMENT
# MATRIX_IP=${ASN}.0.198.2
# MATRIX_CORR=true
# MEASURE_IP=${ASN}.0.199.2
# MEASURE_CORR=true

# TODO contine checking even if the config is incorrect
E2E_CORR=true
if [ "$L3_IF_CORR" = true ]; then
    echo "Correct L3 interface configuration."
    echo -e
    echo "Checking end-to-end host connection..."
    # check end-to-end host traceroute
    for (( i=1; i<=${#ROUTERS[@]}; i++ ));
    do
        for (( j=$(($i+1)); j<=${#ROUTERS[@]}; j++ ));
        do
            # TODO check routes are learnt from ospf, use 'ip route' in bash may work
            LOSS=$(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "ping -q -c $PING_COUNT ${HOSTS[$j]} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
            if [ $LOSS -le $LOSS_TOL ]; then
                HOPS=($(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "traceroute -4 -n ${HOSTS[$j]} | awk '/^ [0-9]+/{print \$2}'"))
                # echo "${ROUTERS[$i]}host --> ${HOSTS[$j]}: ${#HOPS[@]} hops"
                # at least one hop is between routers and 2 hops between routers and hosts
                if [ ${#HOPS[@]} -ge 3 ]; then
                    # echo "${ROUTERS[$i]}host <--> ${ROUTERS[$j]}host: success"
                    true
                else
                    E2E_CORR=false
                    echo "${ROUTERS[$i]}host <--> ${ROUTERS[$j]}host: invalid traceroute"
                fi
            else
                echo "${ROUTERS[$i]}host <--> ${ROUTERS[$j]}host: failed"
                E2E_CORR=false
            fi
        done
        # check connection between hosts and infrastructure (i.e., dns, matrix, measurement)
        LOSS_DNS=$(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "ping -q -c $PING_COUNT ${DNS_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
        # LOSS_MATRIX=$(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "ping -q -c $PING_COUNT ${MATRIX_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
        # LOSS_MEASURE=$(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "ping -q -c $PING_COUNT ${MEASURE_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
        if [ $LOSS_DNS -gt $LOSS_TOL ]; then
            echo "${ROUTERS[$i]}host <--> DNS: failed"
            # DNS_CORR=false
            E2E_CORR=false
        else
            # echo "${ROUTERS[$i]}host <--> DNS: success"
            true
        fi
        # if [ $LOSS_MATRIX -gt $LOSS_TOL ]; then
        #     echo "${ROUTERS[$i]}host <--> MATRIX: failed"
        #     MATRIX_CORR=false
        # fi
        # if [ $LOSS_MEASURE -gt $LOSS_TOL ]; then
        #     echo "${ROUTERS[$i]}host <--> MEASURE: failed"
        #     MEASURE_CORR=false
        # fi
        # check connection with DCN
        for (( k=1;  k<=3; k++ ));
        do
            FIFA_IP=FIFA_${k}_IP
            UEFA_IP=UEFA_${k}_IP
            LOSS_FIFA=$(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "ping -q -c $PING_COUNT ${!FIFA_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
            LOSS_UEFA=$(docker exec -i -w /root ${ASN}_${ROUTERS[$i]}host bash -c "ping -q -c $PING_COUNT ${!UEFA_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
            if [ $LOSS_FIFA -le $LOSS_TOL ]; then
                # echo "${ROUTERS[$i]}host <--> FIFA_$k: success"
                true
            else
                echo "${ROUTERS[$i]}host <--> FIFA_$k: failed"
                E2E_CORR=false
            fi
            if [ $LOSS_UEFA -le $LOSS_TOL ]; then
                # echo "${ROUTERS[$i]}host <--> UEFA_$k: success"
                true
            else
                echo "${ROUTERS[$i]}host <--> UEFA_$k: failed"
                E2E_CORR=false
            fi
        done
    done
    if [ "$E2E_CORR" = true ]; then
        echo "Full connection among ent-to-end hosts."
        # print a random traceroute result with DNS resolution
            RANDOM_HOSTS=($(shuf -i 1-${#ROUTERS[@]} -n 2))
            FROM=${RANDOM_HOSTS[0]}
            TO=${RANDOM_HOSTS[1]}
            echo -e
            echo "Printing random traceroute trace: ${ROUTERS[$FROM]}host -> ${ROUTERS[$TO]}host..."
            readarray -t TRACE <<<$(docker exec -i -w /root ${ASN}_${ROUTERS[$FROM]}host bash -c "traceroute -4 ${HOSTS[$TO]} | awk '/^ [0-9]+/{print}'")
            printf '%s\n' "${TRACE[@]}"
    fi
    echo -e

fi
echo -e


# Q1.3
echo "########## Q1.3 ##########"
echo -e
# collect ospf cost on each interface
# TODO check BASE does not use DCN
# TODO check no external network is used, is it enough to print traceroute trace?
declare -A OSPF
# initialization
for (( i=1; i<=${#ROUTERS[@]}; i++ ));
do
    for (( j=$i; j<=${#ROUTERS[@]}; j++ ));
    do
        if [ ${ROUTER_IFS[$i,$j]} -gt 0 ]; then
            # default cost is 10
            OSPF[$i,$j]=10
            OSPF[$j,$i]=10
        else
            OSPF[$i,$j]=0
            OSPF[$j,$i]=0
        fi
    done
done

# update weights if specified in config
# echo "Printing modified OSPF weights..."
for (( i=1; i<=${#ROUTERS[@]}; i++ ));
do
    for (( j=1; j<=${#ROUTERS[@]}; j++ ));
    do
        if [ ${OSPF[$i,$j]} -gt 0 ]; then
            PORT_j=port_${ROUTERS[$j]}
            OSPF_j=$(docker exec -i -w /etc/frr $ASN\_${ROUTERS[$i]}router bash -c "awk '/interface ${PORT_j}/,/exit/' frr.conf | awk '/ ip ospf/{print \$4}'")
            if [ "$OSPF_j" != "" ]; then
                OSPF[$i,$j]=${OSPF_j}
                # echo "OSPF(${ROUTERS[$i]}, ${ROUTERS[$j]}) = ${OSPF[$i,$j]}"
            fi
        fi
    done
done

# store OSPF and routers array to file
rm -f ospf_arr.txt
rm -f router_arr.txt
for (( i=1; i<=${#ROUTERS[@]}; i++ ));
do
    printf "${ROUTERS[$i]} " >> router_arr.txt
    for (( j=1; j<=${#ROUTERS[@]}; j++ ));
    do
        printf "${OSPF[$i,$j]} " >> ospf_arr.txt
    done
    printf "\n" >> ospf_arr.txt
done
printf "\n" >> router_arr.txt

# parse to python script to compute shortest paths
echo "Checking load balancing between MUNI and MILA, and between ZURI and GENE..."
source venv/bin/activate
SP=$(python sp.py ../config/l3_links.txt ./ospf_arr.txt ./router_arr.txt MUNI MILA ZURI GENE)
deactivate

# echo "$SP"
LB_CORR=true
SP_MILA_2_MUNI=$(echo "$SP" | awk -F ':' '/SP\(MILA, MUNI\)/{print $2}')
SP_MUNI_2_MILA=$(echo "$SP" | awk -F ':' '/SP\(MUNI, MILA\)/{print $2}')
SP_ZURI_2_GENE=$(echo "$SP" | awk -F ':' '/SP\(ZURI, GENE\)/{print $2}')
SP_GENE_2_ZURI=$(echo "$SP" | awk -F ':' '/SP\(GENE, ZURI\)/{print $2}')
# TODO consider more intelligent pattern match, is the networkx output deterministic?
EXP_SP_MILA_2_MUNI=" [['MILA', 'LUGA', 'ZURI', 'MUNI'], ['MILA', 'LUGA', 'GENE', 'BASE', 'ZURI', 'MUNI']]"
EXP_SP_MUNI_2_MILA=" [['MUNI', 'ZURI', 'LUGA', 'MILA'], ['MUNI', 'ZURI', 'BASE', 'GENE', 'LUGA', 'MILA']]"
EXP_SP_ZURI_2_GENE=" [['ZURI', 'BASE', 'GENE']]"
EXP_SP_GENE_2_ZURI=" [['GENE', 'BASE', 'ZURI']]"
if [ "$SP_MILA_2_MUNI" == "$EXP_SP_MILA_2_MUNI" ] && [ "$SP_MUNI_2_MILA" == "$EXP_SP_MUNI_2_MILA" ] &&
       [ "$SP_ZURI_2_GENE" == "$EXP_SP_ZURI_2_GENE" ] && [ "$SP_GENE_2_ZURI" == "$EXP_SP_GENE_2_ZURI" ]; then
    echo "Correct load balancing configuration."
else
    echo "Incorrect load balancing configuration."
    LB_CORR=false
fi
echo -e

# print 2 random traceroute from MILA to MUNI
# and 1 traceroute from ZURI to GENE
if [ "$LB_CORR" == true ]; then
    echo "Printing 2 traceroute traces: MILAhost -> MUNIhost..."
    readarray -t TRACE <<<$(docker exec -i -w /root ${ASN}_MILAhost bash -c "traceroute -4 ${HOSTS[5]} | awk '/^ [0-9]+/{print}'")
    printf '%s\n' "${TRACE[@]}"
    echo -e
    readarray -t TRACE <<<$(docker exec -i -w /root ${ASN}_MILAhost bash -c "traceroute -4 ${HOSTS[5]} | awk '/^ [0-9]+/{print}'")
    printf '%s\n' "${TRACE[@]}"
    echo -e
    echo "Printing 1 traceroute trace: ZURIhost -> GENEhost (w/o DNS resolution)..."
    # ZURI_GENE_TRACE can be reused in Q1.6, so we need pure IP address here
    readarray -t ZURI_GENE_TRACE <<<$(docker exec -i -w /root ${ASN}_ZURIhost bash -c "traceroute -4 -n ${HOSTS[3]} | awk '/^ [0-9]+/{print}'")
    printf '%s\n' "${ZURI_GENE_TRACE[@]}"
fi
echo -e


# # Q1.5
echo "########## Q1.5 ##########"
echo -e
# # get DC host ipv6
FIFA_1_IP6=$(docker exec -i -w /root $ASN\_L2_DCN_FIFA_1 bash -c "ifconfig ${ASN}-S1 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")
FIFA_2_IP6=$(docker exec -i -w /root $ASN\_L2_DCN_FIFA_2 bash -c "ifconfig ${ASN}-S2 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")
FIFA_3_IP6=$(docker exec -i -w /root $ASN\_L2_DCN_FIFA_3 bash -c "ifconfig ${ASN}-S3 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")
FIFA_4_IP6=$(docker exec -i -w /root $ASN\_L2_DCS_FIFA_4 bash -c "ifconfig ${ASN}-S4 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")

UEFA_1_IP6=$(docker exec -i -w /root $ASN\_L2_DCN_UEFA_1 bash -c "ifconfig $[ASN}-S1 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")
UEFA_2_IP6=$(docker exec -i -w /root $ASN\_L2_DCN_UEFA_2 bash -c "ifconfig ${ASN}-S2 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")
UEFA_3_IP6=$(docker exec -i -w /root $ASN\_L2_DCN_UEFA_3 bash -c "ifconfig $[ASN}-S3 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")
UEFA_4_IP6=$(docker exec -i -w /root $ASN\_L2_DCS_UEFA_4 bash -c "ifconfig ${ASN}-S4 | awk -F ' *|/' '/inet6 addr.*Scope:Global/{print \$4}'")

echo "IP6(FIFA_1)=$FIFA_1_IP6"
echo "IP6(FIFA_2)=$FIFA_2_IP6"
echo "IP6(FIFA_3)=$FIFA_3_IP6"
echo "IP6(FIFA_4)=$FIFA_4_IP6"
echo -e
echo "IP6(UEFA_1)=$UEFA_1_IP6"
echo "IP6(UEFA_2)=$UEFA_2_IP6"
echo "IP6(UEFA_3)=$UEFA_3_IP6"
echo "IP6(UEFA_4)=$UEFA_4_IP6"
echo -e

# # get host ipv6 gateways
FIFA_1_GW6=$(docker exec -i -w /root ${ASN}_L2_DCN_FIFA_1 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")
FIFA_2_GW6=$(docker exec -i -w /root ${ASN}_L2_DCN_FIFA_1 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")
FIFA_3_GW6=$(docker exec -i -w /root ${ASN}_L2_DCN_FIFA_1 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")
FIFA_4_GW6=$(docker exec -i -w /root ${ASN}_L2_DCS_FIFA_4 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")

UEFA_1_GW6=$(docker exec -i -w /root ${ASN}_L2_DCN_UEFA_1 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")
UEFA_2_GW6=$(docker exec -i -w /root ${ASN}_L2_DCN_UEFA_2 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")
UEFA_3_GW6=$(docker exec -i -w /root ${ASN}_L2_DCN_UEFA_3 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")
UEFA_4_GW6=$(docker exec -i -w /root ${ASN}_L2_DCS_UEFA_4 bash -c "ip -6 route show default | awk '/default via/{print \$3}'")

echo "GateWay6(FIFA_1)=$FIFA_1_GW6"
echo "GateWay6(FIFA_2)=$FIFA_2_GW6"
echo "GateWay6(FIFA_3)=$FIFA_3_GW6"
echo "GateWay6(FIFA_4)=$FIFA_4_GW6"
echo -e
echo "GateWay6(UEFA_1)=$UEFA_1_GW6"
echo "GateWay6(UEFA_2)=$UEFA_2_GW6"
echo "GateWay6(UEFA_3)=$UEFA_3_GW6"
echo "GateWay6(UEFA_4)=$UEFA_4_GW6"
echo -e

# # get ZURI and GENE ipv6 interface to DCN
ZURI_10_6=$(docker exec -i -w /etc/frr 1_ZURIrouter bash -c "awk '/ZURI-L2.10/,/exit/' frr.conf | awk -F ' *|/' '/ ipv6 address/{print \$4}'")
ZURI_20_6=$(docker exec -i -w /etc/frr 1_ZURIrouter bash -c "awk '/ZURI-L2.20/,/exit/' frr.conf | awk -F ' *|/' '/ ipv6 address/{print \$4}'")
GENE_10_6=$(docker exec -i -w /etc/frr 1_GENErouter bash -c "awk '/GENE-L2.10/,/exit/' frr.conf | awk -F ' *|/' '/ ipv6 address/{print \$4}'")
GENE_20_6=$(docker exec -i -w /etc/frr 1_GENErouter bash -c "awk '/GENE-L2.20/,/exit/' frr.conf | awk -F ' *|/' '/ ipv6 address/{print \$4}'")

echo "IP6(ZURI-L2.10)=$ZURI_10_6"
echo "IP6(ZURI-L2.20)=$ZURI_20_6"
echo "IP6(GENE-L2.10)=$GENE_10_6"
echo "IP6(GENE-L2.20)=$GENE_20_6"
echo -e

# print S4 VLAN config
print_vlan_info S4 DCS

# check ipv6 connection within DCN or DCS
# TODO compress it
echo "Checking intra-company Ipv6 connection in DC..."
intra_company_ping FIFA 1 2 6 DCN
intra_company_ping FIFA 1 3 6 DCN
intra_company_ping FIFA 2 1 6 DCN
intra_company_ping FIFA 2 3 6 DCN
intra_company_ping FIFA 3 1 6 DCN
intra_company_ping FIFA 3 2 6 DCN
echo -e

intra_company_ping UEFA 1 2 6 DCN
intra_company_ping UEFA 1 3 6 DCN
intra_company_ping UEFA 2 1 6 DCN
intra_company_ping UEFA 2 3 6 DCN
intra_company_ping UEFA 3 1 6 DCN
intra_company_ping UEFA 3 2 6 DCN
echo -e

echo "Checking inter-company Ipv6 connection in DC..."
for i in {1..3}
do
    for j in {1..3}
    do
        inter_company_ping FIFA $i UEFA $j 6 DCN
    done
done
inter_company_ping FIFA 4 UEFA 4 6 DCS
echo -e

for i in {1..3}
do
    for j in {1..3}
    do
        inter_company_ping UEFA $i FIFA $j 6 DCN
    done
done
inter_company_ping UEFA 4 FIFA 4 6 DCS
echo -e

# get tunnel name of ZURI and GENE router
declare -A TUN_DEVS
# store tunnel remote address, may be used in Q1.6
declare -A TUN_REMOTE

# TODO is it necessary to use loopback address?
print_tunnel_info () {
    ROUTER=$1
    TUN_CORR=false
    readarray -t TUN_INFO < <(docker exec -i -w /root ${ASN}_${ROUTER}router bash -c "ip tunnel show | awk '{print}'")
    if [ $ROUTER == "ZURI" ]; then
        readarray -t TUN_ROUTE < <(docker exec -i -w /root ${ASN}_${ROUTER}router bash -c "ip -6 route | awk '/${ASN}:201/{print}'")
    elif [ $ROUTER == "GENE" ]; then
        readarray -t TUN_ROUTE < <(docker exec -i -w /root ${ASN}_${ROUTER}router bash -c "ip -6 route | awk '/${ASN}:200/{print}'")
    fi
    for i in "${TUN_INFO[@]}"
    do
        TUN_DEV=$(echo $i | awk -F ':' '{print $1}')
        if [ "$TUN_DEV" != 'sit0' ]; then
            # print tunnel config
            REMOTE_ADDR=$(echo "$i" | awk '/remote/{print $4}')
            LOCAL_ADDR=$(echo "$i" | awk '/local/{print $6}')
            TUN_REMOTE[$ROUTER]=$REMOTE_ADDR
            echo "TunnelDev(${ROUTER})=$TUN_DEV, remote=$REMOTE_ADDR, local=$LOCAL_ADDR"
            echo -e
            echo "Printing ipv6 route info at ${ROUTER}:"
            printf ' %s\n' "${TUN_ROUTE[@]}"
            echo -e
            # check remote and local addresses == lo
            # TODO do not hardcord Ip address
            if ([ "$ROUTER" == "ZURI" ] && ([ "$REMOTE_ADDR" != "${ASN}.153.0.1" ] || [ "$LOCAL_ADDR" != "${ASN}.151.0.1" ])) ||
               ([ "$ROUTER" == "GENE" ] && ([ "$REMOTE_ADDR" != "${ASN}.151.0.1" ] || [ "$LOCAL_ADDR" != "${ASN}.153.0.1" ])); then
                true
                # echo "$ROUTER-$TUN_DEV: incorrect tunnel address config"
            else
                # TODO consider multiple devices used?
                TUN_DEVS[$ROUTER]=$TUN_DEV
                TUN_CORR=true
                break
            fi
        fi
    done
    if [ "$TUN_CORR" == false ]; then
        echo "Tunnel($ROUTER): incorrect tunnel setup"
    fi
}

print_tunnel_info ZURI
print_tunnel_info GENE

# check whether cross DC traffic goes via tunnel
echo "Checking connection across DC..."
TUN_CORR=true
ZURI_TUN6=$(docker exec -i -w /root ${ASN}_ZURIrouter bash -c "ip -6 route | awk '/1:201/{print \$3}'")
if [ "${TUN_DEVS[ZURI]}" != "" ]; then
       if [ "$ZURI_TUN6" != "${TUN_DEVS[ZURI]}" ]; then
           echo "Tunnel(ZURI): incorrect tunnel route"
           TUN_CORR=false
       fi
fi
GENE_TUN6=$(docker exec -i -w /root ${ASN}_GENErouter bash -c "ip -6 route | awk '/1:200/{print \$3}'")
if [ "${TUN_DEVS[GENE]}" != "" ]; then
       if [ "$GENE_TUN6" != "${TUN_DEVS[GENE]}" ]; then
           echo "Tunnel(ZURI): incorrect tunnel route"
           TUN_CORR=false
       fi
fi


# check and print traceroute between random hosts across two DCs
# set -x
if [ "$TUN_CORR" == true ]; then
    # check full connection
    DC_FULL_CONN=true
    for FROM_COMP in FIFA UEFA;
    do
        for (( FROM_NO=1; FROM_NO<=3; FROM_NO++ ));
        do
            for TO_COMP in FIFA UEFA;
            do

                TO_IP=${TO_COMP}_4_IP6
                LOSS=$(docker exec -i -w /root ${ASN}_L2_DCN_${FROM_COMP}_${FROM_NO} bash -c "ping -6 -q -c $PING_COUNT ${!TO_IP} 2>&1 | awk -F ' *|%' '/loss/{print \$6}'")
                if [ $LOSS -gt $LOSS_TOL ]; then
                    echo "${FROM_COMP}_${FROM_NO} --> ${TO_COMP}_4: unreachable"
                    DC_FULL_CONN=false
                else
                    HOPS=($(docker exec -i -w /root ${ASN}_L2_DCN_${FROM_COMP}_${FROM_NO} bash -c "traceroute -6 -n ${!TO_IP} | awk '/^ [0-9]+/{print \$2}'"))
                    if [ ${#HOPS[@]} -ne 3 ]; then
                        echo "${FROM_COMP}_${FROM_NO} --> ${TO_COMP}_4: invalid traceroute"
                        DC_FULL_CONN=false
                    else
                        # check traceroute is correct
                        EXP_HOP_1=${FROM_COMP}_${FROM_NO}_GW6
                        # TODO second hop depends on the src vlan tag, need to store vlan tag mapping before
                        # now just check first and last hops
                        # EXP_HOP_2=${TO_COMP}_4_GW6
                        EXP_HOP_3=${TO_COMP}_4_IP6
                        if [ "${!EXP_HOP_1}" != "${HOPS[0]}" ] || [ "${!EXP_HOP_3}" != "${HOPS[2]}" ]; then
                            echo "${FROM_COMP}_${FROM_NO} --> ${TO_COMP}_4: invalid traceroute path"
                            DC_FULL_CONN=false
                        else
                            echo "${FROM_COMP}_${FROM_NO} --> ${TO_COMP}_4: success"
                        fi
                    fi
                fi
            done
        done
    done

    if [ "$DC_FULL_CONN" == true ]; then
        echo "Full connection across DCs."
        echo -e
        # print random traceroute trace
        FROM_COMP=$(( $RANDOM % 2 + 1 ))
        if [ $FROM_COMP -eq 1 ]; then
            FROM_COMP=FIFA
        else
            FROM_COMP=UEFA
        fi
        FROM_NO=$(( $RANDOM % 3 + 1 ))
        TO_COMP=$(( $RANDOM % 2 + 1 ))
        if [ $TO_COMP -eq 1 ]; then
            TO_COMP=FIFA
        else
            TO_COMP=UEFA
        fi
        TO_IP=${TO_COMP}_4_IP6
        readarray -t TRACE < <(docker exec -i -w /root ${ASN}_L2_DCN_${FROM_COMP}_${FROM_NO} bash -c "traceroute -6 -n ${!TO_IP} | awk '/^ [0-9]+/{print}'")
        echo "Printing random traceroute trace ${FROM_COMP}_${FROM_NO} --> ${TO_COMP}_4:"
        printf '%s\n' "${TRACE[@]}"
        # the print of tcpdump result is moved to Q1.6
    fi
fi
echo -e

# Q1.6
echo "########## Q1.6 ##########"
echo -e

# check traceroute between ZURI_host and GENE_host is still via BASE
# traceroute from ZURI to GENE has been printed in Q1.3, but not checked (only checked shortest paths)
# TODO remove hard-coded ZURI and BASE IPs
GENE_ZURI_HOPS=($(docker exec -i -w /root ${ASN}_GENEhost bash -c "traceroute -n ${HOSTS[1]} | awk '/^ [0-9]+/{print \$2}'"))
ZURI_GENE_HOPS=($(printf '%s\n' "${ZURI_GENE_TRACE[@]}" | awk '/^ [0-9]+/{print $2}'))
ZURI_GENE_LB=true
if [ ${#GENE_ZURI_HOPS[@]} -ne 4 ] || [ "${GENE_ZURI_HOPS[1]}" != "${ASN}.0.6.1" ]; then
    # check traceroute between ZURI and GENE is still via BASE
    echo "GENE -> ZURI: not take desired path."
    ZURI_GENE_LB=false
fi

if [ ${#ZURI_GENE_HOPS[@]} -ne 4 ] || [ "${ZURI_GENE_HOPS[1]}" != "${ASN}.0.1.2" ]; then
    echo "ZURI -> GENE: not take desired path."
    ZURI_GENE_LB=false
fi
if [ $ZURI_GENE_LB == "true" ]; then
    echo "Connection between ZURIhost and GENEhost follows intended paths."
    echo -e
fi

# check output of tcpdump at ZURI:port_GENE for DC communication
if [ "$DC_FULL_CONN" == true ]; then
    # pick another random DC host pairs
    FROM_COMP=$(( $RANDOM % 2 + 1 ))
    if [ $FROM_COMP -eq 1 ]; then
        FROM_COMP=FIFA
    else
        FROM_COMP=UEFA
    fi
    FROM_NO=$(( $RANDOM % 3 + 1 ))
    TO_COMP=$(( $RANDOM % 2 + 1 ))
    if [ $TO_COMP -eq 1 ]; then
        TO_COMP=FIFA
    else
        TO_COMP=UEFA
    fi
    TO_IP=${TO_COMP}_4_IP6
    # print tcpdump result, 6 pings should be enough
    sudo docker exec -d -w /root ${ASN}_L2_DCN_${FROM_COMP}_${FROM_NO} bash -c "ping -6 -c 6 ${!TO_IP}"
    # 15s for tcpdump is not enough
    echo "Collecting tcpdump result (20 sec) at port ZURI:port_GENE:"
    readarray -t TCPDUMP < <(sudo docker exec -i -w /root ${ASN}_ZURIrouter bash -c "timeout 20 tcpdump -i port_GENE" 2> /dev/null | awk -v pat=${!TO_IP} '$0~pat' | tail -n 4)
    printf ' %s\n' "${TCPDUMP[@]}"
    if [ ${#TCPDUMP[@]} -gt 0 ]; then
        echo -e
        echo "Connection between DCs follows intended paths."
    fi
fi
echo -e

# print static route configuration
# TODO is static route the unique solution?
echo "Printing static route configuration in ZURIrouter..."
readarray -t ZURI_STATIC <<<$(docker exec -i -w /etc/frr 1_ZURIrouter bash -c "awk '/^ip route /{print}' < frr.conf")
printf ' %s\n' "$ZURI_STATIC"
echo -e
echo "Printing static route configuration in GENErouter..."
readarray -t GENE_STATIC <<<$(docker exec -i -w /etc/frr 1_GENErouter bash -c "awk '/^ip route /{print}' < frr.conf")
printf ' %s\n' "$GENE_STATIC"
echo -e

declare -A ROUTER_LO
for (( i=1; i<=${#ROUTERS[@]}; i++ ));
do
    ROUTER_LO[$i]=${ASN}.$((150+$i)).0.1
done

