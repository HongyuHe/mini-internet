#!/usr/bin/env python3

"""Utilities to interact with the LIVE mini-internet environment."""

import json
import re
from collections import defaultdict

from ctn_utils import exec_ctn

# --- Constants from original mnet_utils --- #
REGION_NAMES = ["BIRM", "FRAN", "MUNI", "ZURI", "LYON", "MILA", "BARC", "NAPL"]
L2_DCN_HOST_NAMES = ["A_TUM", "S_TUM"]
L2_DCS_HOST_NAMES = ["A_MIL", "S_MIL", "A_POL", "S_POL"]
L2_HOST_NAMES = L2_DCN_HOST_NAMES + L2_DCS_HOST_NAMES
NB_CONN = {
    "PROV1": "BIRM",
    "PROV2": "FRAN",
    "CUST1": "BARC",
    "CUST2": "NAPL",
    "PEER1": "MUNI",
    "IXP": "LYON",
}
# --- End Constants --- #

# --- Core Functions for Targeting Live Containers --- #

def get_r_ctn_name(asn, r_name):
    """Return the live container name of a router."""
    return f"{asn}_{r_name}router"

def get_h_ctn_name(asn, name):
    """Return the live container name of a host."""
    if name in REGION_NAMES:
        return f"{asn}_{name}host"
    elif name in L2_HOST_NAMES:
        # Assuming a naming convention like ASN_L2_DCN_A_TUM
        # This might need adjustment based on the actual live container names.
        if name in L2_DCN_HOST_NAMES:
            return f"{asn}_L2_DCN_{name}"
        else:
            return f"{asn}_L2_DCS_{name}"
    raise ValueError(f"Unknown host name: {name}")

# --- Modified Data Query Functions --- #

r_bgp_nb_json_cache = {}

def get_bgp_nb_json(asn, r_name, new=False):
    """Return the json file of `show ip bgp neighbors json` from a live router."""
    if (asn, r_name) not in r_bgp_nb_json_cache or new:
        ctn_name = get_r_ctn_name(asn, r_name)
        cmd = ["show bgp neighbors json"]
        output = exec_ctn(ctn_name, cmd, "vtysh")
        r_bgp_nb_json_cache[(asn, r_name)] = json.loads(output) if output else {}
    return r_bgp_nb_json_cache[(asn, r_name)]

def get_act_h_intf_subnet(asn, h_name, intf_name="", v6=False):
    """Return host subnet for a given interface string in cidr form."""
    ctn_name = get_h_ctn_name(asn, h_name)
    if not intf_name:
        # This logic might need to be adapted based on live setup
        intf_name = f"{asn}-S1" # Placeholder

    if not v6:
        cmd = [f"ifconfig {intf_name} | awk -F' *|:' '/inet /{{print}}'"]
        results = exec_ctn(ctn_name, cmd).strip()
        match = re.search(r"inet (\S+).*netmask (\S+)", results)
        if not match:
            return ""
        ip = match.group(1)
        mask = match.group(2)
        return f"{ip}/{sum([bin(int(x)).count('1') for x in mask.split('.')])}"
    else:
        cmd = [f"ifconfig {intf_name} | awk -F' *|/' '/inet6 .*<global>/{{print $3 "/" $5}}'"]
        return exec_ctn(ctn_name, cmd).strip()


def get_intra_host_ping_loss(asn, src, dst, v6=False, times=5):
    """Return the ping loss ratio between 2 given live intra-domain hosts."""
    src_ctn = get_h_ctn_name(asn, src)
    # In a live environment, the destination IP must be discovered, not assumed.
    # This is a simplified version.
    dst_ip = get_act_h_intf_subnet(asn, dst, v6=v6).split('/')[0]
    if not dst_ip:
        return 100

    v_flag = "-6" if v6 else ""
    cmd = [f"ping {v_flag} -q -c {times} -W 1 {dst_ip} | awk '/loss/{{print}}'"]
    ping_ret = exec_ctn(src_ctn, cmd)
    match = re.search(r"(\d+)% packet loss", ping_ret)
    return int(match.group(1)) if match else 100

# ... other utility functions (get_r_route_json, get_net_all_ospf_sp, etc.) would be
# adapted in a similar fashion, always using the new get_*_ctn_name functions
# to target the correct live container based on the ASN.
