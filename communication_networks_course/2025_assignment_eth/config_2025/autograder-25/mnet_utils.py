#!/usr/bin/env python3

"""Inner functions to interact with mini-internet."""

import json
import os
import re
from collections import defaultdict, namedtuple
from multiprocessing import Process, Queue
from functools import partial

from ctn_utils import exec_ctn
from other_utils import (
    compute_all_shortest_paths,
    create_graph_from_link_cost,
    is_v6_subnet,
    mask_to_cidr,
    is_within_v4_subnet,
    new_print,
)

####################################################
################# EXP CONFIG SETUP##################
####################################################

# TODO: parse names from config file
REGION_NAMES = ["BIRM", "FRAN", "MUNI", "ZURI", "LYON", "MILA", "BARC", "NAPL"]

REGION_NAME_TO_ID = {
    "BIRM": 1,
    "FRAN": 2,
    "MUNI": 3,
    "ZURI": 4,
    "LYON": 5,
    "MILA": 6,
    "BARC": 7,
    "NAPL": 8,
}

REGION_ID_TO_NAME = {v: k for k, v in REGION_NAME_TO_ID.items()}

ROUTER_LINK_TO_ID = {
    ("BIRM", "BARC"): 1,
    ("BIRM", "LYON"): 2,
    ("BIRM", "FRAN"): 3,
    ("FRAN", "ZURI"): 4,
    ("FRAN", "MUNI"): 5,
    ("LYON", "NAPL"): 6,
    ("LYON", "ZURI"): 7,
    ("ZURI", "MILA"): 8,
    ("ZURI", "MUNI"): 9,
    ("MUNI", "MILA"): 10,
    ("MILA", "NAPL"): 11,
    ("BARC", "NAPL"): 12,
}

ROUTER_ID_TO_LINK = {v: k for k, v in ROUTER_LINK_TO_ID.items()}

L2_DCN_HOST_NAMES = ["A_TUM", "S_TUM"]

L2_COMP_NAME_1 = "A"

L2_COMP_NAME_2 = "S"

L2_DCN_REGION_NAMES = ["TUM"]

L2_DCS_HOST_NAMES = ["A_MIL", "S_MIL", "A_POL", "S_POL"]
L2_DCS_REGION_NAMES = ["MIL", "POL"]

L2_HOST_NAMES = L2_DCN_HOST_NAMES + L2_DCS_HOST_NAMES

L2_DCN_SW_NAMES = ["S1"]

L2_DCS_SW_NAMES = ["S2","S3"]

L2_SW_NAMES = L2_DCN_SW_NAMES + L2_DCS_SW_NAMES

L2_REGION_TO_SW = {"TUM": 1, "MIL": 2, "POL": 3}

L3_EXP_MASK_LEN = 24

L2_DCN_GW_R = "MUNI"

L2_DCS_GW_R = "MILA"

L2_DCN_CONN_R = ["MUNI"]

L2_SW_CONN = [("S2", "S3")]

L2_L3_CONN = [("S1", "MUNI"), ("S2", "MILA")]

TUNNEL_REGIONS = ["MUNI", "MILA"]

VLAN_TAGS = {10, 20}

SERVICES = ["dns", "matrix", "measurement"]

DNS_IP4 = "198.0.0.100"

MAX_OSPF_COST = 65535

# TODO: update it
MAX_ZONE = 6
AS_NUM_PER_ZONE = 12
MAX_AS = 112
START_IXP = 140

# maximum ping loss tolerated
LOSS_TH = 25

# PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# AS_INFO_PATH = os.path.join(PARENT_DIR, "config/aslevel_links_students.txt")

AS_INFO_PATH = os.path.join(os.getcwd(), "configs/aslevel_links_students.txt")

NB_CONN = {
    "PROV1": "BIRM",
    "PROV2": "FRAN",
    "CUST1": "BARC",
    "CUST2": "NAPL",
    "PEER1": "MUNI",
    "IXP": "LYON",
}

SD_CTN_PREFIX = "SD"

ROUTINATOR_R = "ZURI"
BGP_CONV_WAIT = 20


def get_ixp_intf(asn):
    """Return the static IXP ip on interface IXP."""
    return f"180.{asn}.0.{asn}/24"




def parse_as_conn_info():
    """
    Parse AS level connection info.

    I.e., link intfs and relations and IXP lists.
    """
    conn = defaultdict(lambda: defaultdict(list))
    ixps = set()
    with open(AS_INFO_PATH, "r") as f:
        for line in f:
            as_a, r_a, _, as_b, r_b, role_b, ip = line.split()
            if r_a == "None":
                r_a = "IXP"
                ixps.add(int(as_a))
            if r_b == "None":
                r_b = "IXP"
                ixps.add(int(as_b))
            conn[int(as_a)][r_a].append((int(as_b), r_b, role_b, ip))

    return conn, ixps


# {1: {'ZURI': (2, 'MUNI', 'Customer', '179.0.41.1/24')}}
# means MUNI of AS 2 is a customer of ZURI of AS 1, and ZURI of AS 1
# should have 179.0.41.1/24 on its ext_2_MUNI interface
AS_CONN_INFO, IXP_ASNS = parse_as_conn_info()


def get_as_to_zone(asn):
    """Return the zone number given the asn."""
    if AS_NUM_PER_ZONE <= 10:
        return asn // 10 + 1
    else:
        assert AS_NUM_PER_ZONE <= 20
        return asn // 20 + 1

def get_as_to_ixp(asn):
    """
    Return the connected IXP of an AS.
    """
    as_zone = get_as_to_zone(asn)
    # if the as number is odd, the ixp is START_IXP + as_zone
    if asn % 2 == 1:
        return START_IXP + as_zone
    else:
        # (as_zone + 1) % 7 + START_IXP
        return (as_zone % MAX_ZONE + 1) + START_IXP


def get_zone_to_as_lst(zone):
    """Returns a list asns in the given zone."""
    assert zone <= MAX_ZONE
    if zone == 7:
        return [i for i in range(121, 136) if i != 127]
    interval = 10 if AS_NUM_PER_ZONE <= 10 else 20
    start = (zone - 1) * interval + 1
    return list(range(start, start + AS_NUM_PER_ZONE))


def get_ixp_tranit_asns(asn):
    """Return the allowed transit asns via IXP."""
    asn_zone = get_as_to_zone(asn)
    interval = 10 if AS_NUM_PER_ZONE <= 10 else 20
    if asn % 2 == 1:
        peer_zone = MAX_ZONE if (asn_zone - 1) == 0 else asn_zone - 1
        start = (peer_zone - 1) * interval + 2
        if peer_zone == 7:
            return [122, 124, 126, 129, 131, 133, 135]
        return list(range(start, start + AS_NUM_PER_ZONE, 2))
    else:
        peer_zone = 1 if (asn_zone + 1) > MAX_ZONE else asn_zone + 1
        if peer_zone == 7:
            return [121, 123, 125, 128, 130, 132, 134]
        start = (peer_zone - 1) * interval + 1
        return list(range(start, start + AS_NUM_PER_ZONE, 2))


def get_exp_ext_conn(asn):
    """Return the dictionary of expected external links and relations."""
    return AS_CONN_INFO[asn]


def get_exp_service_intf(asn, service):
    """Return expected service interface used in mini-internet."""
    if service == "dns":
        return "KINS", f"dns_{asn}", f"198.{asn}.0.1/24"
    if service == "matrix":
        return "LUAN", f"matrix_{asn}", f"{asn}.0.198.1/24"
    if service == "measurement":
        return "NAIR", f"measurement_{asn}", f"{asn}.0.199.1/24"


def get_exp_intf_ip(addr_type, asn, r_name, other_r_name=""):
    """Return expected interface ip, the subnet is always /24."""

    def router_lo():
        if asn in IXP_ASNS:
            return f"180.80.{asn}.0"
        tmp = 150 + REGION_NAME_TO_ID[r_name]
        return f"{asn}.{tmp}.0.1"

    def router_ip():
        tmp = 100 + REGION_NAME_TO_ID[r_name]
        return f"{asn}.{tmp}.0.2"

    def router_host():
        tmp = 100 + REGION_NAME_TO_ID[r_name]
        return f"{asn}.{tmp}.0.1"

    def router_router():
        assert other_r_name in REGION_NAMES
        if (r_name, other_r_name) in ROUTER_LINK_TO_ID:
            return f"{asn}.0.{ROUTER_LINK_TO_ID[(r_name, other_r_name)]}.1"
        assert (other_r_name, r_name) in ROUTER_LINK_TO_ID
        return f"{asn}.0.{ROUTER_LINK_TO_ID[(other_r_name, r_name)]}.2"

    def router_ext_nb():
        # print(asn)
        assert r_name in AS_CONN_INFO[asn]
        for nb in AS_CONN_INFO[asn][r_name]:
            if nb[1] == other_r_name:
                return nb[3].split("/")[0]

    if addr_type == "lo":
        return router_lo()
    if addr_type == "ip":
        # returns the router ip connecting to the host
        return router_ip()
    if addr_type == "host":
        # returns the host ip connecting to the router
        return router_host()

    if addr_type == "router":
        # returns the router ip connecting to another router
        return router_router()

    if addr_type == "ext":
        # return the ip connecting to ext nb
        # NOTE: this returns wildcard for student AS
        return router_ext_nb()


def get_r_ctn_name(asn, r_name):
    """Return the ctn name of a router."""
    # TODO: better format default asn
    asn = SD_CTN_PREFIX
    assert r_name in REGION_NAMES
    return f"{asn}_{r_name}router"


def get_h_ctn_name(asn, name):
    """
    Return the ctn name of a host.

    The host can be either a region or l2 host name.
    """
    asn = SD_CTN_PREFIX
    if name in REGION_NAMES:
        return f"{asn}_{name}host"
    elif name in L2_DCN_HOST_NAMES:
        return f"{asn}_L2_L2N_{name}"
    else:
        assert name in L2_DCS_HOST_NAMES
        return f"{asn}_L2_L2S_{name}"


def get_s_ctn_name(asn, s_name):
    """Return the ctn name of a swtich."""
    asn = SD_CTN_PREFIX
    if s_name in L2_DCN_SW_NAMES:
        return f"{asn}_L2_L2N_{s_name}"
    elif s_name in L2_DCS_SW_NAMES:
        return f"{asn}_L2_L2S_{s_name}"


def get_ext_intf_names(asn, nb_name):
    """Return the intf names of the ext link on both ends."""
    nb_asn, nb_r = get_nb_asn_r(asn, nb_name)
    if nb_asn not in IXP_ASNS:
        intf_r = f"ext_{nb_asn}_{nb_r}"
        intf_nb = f"ext_{asn}_{NB_CONN[nb_name]}"
    else:
        intf_r = f"ixp_{nb_asn}"
        intf_nb = f"grp_{asn}"
    return intf_r, intf_nb


# for cache, {(3, 'PROV1'): (1, 'ZURI')}
# means AS 3's PROV is ZURI of AS 1
nb_exp_asn = {}


def get_nb_asn_r(asn, nb_name):
    """Return the neighbor ASN and region given the current asn and nb name."""
    # NOTE: assume only student asn will be passed
    assert nb_name in NB_CONN
    if (asn, nb_name) not in nb_exp_asn:
        as_conn = get_exp_ext_conn(asn)
        r_name = NB_CONN[nb_name]
        assert len(as_conn[r_name]) == 1
        nb_exp_asn[(asn, nb_name)] = (as_conn[r_name][0][0], as_conn[r_name][0][1])
    return nb_exp_asn[(asn, nb_name)]


####################################################
################# CTLPLANE QUERY####################
####################################################
##### JSON QUERY ######
# router control plane cache
r_bgp_nb_json = {}
r_intf_json = {}
r_ospf_intf_json = {}
net_ospf_graph = {}
r_route_json = {}
r_fib_json = {}
r_bgp_r_json = {}


def get_bgp_nb_json(asn, r_name, new=False):
    """Return the json file of `show ip bgp neighbors json`."""
    if (asn, r_name) not in r_bgp_nb_json or new:
        ctn_name = get_r_ctn_name(asn, r_name)
        cmd = ["show bgp neighbors json"]
        r_bgp_nb_json[(asn, r_name)] = json.loads(exec_ctn(ctn_name, cmd, "vtysh"))
    return r_bgp_nb_json[(asn, r_name)]


def get_r_intf_json(asn, r_name):
    """Return the json file of `show interface brief json`."""
    if (asn, r_name) not in r_intf_json:
        ctn_name = get_r_ctn_name(asn, r_name)
        cmd = ["show interface brief json"]
        r_intf_json[(asn, r_name)] = json.loads(exec_ctn(ctn_name, cmd, "vtysh"))
    tmp = r_intf_json[(asn, r_name)]
    if asn == SD_CTN_PREFIX:
        del r_intf_json[(asn, r_name)]
    return tmp


def get_r_ospf_intf_json(asn, r_name):
    """Return the json file of `show ip ospf interface json`."""
    if (asn, r_name) not in r_ospf_intf_json:
        ctn_name = get_r_ctn_name(asn, r_name)
        cmd = ["show ip ospf interface json"]
        r_ospf_intf_json[(asn, r_name)] = json.loads(exec_ctn(ctn_name, cmd, "vtysh"))
    return r_ospf_intf_json[(asn, r_name)]


def get_r_bgp_route_json(asn, r_name, new=True):
    """
    Return the json file of `show ip bgp json`.

    If new = True, will dump the json again.
    """
    if (asn, r_name) not in r_bgp_r_json or new:
        ctn_name = get_r_ctn_name(SD_CTN_PREFIX, r_name)
        cmd = ["show ip bgp json"]
        ret = json.loads(exec_ctn(ctn_name, cmd, "vtysh"))
        if "routes" in ret:
            r_bgp_r_json[(asn, r_name)] = ret["routes"]
        else:
            r_bgp_r_json[(asn, r_name)] = {}
    return r_bgp_r_json[(asn, r_name)]


def get_r_route_json(asn, r_name, v6=False):
    """Return the json file of `show ip{v6} route json`."""
    if (asn, r_name, v6) not in r_route_json:
        v_flag = "v6" if v6 else ""
        ctn_name = get_r_ctn_name(asn, r_name)
        cmd = [f"show ip{v_flag} route json"]
        r_route_json[(asn, r_name, v6)] = json.loads(exec_ctn(ctn_name, cmd, "vtysh"))
    return r_route_json[(asn, r_name, v6)]


def get_r_fib_json(asn, r_name, v6=False):
    """Return the json file of `show ip{v6} fib json`."""
    if (asn, r_name, v6) not in r_fib_json:
        v_flag = "v6" if v6 else ""
        ctn_name = get_r_ctn_name(asn, r_name)
        cmd = [f"show ip{v_flag} fib json"]
        r_fib_json[(asn, r_name, v6)] = json.loads(exec_ctn(ctn_name, cmd, "vtysh"))
    return r_fib_json[(asn, r_name, v6)]


##### INTF QUERY ######
# cache
h_gw = {}
h_intf = {}
s_tags = {}
r_tunns = {}


def get_act_r_intf_subnet(asn, r_name, intf_name, v6=False):
    """Return router subnet for a given interface string in cidr form."""
    assert r_name in REGION_NAMES
    intf_json = get_r_intf_json(asn, r_name)
    subnets = intf_json[intf_name]["addresses"]
    # a router may only have ipv6 interfaces
    for subnet in subnets:
        if is_v6_subnet(subnet) and v6:
            return subnet
        elif not v6 and not is_v6_subnet(subnet):
            return subnet
    return ""


def get_exp_h_intf_name(asn, h_name):
    """Return the expected interface name of a host."""
    if h_name in L2_HOST_NAMES:
        return f"{asn}-S{L2_REGION_TO_SW[h_name.split('_')[1]]}"
    else:
        assert h_name in REGION_NAMES
        return f"{h_name}router"


def get_act_h_intf_subnet(asn, h_name, intf_name="", v6=False):
    """Return host subnet for a given interface string in cidr form."""
    assert h_name in REGION_NAMES + L2_HOST_NAMES
    ctn_name = get_h_ctn_name(asn, h_name)
    if intf_name == "":
        # for l2 hosts, the interface is known, e.g., 1-S1
        assert h_name in L2_HOST_NAMES
        intf_name = f"{asn}-S{L2_REGION_TO_SW[h_name.split('_')[1]]}"
    if (asn, h_name, intf_name, v6) not in h_intf:
        if not v6:
            cmd = [f"ifconfig {intf_name}" + " | awk -F' *|:' '/inet /{print}'"]
            results = exec_ctn(ctn_name, cmd).strip()
            # different intf may have different patterns
            pat = (
                r"inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*"
                + r"netmask (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
            )
            match = re.search(pat, results)
            if not match:
                return ""
            ip = match.group(1)
            mask = match.group(2)
            h_intf[(asn, h_name, intf_name, v6)] = mask_to_cidr(ip, mask)
        else:
            cmd = [
                f"ifconfig {intf_name}"
                + " | awk -F' *|' '/inet6 .*<global>/{print $3 \"/\" $5}'"
            ]
            h_intf[(asn, h_name, intf_name, v6)] = exec_ctn(ctn_name, cmd).strip()
    return h_intf[(asn, h_name, intf_name, v6)]


valid_ext_links_intfs = {}

ExtIntfs = namedtuple("ExtIntfs", ["r_ip", "nb_ip"])


def get_valid_ext_link_intfs(asn):
    """
    Return a dict of the valid intfs on both ends of an eBGP sessions.

    Each valur in the dict is a tuple, tuple[0] is the intf on the router,
    tuple[1] is the intf on the neighbor.

    """
    # NOTE: assume each router only has at most one ebgp session
    # TODO: do not use tuple, use class instead
    if asn not in valid_ext_links_intfs:
        ret = {}
        ext_conns = get_exp_ext_conn(asn)
        for nb_name, r_name in NB_CONN.items():
            exp_subnet = ext_conns[r_name][0][3]
            intf_r_name = get_ext_intf_names(asn, nb_name)[0]
            nb_asn = get_nb_asn_r(asn, nb_name)[0]
            subnet_r = get_act_r_intf_subnet(asn, r_name, intf_r_name)
            nb_json = get_bgp_nb_json(asn, r_name)
            ip_nb = ""
            for ip in nb_json:
                if nb_json[ip]["remoteAs"] == nb_asn:
                    ip_nb = ip
            if is_within_v4_subnet(subnet_r, exp_subnet) and is_within_v4_subnet(
                f"{ip_nb}/24", exp_subnet
            ):
                ip_r = subnet_r.split("/")[0]
                ret[nb_name] = (ip_r, ip_nb)
        valid_ext_links_intfs[asn] = ret
    return valid_ext_links_intfs[asn]


def get_h_gw(asn, h_name, v6=False):
    """Return hosts gateway."""
    assert h_name in REGION_NAMES + L2_HOST_NAMES
    ctn_name = get_h_ctn_name(asn, h_name)
    if (asn, h_name, v6) in h_gw:
        return h_gw[(asn, h_name, v6)]
    v_flag = "-6" if v6 else ""
    cmd = [f"ip {v_flag} r" + " | awk '/default/{print $3}'"]
    result = exec_ctn(ctn_name, cmd).strip()
    h_gw[(asn, h_name, v6)] = result
    return result


def get_s_vlan_tags(asn, s_name):
    """
    Return the vlan tag dictionary of the switch.

    E.g., {'1-ZURI': [10, 20], '1-FIFA_1': 10}
    """
    assert s_name in L2_SW_NAMES
    if (asn, s_name) not in s_tags:
        ctn_name = get_s_ctn_name(asn, s_name)
        cmd = ["ovs-vsctl show | awk '/Port/,/Interface/'"]
        port_ret = [
            line.strip() for line in exec_ctn(ctn_name, cmd).strip().split("\n")
        ]
        result = {}
        port = None
        for line in port_ret:
            if line.startswith("Port"):
                port = line.split("Port ")[1].strip('"')
            elif line.startswith("tag:"):
                result[port] = int(line.split("tag: ")[1])
            elif line.startswith("trunks:"):
                result[port] = list(
                    map(int, line.split("trunks: ")[1].strip("[]").split(", "))
                )
        s_tags[(asn, s_name)] = result
    return s_tags[(asn, s_name)]


def get_ospf_cost_via_dcn(asn, src, dst):
    """
    Return the ospf cost list from src to dst via dcn.

    E.g., [('ZURI', 'DCN', 0), ('DCN', 'BASE', 10)],
    the cost depends on the ospf cost from src to dst (w/o via dcn).
    """

    def compute_dcn_ospf_cost(fst, snd, direct):
        """
        Return the ospf cost to cross DCN.

        fst stands for ingress link, snd stands for egress link,
        the cost is computed as:
        if snd < direct and fst < direct, return direct - 1,
        if (snd < direct and fst >= direct) or snd == direct, return direct,
        if snd > diret, return direct + 1
        """
        # NOTE: the cost computation is based on my observation
        # the reason to use relative cost is that when snd < direct and
        # fst = MAX, it's still balanced
        if snd > direct:
            return direct + 1
        if snd < direct and fst < direct:
            return direct - 1
        return direct

    assert src in L2_DCN_CONN_R
    assert dst in L2_DCN_CONN_R
    result = []
    src_ospf_json = get_r_ospf_intf_json(asn, src)
    dst_ospf_json = get_r_ospf_intf_json(asn, dst)
    try:
        direct = src_ospf_json["interfaces"][f"port_{dst}"]["cost"]
    except KeyError:
        direct = MAX_OSPF_COST

    min_tag_cost = MAX_OSPF_COST
    tag_cost_updated = False
    for vlan_tag in VLAN_TAGS:
        try:
            fst = src_ospf_json["interfaces"][f"{src}-L2.{vlan_tag}"]["cost"]
            snd = dst_ospf_json["interfaces"][f"{dst}-L2.{vlan_tag}"]["cost"]
            min_tag_cost = min(min_tag_cost, compute_dcn_ospf_cost(fst, snd, direct))
            tag_cost_updated = True
        except KeyError:
            # if the interface does not exist
            continue

    if tag_cost_updated:
        result = [(src, "DCN", 0), ("DCN", dst, min_tag_cost)]
    return result


def get_net_ospf_graph(asn):
    """Return the ospf graph of an AS."""

    def get_net_ospf_cost(asn):
        """Return the ospf cost dict for the entire AS."""

        def get_r_ospf_cost(asn, r_name):
            """
            Return the ospf cost list for other router neighbors of a router.

            E.g., [('ZURI', 'BASE', 10)], this format is compatible with nx.
            """
            assert r_name in REGION_NAMES
            cost = []
            ospf_intf_json = get_r_ospf_intf_json(asn, r_name)
            # unconfigured router does not have interface
            if "interfaces" in ospf_intf_json:
                for port in ospf_intf_json["interfaces"]:
                    other_p = port.split("port_")[1] if port.startswith("port_") else ""
                    if other_p in REGION_NAMES:
                        # TODO should I consider weights to DCN?
                        cost.append(
                            (
                                r_name,
                                other_p,
                                int(ospf_intf_json["interfaces"][port]["cost"]),
                            )
                        )
            return cost

        net_cost = []
        for r_name in REGION_NAMES:
            net_cost.extend(get_r_ospf_cost(asn, r_name))

        # update cost via DCN
        for src_id, src_r in enumerate(L2_DCN_CONN_R):
            for dst_id, dst_r in enumerate(L2_DCN_CONN_R):
                if src_id == dst_id:
                    continue
                net_cost.extend(get_ospf_cost_via_dcn(asn, src_r, dst_r))
        return net_cost

    if asn not in net_ospf_graph:
        net_cost = get_net_ospf_cost(asn)
        g = create_graph_from_link_cost(net_cost)
        net_ospf_graph[asn] = g
    return net_ospf_graph[asn]


def get_net_all_ospf_sp(asn, src, dst):
    """Return a list of shortest path from src to dst."""
    assert src in REGION_NAMES
    assert dst in REGION_NAMES
    g = get_net_ospf_graph(asn)
    # print the graph with cost
    for u, v, d in g.edges(data=True):
        print(f"    {u} --> {v}: {d['weight']}")
    sp = compute_all_shortest_paths(g, src, dst)
    return sp


def get_r_6in4_tunnel(asn, r_name):
    """
    Return the router tunnel information in a dict.

    I.e.,
    {tun_name: {'local': local-ipv4, 'remote': remote-ipv4, 'dst': [dst-ipv6]}}
    """
    assert r_name in REGION_NAMES
    if (asn, r_name) not in r_tunns:
        ctn_name = get_r_ctn_name(asn, r_name)
        v6_route_json = get_r_route_json(asn, r_name, v6=True)
        # collect interfaces used in each subnet
        tun_2_dst = defaultdict(list)
        for v6_dst in v6_route_json.keys():
            routes = v6_route_json[v6_dst]
            # NOTE: is this logic correct?
            for route in routes:
                if "selected" in route:
                    prefix = route["prefix"]
                    nexthops = route["nexthops"]
                    for nh in nexthops:
                        if nh["active"]:
                            intf = nh["interfaceName"]
                            tun_2_dst[intf].append(prefix)

        cmd = ["ip tunnel show | awk '!/sit0/'"]
        tun_res = exec_ctn(ctn_name, cmd, shell="bash").split("\n")
        pat = r"^([^\s]+):.*remote\s+(\d+\.\d+\.\d+\.\d+).*local\s+(\d+\.\d+\.\d+\.\d+)"
        tunnels = {}
        for tunnel in tun_res:
            match = re.search(pat, tunnel)
            if not match:
                continue
            tun_name = match.group(1)
            tun_remote = match.group(2)
            tun_local = match.group(3)
            tunnels[tun_name] = {
                "remote": tun_remote,
                "local": tun_local,
                "dst": tun_2_dst[tun_name],
            }
        r_tunns[(asn, r_name)] = tunnels

    return r_tunns[(asn, r_name)]


def print_r_6in4_tunnel(asn, r_name, log_file=None):
    """Print the router runnel information."""
    assert r_name in REGION_NAMES
    print = partial(new_print, log_file=log_file)
    print(f"\n     Print 6in4 tunnel information in {r_name}router:")
    tunnels = get_r_6in4_tunnel(asn, r_name)
    for tun_name, tun_info in tunnels.items():
        print(
            f"      {tun_name}: remote: {tun_info['remote']}, "
            f"local: {tun_info['local']}, dst: {tun_info['dst']}"
        )
    print()


def print_r_static_route(asn, r_name, v6=False):
    """Print static route information: (dst, next-port)."""
    # NOTE: unselected static route is not displayed
    assert r_name in REGION_NAMES
    r_route = get_r_route_json(asn, r_name, v6)
    static_r = set()
    for dst in r_route.keys():
        for route in r_route[dst]:
            if route["protocol"] == "static" and "selected" in route.keys():
                prefix = route["prefix"]
                for nh in route["nexthops"]:
                    if "interfaceName" in nh.keys():
                        static_r.add((prefix, nh["interfaceName"]))
                    elif "blackhole" in nh.keys():
                        static_r.add((prefix, "Null"))
    v_flag = "Ipv6" if v6 else "Ipv4"
    print(f"\n  Print {v_flag} static route for {r_name}router")
    for static in static_r:
        print(f"    {static[0]} --> {static[1]}")


def get_best_ext_route_nh(asn, r_name, prefix, new=True):
    """
    Return the BGP next-hop where the best route is learnt.

    If new=True, will re-fetch the bgp json
    """
    bgp_json = get_r_bgp_route_json(asn, r_name, new)
    if prefix not in bgp_json:
        return ""
    for route in bgp_json[prefix]:
        if "bestpath" in route:
            return route["peerId"]


####################################################
################# DATAPLANE QUERY###################
####################################################


def get_intra_host_tracert_hops(
    asn, src, dst, src_addr="", v6=False, dns=False, repeat=1, timeout=1, probes=1
):
    """
    Returns a list of intra-domain traceroute results between 2 given hosts.

    if src_addr is provided, it needs to be a valid interface address."""
    ctn_name = get_h_ctn_name(asn, src)
    if dst in REGION_NAMES:
        # only check on expected interface
        dst_ip = get_exp_intf_ip("host", asn, dst)
    else:
        assert dst in L2_HOST_NAMES
        dst_subnet = get_act_h_intf_subnet(asn, dst, v6=v6)
        if dst_subnet == "":
            return [[] for _ in range(repeat)]
        dst_ip = dst_subnet.split("/")[0]
    result = []
    dns_flag = "" if dns else "-n"
    v_flag = "-6" if v6 else ""
    src_addr_flag = f"-s {src_addr}" if src_addr != "" else ""
    cmd = [
        f"traceroute {src_addr_flag} -w {timeout} -q {probes} {v_flag} "
        + f"{dns_flag} {dst_ip}"
        + " | awk '/^ [0-9]+/{print $2}'"
    ]
    for _ in range(repeat):
        tracert_ret = exec_ctn(ctn_name, cmd).split()
        if "unreachable" in tracert_ret:
            result.append([])
        else:
            result.append(exec_ctn(ctn_name, cmd).split())
    return result


def print_intra_host_tracert_hops(
    asn, src, dst, src_addr="", v6=False, dns=False, repeat=1, probes=1
):
    """Print the intra domain traceroute hops enumerically."""
    assert src in REGION_NAMES + L2_HOST_NAMES
    assert dst in REGION_NAMES + L2_HOST_NAMES
    src_name = f"{src}host" if src in REGION_NAMES else src
    dst_name = f"{dst}host" if dst in REGION_NAMES else dst
    dns_flag = "w/ DNS" if dns else "w/o DNS"
    print(
        f"\n    Print traceroute hops from {src_name} to {dst_name} for "
        + f"{repeat} times ({dns_flag}):"
    )
    traces = get_intra_host_tracert_hops(
        asn, src, dst, src_addr, v6, dns, repeat, probes
    )
    for i, trace in enumerate(traces):
        print(f"      Iter {i+1}:")
        if not trace or "bad" in trace:
            print("        traceroute unreachable")
        else:
            for id, hop in enumerate(trace):
                print(f"        {id + 1}: {hop}")
        print()


def get_intra_host_ping_loss(asn, src, dst, src_intf="", v6=False, times=10, timeout=1):
    """
    Return the ping loss ratio between 2 given intra-domain hosts.

    v6 only works when both ends are l2 hosts,
    src_intf can be an interface name or the address.
    """
    ctn_name = get_h_ctn_name(asn, src)
    if dst in REGION_NAMES:
        dst_ip = get_exp_intf_ip("host", asn, dst)
    elif dst in L2_HOST_NAMES:
        dst_subnet = get_act_h_intf_subnet(asn, dst, v6=v6)
        if dst_subnet == "":
            return 100
        dst_ip = dst_subnet.split("/")[0]
    else:
        assert dst == "dns"
        dst_ip = DNS_IP4

    v_flag = "-6" if v6 else ""
    src_intf_flag = f"-I {src_intf}" if src_intf != "" else ""
    cmd = [
        f"ping {v_flag} -q -c {times} -W {timeout} "
        + f"{src_intf_flag} {dst_ip} 2>&1"
        + " | awk '/loss/{print}'"
    ]
    ping_ret = exec_ctn(ctn_name, cmd)
    pat = r"(\d+)% packet loss"
    match = re.search(pat, ping_ret)
    if not match:
        return 100
    return int(match.group(1))


def get_intra_tcpdump_result(
    asn,
    src_h,
    dst_h,
    r_name,
    r_intf_name,
    src_h_intf="",
    v6=False,
    ping_times=5,
    dump_timeout=15,
    display=False,
):
    """
    Return the tcpdump result for the ping during the given timeout.

    First trigger a ping from src_h to dst_h, then perform the tcpdump.
    """

    def exec_ping_proc():
        """Execute ping process."""
        get_intra_host_ping_loss(
            asn, src_h, dst_h, src_intf=src_h_intf, v6=v6, times=ping_times
        )

    def exec_tcpdump_proc(queue):
        """Execute tcpdump process and store output in the queue."""
        r_ctn_name = get_r_ctn_name(asn, r_name)
        cmd = [
            f"timeout {dump_timeout} tcpdump -i {r_intf_name} 2> /dev/null"
            + " | awk '/ICMP/{print}'"
        ]
        dump_ret = exec_ctn(r_ctn_name, cmd, shell="bash")
        queue.put(dump_ret)

    output_queue = Queue()
    proc_ping = Process(target=exec_ping_proc, args=())
    proc_tcpdump = Process(target=exec_tcpdump_proc, args=(output_queue,))
    proc_ping.start()
    proc_tcpdump.start()
    proc_ping.join()
    proc_tcpdump.join()

    dump_icmp = output_queue.get()
    if display:
        # print tcpdump result iinvolving ICMP result
        dump_display = dump_icmp.split("\n")
        max_display_len = 4
        print("  Print (partial) tcpdump result for ICMP packets:")
        for i in range(min(len(dump_display), max_display_len)):
            print(f"    {dump_display[i].split(', id')[0]}")

    return dump_icmp


####################################################
####### MODIFY CONFIG(for solutions) ###############
####################################################


# NOTE: assume the AS is in a clean state
def add_r_intf(asn, r_name, intf_name, addr):
    """Configure router interface address."""
    ctn_name = get_r_ctn_name(asn, r_name)
    cmds = ["config", f"interface {intf_name}", f"ip address {addr}"]
    exec_ctn(ctn_name, cmds, shell="vtysh")


def add_s_vlan(asn, s_name, port_name, tags):
    """Configure VLAN tags for the switch."""
    ctn_name = get_s_ctn_name(asn, s_name)
    assert len(tags) > 0
    if len(tags) == 1:
        # add tag
        cmd = [f"ovs-vsctl set port {port_name} tag={tags[0]}"]
        exec_ctn(ctn_name, cmd, shell="sh")
    else:
        # add trunks
        trunks = ",".join([str(x) for x in tags])
        cmd = [f"ovs-vsctl set port {port_name} trunks={trunks}"]
        exec_ctn(ctn_name, cmd, shell="sh")


def add_r_ospf_cost(asn, r_name, intf_name, cost):
    """Add OSPF cost given the router and the specific interface."""
    ctn_name = get_r_ctn_name(asn, r_name)
    cmds = ["config", f"interface {intf_name}", f"ip ospf cost {cost}"]
    exec_ctn(ctn_name, cmds, shell="vtysh")


def add_h_intf(asn, h_name, subnet, intf_name, v6=False):
    """Add host interface given the name and the interface."""
    ctn_name = get_h_ctn_name(asn, h_name)
    v6_flag = "-6" if v6 else ""
    cmd = [f"ip {v6_flag} addr add {subnet} dev {intf_name}"]
    exec_ctn(ctn_name, cmd, shell="bash")


def add_h_gw(asn, h_name, gw, v6=False):
    """Add host gateway given the name and the interface."""
    ctn_name = get_h_ctn_name(asn, h_name)
    v6_flag = "-6" if v6 else ""
    cmd = [f"ip {v6_flag} route add default via {gw}"]
    exec_ctn(ctn_name, cmd, shell="bash")


def add_r_tunnel(asn, r_name, t_name, remote, local, ttl, subnets):
    """Add router tunnel."""
    ctn_name = get_r_ctn_name(asn, r_name)
    cmd = [f"ip tunnel add {t_name} mode sit remote {remote} local {local} ttl {ttl}"]
    exec_ctn(ctn_name, cmd, shell="bash")
    cmd = [f"ip link set {t_name} up"]
    exec_ctn(ctn_name, cmd, shell="bash")
    for subnet in subnets:
        cmd = [f"ip route add {subnet} dev {t_name}"]
        exec_ctn(ctn_name, cmd, shell="bash")
