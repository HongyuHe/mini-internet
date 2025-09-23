#!/usr/bin/env python3
from mnet_config import *


def a_1_8(asn=1):
    # configure PHY and BASE intf
    # can only apply once
    add_r_intf(asn, "PHY", "PHY-L2.30", f"{asn}.200.30.1/24")
    add_r_intf(asn, "BASE", "BASE-L2.30", f"{asn}.200.30.2/24")
    # configure DCN switch vlan
    add_s_vlan(asn, "S1", f"{asn}-vpn_1", [30])
    add_s_vlan(asn, "S1", f"{asn}-S2", [10, 20, 30])
    add_s_vlan(asn, "S1", f"{asn}-S3", [10, 20, 30])
    add_s_vlan(asn, "S1", f"ZURIrouter", [10, 20, 30])

    add_s_vlan(asn, "S2", f"{asn}-vpn_2", [30])
    add_s_vlan(asn, "S2", f"{asn}-S1", [10, 20, 30])
    add_s_vlan(asn, "S2", f"{asn}-S3", [10, 20, 30])

    add_s_vlan(asn, "S3", f"{asn}-vpn_3", [30])
    add_s_vlan(asn, "S3", f"{asn}-S1", [10, 20, 30])
    add_s_vlan(asn, "S3", f"{asn}-S2", [10, 20, 30])
    # to test the connection between local device and mini-net,
    # need to also start the openvpn client and
    # change the default gateway on the local device


# a_1_8(1)
