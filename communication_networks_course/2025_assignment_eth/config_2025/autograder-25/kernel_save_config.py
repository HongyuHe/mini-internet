#!/usr/bin/env python3

"""Save kernel-related config information to json file."""

import json
import sys

from mnet_utils import (
    L2_DCN_GW_R,
    L2_DCS_GW_R,
    L2_HOST_NAMES,
    REGION_NAMES,
    get_act_h_intf_subnet,
    get_h_gw,
    get_r_6in4_tunnel,
)


JSON_FILE = "kernel_saved_config.json"


def dump_kernel_config(asn_path, json_file=JSON_FILE):
    """
    Dump kernel config to a json file.

    The AS numbers is provided in a file looks like: 1 2 3 4 5
    """
    with open(asn_path, "r") as f:
        asn_lst = [int(asn) for asn in f.read().split()]
    saved_config = {}
    for asn in asn_lst:
        # l2 host ipv4/v6 interfaces
        l2_v4 = {l2_h: get_act_h_intf_subnet(asn, l2_h) for l2_h in L2_HOST_NAMES}
        l2_v6 = {
            l2_h: get_act_h_intf_subnet(asn, l2_h, v6=True) for l2_h in L2_HOST_NAMES
        }

        # l2 host ipv4/v6 gateway
        l2_gw_v4 = {l2_h: get_h_gw(asn, l2_h) for l2_h in L2_HOST_NAMES}
        l2_gw_v6 = {l2_h: get_h_gw(asn, l2_h, v6=True) for l2_h in L2_HOST_NAMES}

        # l3 host ipv4 interfaces to its connected router
        l3_v4 = {
            l3_h: get_act_h_intf_subnet(asn, l3_h, f"{l3_h}router")
            for l3_h in REGION_NAMES
        }

        # router tunnel interfaces
        tunnels = {
            L2_DCN_GW_R: get_r_6in4_tunnel(asn, L2_DCN_GW_R),
            L2_DCS_GW_R: get_r_6in4_tunnel(asn, L2_DCS_GW_R),
        }

        saved_as_config = {
            "host-l2": {
                "ipv4": l2_v4,
                "ipv6": l2_v6,
                "gw_v4": l2_gw_v4,
                "gw_v6": l2_gw_v6,
            },
            "host-l3": {"ipv4": l3_v4},
            "tunnels": tunnels,
        }

        saved_config[asn] = saved_as_config

        config_json = json.dumps(saved_config)

        with open(json_file, "w") as f:
            f.write(config_json)


if __name__ == "__main__":
    asn_path = sys.argv[1]
    dump_kernel_config(asn_path)
