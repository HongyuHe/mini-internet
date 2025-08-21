#!/usr/bin/env python3

"""Provide grading functions for separate questions."""

import random
import re
import sys
import time
import math
import os
import subprocess
from collections import defaultdict
from functools import partial
from datetime import datetime
import shutil

from other_utils import Logger, new_print
from mnet_utils import (
    L2_COMP_NAME_1,
    L2_COMP_NAME_2,
    L2_DCN_GW_R,
    L2_DCN_HOST_NAMES,
    L2_DCN_SW_NAMES,
    L2_DCS_GW_R,
    L2_DCS_HOST_NAMES,
    L2_DCS_SW_NAMES,
    L2_HOST_NAMES,
    L3_EXP_MASK_LEN,
    REGION_NAME_TO_ID,
    REGION_NAMES,
    ROUTER_ID_TO_LINK,
    LOSS_TH,
    ROUTER_LINK_TO_ID,
    SERVICES,
    L2_DCS_REGION_NAMES,
    NB_CONN,
    BGP_CONV_WAIT,
    MAX_ZONE,
    IXP_ASNS,
    ExtIntfs,
    L2_DCN_REGION_NAMES,
    MAX_AS,
    get_act_h_intf_subnet,
    get_act_r_intf_subnet,
    get_bgp_nb_json,
    get_exp_intf_ip,
    get_exp_service_intf,
    get_h_gw,
    get_intra_host_ping_loss,
    get_intra_host_tracert_hops,
    get_intra_tcpdump_result,
    get_net_all_ospf_sp,
    get_s_vlan_tags,
    print_intra_host_tracert_hops,
    print_r_6in4_tunnel,
    get_exp_ext_conn,
    get_valid_ext_link_intfs,
    get_nb_asn_r,
    get_r_bgp_route_json,
    get_best_ext_route_nh,
    get_as_to_zone,
    get_zone_to_as_lst,
    get_ixp_tranit_asns,
    get_as_to_ixp
)
from exabgp_utils import (
    announce_exabgp_route,
    withdraw_exabgp_route,
    get_exabgp_rib_in,
    compare_route_preference,
)
# from sdas_utils import start_shadow_as, clear_shadow_as

DUMP_CONFIG_SCRIPT = os.path.join(os.getcwd(), "parse_gitlab_config.sh")
REPORT_DIR = f"reports/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
DUMP_WAIT = 2


def check_l2_conn_in_dc(asn, v6=False, dcn=False, dcs=True, log_file=None):
    """
    Print DC information and check L2 host connectivity within the same DC.

    """
    print = partial(new_print, log_file=log_file)
    v_flag = "Ipv6" if v6 else "Ipv4"
    print(f"\nChecking L2 host {v_flag} connectivity...")

    # print host interfaces and gateways
    # TODO: check subnets are within the specified subnets
    host_names = []
    if dcn:
        host_names += L2_DCN_HOST_NAMES

    if dcs:
        host_names += L2_DCS_HOST_NAMES
    # host_names = L2_HOST_NAMES if dcs else L2_DCN_HOST_NAMES
    print(f"  Print L2 host {v_flag} interface:")
    for l2_h in host_names:
        subnet = get_act_h_intf_subnet(asn, l2_h, v6=v6)
        print(f"    {l2_h}: {subnet}")

    print(f"\n  Print L2 host {v_flag} gateway:")
    for l2_h in host_names:
        gw = get_h_gw(asn, l2_h, v6=v6)
        print(f"    {l2_h}: {gw}")

    # print gateway router addresses
    print(f"\n  Print L2 gateway router {v_flag} interface:")
    dcn_vlan_10_subnet = get_act_r_intf_subnet(
        asn, L2_DCN_GW_R, f"{L2_DCN_GW_R}-L2.10", v6=v6
    )
    dcn_vlan_20_subnet = get_act_r_intf_subnet(
        asn, L2_DCN_GW_R, f"{L2_DCN_GW_R}-L2.20", v6=v6
    )
    print(f"    {L2_DCN_GW_R}-L2.10: {dcn_vlan_10_subnet}")
    print(f"    {L2_DCN_GW_R}-L2.20: {dcn_vlan_20_subnet}")

    dcs_vlan_10_subnet = get_act_r_intf_subnet(
        asn, L2_DCS_GW_R, f"{L2_DCS_GW_R}-L2.10", v6=v6
    )
    dcs_vlan_20_subnet = get_act_r_intf_subnet(
        asn, L2_DCS_GW_R, f"{L2_DCS_GW_R}-L2.20", v6=v6
    )
    if dcs:
        print(f"    {L2_DCS_GW_R}-L2.10: {dcs_vlan_10_subnet}")
        print(f"    {L2_DCS_GW_R}-L2.20: {dcs_vlan_20_subnet}")

    # print switch vlan tags
    # NOTE: assume when checking DCS, switch information has been
    # printed for DCN before
    # sw_names = L2_DCS_SW_NAMES if dcs else L2_DCN_SW_NAMES
    sw_names = []
    if dcn:
        sw_names += L2_DCN_SW_NAMES
    if dcs:
        sw_names += L2_DCS_SW_NAMES
    print("\n  Print switch VLAN configuration:")
    for l2_s in sw_names:
        print(f"    switch {l2_s}:")
        tags = get_s_vlan_tags(asn, l2_s)
        for port, tags in tags.items():
            print(f"      {port}: {tags}")
        print()

    # check ping and traceroute
    vio_count = 0
    check_count = 0

    # intra-company only works for one dc
    print(f"\n  Checking {v_flag} intra-company host connectivity within DCS...")
    for comp_name in [L2_COMP_NAME_1, L2_COMP_NAME_2]:
        for src_id, src_name in enumerate(L2_DCS_REGION_NAMES):
            for dst_id, dst_name in enumerate(L2_DCS_REGION_NAMES):
                if dst_id <= src_id:
                    continue
                check_count += 1
                src = f"{comp_name}_{src_name}"
                dst = f"{comp_name}_{dst_name}"
                loss = get_intra_host_ping_loss(asn, src, dst, v6=v6)
                if loss > LOSS_TH:
                    vio_count += 1
                    print(f"    {src}-->{dst}: ping failed")
                else:
                    # pass
                    hops = get_intra_host_tracert_hops(
                        asn, src, dst, dns=False, repeat=1, v6=v6
                    )
                    # traces should only contain dst address
                    if len(hops[0]) != 1:
                        vio_count += 1
                        print(
                            f"    {src}-->{dst}: traceroute check failed"
                            + " (more than 1 hop)"
                        )
                    else:
                        # print(f"    {src}-->{dst}: ping and traceroute ok")
                        pass

    # inter-company
    print(f"\n  Checking {v_flag} inter-company host connectivity within DC...")
    # dc_set = {"DCN", "DCS"} if dcs else {"DCN"}
    dc_set = set()
    if dcn:
        dc_set.add("DCN")
    if dcs:
        dc_set.add("DCS")
    for dc in dc_set:
        vlan_10_subnet = dcn_vlan_10_subnet if dc == "DCS" else dcs_vlan_10_subnet
        vlan_20_subnet = dcn_vlan_20_subnet if dc == "DCS" else dcs_vlan_20_subnet

        region_names = L2_DCN_REGION_NAMES if dc == "DCN" else L2_DCS_REGION_NAMES
        for src_id, src_name in enumerate(region_names):
            for dst_id, dst_name in enumerate(region_names):
                if dst_id == src_id:
                    continue
                check_count += 1
                src = f"{L2_COMP_NAME_1}_{src_name}"
                dst = f"{L2_COMP_NAME_2}_{dst_name}"
                loss = get_intra_host_ping_loss(asn, src, dst, v6=v6)
                if loss > LOSS_TH:
                    vio_count += 1
                    print(f"    {src}-->{dst}: ping failed")
                else:
                    # no group has this error
                    pass
                    # hops = get_intra_host_tracert_hops(
                    #     asn, src, dst, dns=False, repeat=1, v6=v6
                    # )
                    # # traces should contain gateway router
                    # if (
                    #     vlan_10_subnet.split("/")[0] not in hops[0]
                    #     and vlan_20_subnet.split("/")[0] not in hops[0]
                    # ):
                    #     vio_count += 1
                    #     print(
                    #         f"    {src}-->{dst}: traceroute check failed: {hops}"
                    #     )
                    # else:
                    #     # print(f"    {src}-->{dst}: ping and traceroute ok")
                    #     pass

    points = (check_count - vio_count) * 1.0 / check_count
    print(
        f"\n  Summary: {check_count - vio_count}/{check_count} host {v_flag}"
        + " connectivity are correctly configured"
    )
    return points


def check_l3_intf_config(asn, log_file=None):
    """Check l3 host/router interface configuration."""
    print = partial(new_print, log_file=log_file)
    print("\nChecking L3 interface configuration...")
    check_count = 0
    vio_count = 0
    # check router lo and interfaces between routers and hosts
    print("  Checking router loopback interface configuration...")
    for r_name in REGION_NAMES:
        check_count += 1
        r_act_lo = get_act_r_intf_subnet(asn, r_name, "lo")
        r_exp_lo = f"{get_exp_intf_ip('lo', asn, r_name)}/{L3_EXP_MASK_LEN}"
        if r_act_lo != r_exp_lo:
            vio_count += 1
            print(f"    {r_name}router: failed (act: {r_act_lo}, " f"exp: {r_exp_lo})")
        else:
            # print(f"    {r_name}router: ok")
            pass

    print("\n  Checking interface configuration between routers and connected hosts...")
    for r_name in REGION_NAMES:
        check_count += 1
        r_act_host = get_act_r_intf_subnet(asn, r_name, "host")
        r_exp_host = f"{get_exp_intf_ip('ip', asn, r_name)}/{L3_EXP_MASK_LEN}"
        if r_act_host != r_exp_host:
            vio_count += 1
            print(
                f"    {r_name}router: failed (act: {r_act_host}, exp: " f"{r_exp_host})"
            )
        else:
            # print(f"    {r_name}router: ok")
            pass

        check_count += 1
        h_act_ip = get_act_h_intf_subnet(asn, r_name, f"{r_name}router")
        h_exp_ip = f"{get_exp_intf_ip('host', asn, r_name)}/{L3_EXP_MASK_LEN}"
        if h_act_ip != h_exp_ip:
            vio_count += 1
            print(f"    {r_name}host: failed (act: {h_act_ip}, " f"exp: {h_exp_ip})")
        else:
            # print(f"    {r_name}host: ok")
            pass

    # check interfaces between routers
    print("\n  Checking interface configuration between routers...")
    for r_a, r_b in ROUTER_LINK_TO_ID:
        check_count += 1
        a_act_intf = get_act_r_intf_subnet(asn, r_a, f"port_{r_b}")
        a_exp_intf = (
            f"{get_exp_intf_ip('router', asn, r_a, r_b)}/" + f"{L3_EXP_MASK_LEN}"
        )
        if a_act_intf != a_exp_intf:
            vio_count += 1
            print(
                f"    {r_a}-->{r_b}: failed (act: {a_act_intf}, "
                + f"exp: {a_exp_intf})"
            )
        else:
            # print(f"    {r_a}-->{r_b}: ok")
            pass

        check_count += 1
        b_act_intf = get_act_r_intf_subnet(asn, r_b, f"port_{r_a}")
        b_exp_intf = (
            f"{get_exp_intf_ip('router', asn, r_b, r_a)}/" + f"{L3_EXP_MASK_LEN}"
        )
        if b_act_intf != b_exp_intf:
            vio_count += 1
            print(
                f"    {r_b}-->{r_a}: failed (act: {b_act_intf}, "
                + f"exp: {b_exp_intf})"
            )
        else:
            # print(f"    {r_b}-->{r_a}: ok")
            pass

    # check special interfaces: dns, measurement, matrix
    # print("\n  Check interface configuration between routers and service:")
    # for service in SERVICES:
    #     check_count += 1
    #     r_name, intf_name, exp_subnet = get_exp_service_intf(asn, service)
    #     r_act_service = get_act_r_intf_subnet(asn, r_name, intf_name)
    #     if r_act_service != exp_subnet:
    #         vio_count += 1
    #         print(
    #             f"    {r_name}-->{service}: failed (act: {r_act_service} "
    #             + f"exp: {exp_subnet})"
    #         )
    #     else:
    #         # print(f"    {r_name}-->{service}: ok")
    #         pass

    points = (check_count - vio_count) * 1.0 / check_count
    print(
        f"\n  Summary: {check_count - vio_count}/{check_count} L3 interfaces"
        + " are correctly configured"
    )
    return points


def check_l3_dcn_host_conn(asn, log_file=None):
    """Check connectivity among l3 hosts and between l3 and dcn hosts."""
    print = partial(new_print, log_file=log_file)
    print("\nChecking connectivity among L3 and L2 hosts...")
    check_count = 0
    vio_count = 0
    # randomly pick a pair of hosts and print traceroute hops
    # rand_hosts = random.sample(REGION_NAMES, 2)
    print("  Checking connectivity between L3 hosts...")
    for id_a, h_a in enumerate(REGION_NAMES):
        # check connectivity among l3 hosts
        for id_b, h_b in enumerate(REGION_NAMES):
            if id_b <= id_a:
                continue
            check_count += 1
            loss = get_intra_host_ping_loss(asn, h_a, h_b, times=1)
            if loss > LOSS_TH:
                print(f"    {h_a}host-->{h_b}host: ping failed")
                vio_count += 1
            else:
                pass
                # print(f"    {h_a}host-->{h_b}host: ping ok")
                # if [h_a, h_b] == rand_hosts:
                # NOTE: whether the dns is resolved is not checked
                # print_intra_host_tracert_hops(asn, h_a, h_b, dns=True, repeat=1)
                # TODO check the route is learnt via ospf or connected,
                # not via other protocols

    # check connectivity between l3 and dcn hosts
    # NOTE ping involving L2 hosts is slower than ping between l3 routers
    print("\n  Checking connectivity between L3 and L2 hosts...")
    for h_a in REGION_NAMES:
        for l2_h in L2_DCS_HOST_NAMES:
            check_count += 1
            loss = get_intra_host_ping_loss(asn, h_a, l2_h)
            if loss > LOSS_TH:
                print(f"    {h_a}host-->{l2_h}: ping failed")
                vio_count += 1
            else:
                # print(f"    {h_a}host-->{l2_h}: ping ok")
                pass

            # check_count += 1
            # loss = get_intra_host_ping_loss(asn, l2_h, h_a)
            # if loss > LOSS_TH:
            #     print(f"    {l2_h}-->{h_a}host: ping failed")
            #     vio_count += 1
            # else:
            #     # print(f"    {l2_h}-->{h_a}host: ping ok")
            #     pass

    # check connectivity between l3 hosts and dns service
    # print("\n  Check connectivity between L2/3 hosts and DNS service:")
    # for h_a in REGION_NAMES:
    #     check_count += 1
    #     loss = get_intra_host_ping_loss(asn, h_a, "dns")
    #     if loss > LOSS_TH:
    #         print(f"    {h_a}host: ping failed")
    #         vio_count += 1
    #     else:
    #         # print(f"    {h_a}host: ping ok")
    #         pass

    # check connectivity between l2 hosts and dns service
    # for l2_h in L2_DCN_HOST_NAMES:
    #     check_count += 1
    #     loss = get_intra_host_ping_loss(asn, l2_h, "dns")
    #     if loss > LOSS_TH:
    #         print(f"    {l2_h}: ping failed")
    #         vio_count += 1
    #     else:
    #         # print(f"    {l2_h}: ping ok")
    #         pass

    points = (check_count - vio_count) * 1.0 / check_count
    print(
        f"\n  Summary: {check_count - vio_count}/{check_count} host "
        + "connectivity are correctly configured"
    )
    return points


def check_l3_load_balancing(asn, src, dst, exp_sp, exp_hops, log_file=None):
    """Check whether the required load balancing paths are implemented."""

    # NOTE: the cost computation for path via DCN is unsure
    # but in 2023 version, there is no path through DCN, so it is fine
    # NOTE: does the check still work when it goes out of AS?
    # def convert_name_seq_to_num(asn, name_lst):
    #     """
    #     Convert a sequence of router names to their numeric hops.

    #     Given a list of router names, e.g., ['ZURI', 'BASE', 'LYON'],
    #     return a list of numerical ipv4 hops, e.g., ['3.0.1.2', '3.0.8.2'],
    #     as BASEroute's interface to ZURIrouter is 3.0.1.2, and
    #     LYONrouter's interface to BASErouter is 3.0.8.2.
    #     """
    #     result = []
    #     for i in range(len(name_lst) - 1):
    #         router_ip = get_exp_intf_ip("router", asn, name_lst[i + 1], name_lst[i])
    #         result.append(router_ip)
    #     return result

    def convert_num_to_name(num_hop):
        """
        Convert a numeric ipv4 address to the l3 link name.

        Given an ipv4 numeric hop, e.g., '3.0.11.1',
        return the equivalent link name, e.g., 'LUGA-MILA'.
        """
        pat = r"^\d+\.\d+\.(\d+)\.(\d+)"
        match = re.search(pat, num_hop)
        assert match
        third = int(match.group(1))
        fourth = int(match.group(2))
        try:
            r_a, r_b = ROUTER_ID_TO_LINK[third]
            if fourth == 1:
                return f"{r_a}-{r_b}"
            else:
                assert fourth == 2
                return f"{r_b}-{r_a}"
        except:
            return num_hop

    print = partial(new_print, log_file=log_file)
    sp_violated = False
    exp_sp = sorted(exp_sp)
    assert src in REGION_NAMES
    assert dst in REGION_NAMES
    print(f"\nChecking OSPF load balancing from {src}router to {dst}router...")
    print(f"  Checking theoretical shortest paths from {src}router to {dst}router...")
    act_sp = sorted(get_net_all_ospf_sp(asn, src, dst))
    if exp_sp != act_sp:
        sp_violated = True
        print(f"    {src}router-->{dst}router: theoretical shortest paths " + "failed")
        print("      act:")
        for sp in act_sp:
            print(f"        {'-->'.join(sp)}")
        print("      exp:")
        for sp in exp_sp:
            print(f"        {'-->'.join(sp)}")
    else:
        # print(f"    {src}router-->{dst}router: theoretical shortest paths ok")
        pass

    # print(f"\n  Checking Ipv4 forwarding paths from {src}host to {dst}host...")
    # tr_violated = False
    # loss = get_intra_host_ping_loss(asn, src, dst, v6=False)
    # if loss > LOSS_TH:
    #     tr_violated = True
    #     print(f"\n    {src}host-->{dst}host: ping failed")
    # else:
    #     # check for each hop, only specific set of links can be taken
    #     act_traces = get_intra_host_tracert_hops(
    #         asn, src, dst, dns=False, repeat=20, probes=1
    #     )
    #     act_hops = defaultdict(set)
    #     for act_trace in act_traces:
    #         # remove host ips
    #         act_trace = act_trace[1:-1]
    #         for hop_id, hop in enumerate(act_trace):
    #             act_hops[hop_id + 1].add(hop)

    #     # exp_hops = defaultdict(set)
    #     # for exp_path in exp_sp:
    #     #     exp_trace = convert_name_seq_to_num(asn, exp_path)
    #     #     for hop_id, hop in enumerate(exp_trace):
    #     #         exp_hops[hop_id + 1].add(hop)

    #     max_hop_len = max(len(act_hops), len(exp_hops))
    #     for hop_id in range(1, max_hop_len + 1):
    #         only_act = {hop for hop in act_hops[hop_id] if hop not in exp_hops[hop_id]}
    #         # only_exp = {hop for hop in exp_hops[hop_id] if hop not in act_hops[hop_id]}
    #         if only_act:
    #             vio_links = {convert_num_to_name(hop) for hop in only_act}
    #             print(
    #                 f"    Link(s) {vio_links} should not appear at hop "
    #                 + f"{hop_id + 1}"
    #             )
    #             tr_violated = True
    #         # if only_exp:
    #         #     vio_links = {convert_num_to_name(hop) for hop in only_exp}
    #         #     print(
    #         #         f"    Link(s) {vio_links} should appear at hop " + f"{hop_id + 1}"
    #         #     )
    #         #     tr_violated = True

    # if not tr_violated:
    #     # print(f"    {src}router-->{dst}router: traceroute check ok")
    #     pass

    # better point assignments
    check_count = 1
    vio_count = 0
    if sp_violated:
        vio_count += 1
    # if tr_violated:
    #     vio_count += 1
    points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_across_dc_v6_conn(asn, log_file=None):
    """Check the Ipv6 connectivity across DCs follows the intended path."""
    print = partial(new_print, log_file=log_file)
    print("\nChecking Ipv6 connectivity across two DCs...")
    # print tunnel information
    # TODO: should I also check the destination ipv6 does use the tunnel?
    # what if the ip used in the tunnel does not equal to /32 subnet?
    print("  Print router tunnel information:")
    print_r_6in4_tunnel(asn, L2_DCN_GW_R, log_file=log_file)
    print_r_6in4_tunnel(asn, L2_DCS_GW_R, log_file=log_file)

    check_count = 0
    vio_count = 0
    # check ipv6 connectivity across dc
    print("\n  Checking Ipv6 host connectivity across DCs...")
    for id_a, h_a in enumerate(L2_HOST_NAMES):
        for id_b, h_b in enumerate(L2_HOST_NAMES):
            if (
                (h_a in L2_DCN_HOST_NAMES and h_b in L2_DCS_HOST_NAMES)
                or (h_a in L2_DCS_HOST_NAMES and h_b in L2_DCN_HOST_NAMES)
            ) and id_b > id_a:
                check_count += 1
                loss = get_intra_host_ping_loss(asn, h_a, h_b, v6=True)
                if loss > LOSS_TH:
                    vio_count += 1
                    print(f"    {h_a}-->{h_b}: ping failed")
                else:
                    # no group has wrong trace
                    pass
                    # act_hops = get_intra_host_tracert_hops(
                    #     asn, h_a, h_b, v6=True, dns=False, repeat=1
                    # )[0]
                    # # exp_hop_len = 3
                    # exp_fst_hop = get_h_gw(asn, h_a, v6=True)
                    # exp_last_hop = get_act_h_intf_subnet(asn, h_b, v6=True).split("/")[
                    #     0
                    # ]
                    # if (
                    #     # len(act_hops) != exp_hop_len
                    #     act_hops[0] != exp_fst_hop
                    #     or act_hops[-1] != exp_last_hop
                    # ):
                    #     vio_count += 1
                    #     print(
                    #         f"    {h_a}-->{h_b}: traceroute check failed "
                    #         + "(incorrect hops or hop numbers)"
                    #     )
                    # else:
                    #     # print(f"    {h_a}-->{h_b}: ping and traceroute ok")
                    #     pass

    points = (check_count - vio_count) * 1.0 / check_count
    print(
        f"\n  Summary: {check_count - vio_count}/{check_count}"
        + " cross DC Ipv6 host connectivity are correctly configured"
    )
    return points


def check_ibgp_full_mesh(asn, log_file=None):
    """Check ibgp full mesh within AS and return points."""
    print = partial(new_print, log_file=log_file)
    print("\nCheck iBGP full mesh configuration within AS:")
    vio_count = 0
    check_count = 0
    for r in REGION_NAME_TO_ID:
        r_lo = get_exp_intf_ip("lo", asn, r)
        nb_json = get_bgp_nb_json(asn, r, new=True)
        for other_r in REGION_NAMES:
            if other_r == r:
                continue
            other_lo = get_exp_intf_ip("lo", asn, other_r)
            check_count += 1
            if (
                other_lo not in nb_json
                or nb_json[other_lo]["localRouterId"] != r_lo
                or nb_json[other_lo]["remoteAs"] != asn
            ):
                print(f"  {r}-->{other_r}: invalid" + "(incorrect interface or region)")
                vio_count += 1
            elif nb_json[other_lo]["bgpState"] != "Established":
                vio_count += 1
                print(f"  {r}-->{other_r}: unestablished")
                # print(f"  {r}-->{other_r}: ok")
            else:
                pass
    print(
        f"\n  Summary: {check_count - vio_count}/{check_count}"
        + " iBGP sessions are correctly configured"
    )
    points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_dc_traffic_use_link(asn, link_name, log_file=None):
    """
    Check a link is used for the acorss DC traffic.

    Check when triggering traffic between 2 dcs,
    there are ICMP packets captured on the given link (e.g., 'ZURI-GENE'),
    if v6=True, the traffic is ipv6.
    """
    print = partial(new_print, log_file=log_file)
    print(f"\nCheck link {link_name} is used for Ipv6 connection between 2 DCs:")
    r_name = link_name.split("-")[0]
    r_intf_name = f"port_{link_name.split('-')[1]}"

    # NOTE: since tcpdump takes time (~20s),
    # I just randomly pick a host from 2 DCs
    src_h = random.choice(list(L2_DCS_HOST_NAMES))
    dst_h = random.choice(list(L2_DCN_HOST_NAMES))

    # check both directions
    check_count = 2
    vio_count = 0

    dump_res = get_intra_tcpdump_result(
        asn, src_h, dst_h, r_name, r_intf_name, v6=True, display=True
    )
    if dump_res == "":
        print(
            f"    {link_name} link is not used for traffic from "
            + f"{src_h} to {dst_h}"
        )
        vio_count += 1

    dump_res = get_intra_tcpdump_result(
        asn, dst_h, src_h, r_name, r_intf_name, v6=True, display=True
    )
    if dump_res == "":
        print(
            f"    {link_name} link is not used for traffic from "
            + f"{dst_h} to {src_h}"
        )
        vio_count += 1

    print(
        f"\n  Summary: {check_count - vio_count}/{check_count} TE"
        + " for Ipv6 connection between 2 DCs are achieved"
    )
    points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_as_intf_config(asn, log_file=None):
    """Check AS's as-level/external intf configuration."""
    # NOTE: assume all expected subnets do not have wildcard
    print = partial(new_print, log_file=log_file)
    print("\nChecking AS-level interface configuration...")
    check_count = 0
    vio_count = 0
    ext_conns = get_exp_ext_conn(asn)
    valid_ext_intfs = get_valid_ext_link_intfs(asn)
    # print(f"valid_ext_intfs")
    # print(valid_ext_intfs)
    for nb_name, r_name in NB_CONN.items():
        check_count += 1
        assert len(ext_conns[r_name]) == 1
        other_as, nb_r, _, _ = ext_conns[r_name][0]
        if nb_name not in valid_ext_intfs:
            vio_count += 1
            print(
                f"  EBGP session {r_name}-->{nb_name} (AS{other_as} {nb_r}): invalid (unestablished or incorrect interfaces)"
            )
        else:
            # print(f"    {r_name}-->{as_type} {other_as}: ok")
            pass

    print(
        f"\n  Summary: {check_count - vio_count}/{check_count} AS-level"
        + " interfaces are correctly configured."
    )
    points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_nb_route_send_rcv(asn, log_file=None):
    """Check asn advertises its network and receives its neighbors' network."""
    # check each router announces asn.0.0.0/8 to EXABGP
    print = partial(new_print, log_file=log_file)
    print(
        "\nChecking the AS advertises its network and receives its neighbors' network..."
    )
    not_checked = False
    ext_infs = get_valid_ext_link_intfs(asn)
    if len(ext_infs) != len(NB_CONN):
        not_checked = True
    else:
        check_count = 0
        vio_count = 0
        rib_in = get_exabgp_rib_in()
        own_net = f"{asn}.0.0.0/8"
        print("  Checking own network is advertised to all eBGP neighbors...")
        for nb_name in NB_CONN:
            check_count += 1
            nb_asn, nb_r = get_nb_asn_r(asn, nb_name)
            r_ip = ext_infs[nb_name][0]
            if r_ip not in rib_in or own_net not in rib_in[r_ip]:
                vio_count += 1
                print(
                    f"  AS's own network {own_net} is not advertised to {nb_name} (AS{nb_asn} {nb_r})."
                )
            elif r_ip != rib_in[r_ip][own_net]["next-hop"]:
                vio_count += 1
                print(
                    f"  AS's own network {own_net} is advertised to {nb_name} (AS{nb_asn} {nb_r}) with wrong next-hop"
                    + f" (exp: {rib_in[r_ip][own_net]['next-hop']}, act: {r_ip})."
                )
            else:
                pass
        # check each router learns neighbors' network and the next-hop is correct
        # only warning, not check
        print("\nChecking each router is receiving eBGP neighbors' network...")
        for r_name in REGION_NAMES:
            bgp_route_json = get_r_bgp_route_json(asn, r_name)
            for nb_name, border_name in NB_CONN.items():
                if nb_name == "IXP":
                    continue
                # check_count += 1
                nb_asn, nb_r = get_nb_asn_r(asn, nb_name)
                nb_net = f"{nb_asn}.0.0.0/8"
                if nb_net not in bgp_route_json:
                    # vio_count += 1
                    print(
                        f"  {r_name} does not receive {nb_net} from {nb_name} ({nb_r})."
                    )
                elif len(bgp_route_json[nb_net]) != 1:
                    # vio_count += 1
                    print(
                        f"  {r_name} learns {nb_name}'s network (AS{nb_asn} {nb_r}) from invalid source."
                    )
                else:
                    act_peer = bgp_route_json[nb_net][0]["peerId"]
                    if border_name == r_name:
                        # peer id = nb intf
                        exp_peer = ext_infs[nb_name][1]
                    else:
                        # peer id = border router
                        exp_peer = get_exp_intf_ip("lo", asn, border_name)
                    if act_peer != exp_peer:
                        # vio_count += 1
                        print(
                            f"  {r_name} has invalid BGP next-hop to reach {nb_name} (AS{nb_asn} {nb_r})'s network (act: {act_peer}, exp: {exp_peer})."
                        )
    if not_checked:
        print("\n  Summary: Not all eBGP sessions are established, not checked.")
        points = 0.0
    else:
        print(
            f"\n  Summary: {check_count - vio_count}/{check_count} checks regarding"
            + " neighboring announcements sending succeeded."
        )
        points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_route_preference(
    asn, total_preferences, exp_best_after_withdraw, log_file=None
):
    """Check the as has the correct router preferences among all neighbors."""
    # TODO: how to check partial preference?
    print = partial(new_print, log_file=log_file)
    print("\nChecking expected route preferences are satisfied...")
    check_count = 0
    vio_count = 0

    ext_intfs = get_valid_ext_link_intfs(asn)
    not_checked = False
    if ext_intfs.keys() != NB_CONN.keys():
        not_checked = True

    else:
        asn_zone = get_as_to_zone(asn)
        nb_zone = random.choice(
            [zone for zone in range(1, MAX_ZONE + 1) if zone != asn_zone]
        )
        fake_asn = random.choice(get_zone_to_as_lst(nb_zone))
        fake_net = f"{fake_asn}.0.0.0/8"

        for nb_name in ext_intfs:
            if nb_name not in total_preferences:
                continue
            r_ip = ExtIntfs(*ext_intfs[nb_name]).r_ip
            nb_asn, nb_r = get_nb_asn_r(asn, nb_name)
            if nb_name != "IXP":
                fake_as_path = [nb_asn, fake_asn]
                community=None
            else:
                fake_as_path = [random.choice(get_ixp_tranit_asns(asn)), fake_asn]
                community = [f"{nb_asn}:{asn}"]
                
            announce_exabgp_route(r_ip, fake_net, next_hop="self", as_path=fake_as_path, community=community)
            print(
                f"  Announced network {fake_net} to {NB_CONN[nb_name]} from {nb_name} with AS-PATH {fake_as_path} and community {community}."
            )
        # check best route for fake net
        withdraw_stack = total_preferences

        while withdraw_stack:
            withdraw_nb = withdraw_stack.pop()
            if withdraw_nb:
                withdraw_exabgp_route(ExtIntfs(*ext_intfs[withdraw_nb]).r_ip, fake_net)
                print(f"\n  Withdrew {withdraw_nb}'s route.")
            exp_best_nbs_all = exp_best_after_withdraw[withdraw_nb]
            print(f"  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
            time.sleep(BGP_CONV_WAIT)
            # NOTE: need some tolerance for some exceptionally slow convergence
            print("  Checking each router's best route...")
            for r_name in REGION_NAMES:
                check_count += 1
                best_nh = get_best_ext_route_nh(asn, r_name, fake_net, new=True)
                exp_best_nbs = exp_best_nbs_all.copy()
                if not exp_best_nbs:
                    continue
                while exp_best_nbs:
                    exp_best = exp_best_nbs.pop()
                    border_r = NB_CONN[exp_best]
                    if (
                        r_name == border_r
                        and best_nh == ExtIntfs(*ext_intfs[exp_best]).nb_ip
                    ) or (
                        r_name != border_r
                        and best_nh == get_exp_intf_ip("lo", asn, border_r)
                    ):
                        break
                    if not exp_best_nbs:
                        vio_count += 1
                        if withdraw_nb:
                            print(
                                f"  {r_name} does not prefer one of "
                                + f"{'|'.join(exp_best_nbs_all)}'s routes after withdrawing "
                                + f"{withdraw_nb}'s route "
                                + f"(act next-hop: {best_nh})."
                            )
                        else:
                            print(
                                f"  {r_name} does not prefer one of "
                                + f"{'|'.join(exp_best_nbs_all)}'s routes among all eBGP neighbors. "
                                + f"(act next-hop: {best_nh})."
                            )

    if not_checked:
        print(
            "\n  Summary: Not all eBGP sessions are correctly established, not checked."
        )
        points = 0.0
    else:
        print(
            f"\n  Summary: {check_count - vio_count}/{check_count} route preference checks"
            + " succeed."
        )
        points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_nb_transit_rules(asn, log_file=None):
    """Check whether the as follows the transit rules in business relationship and
    the inbound preferences."""

    print = partial(new_print, log_file=log_file)

    def get_exp_transit_nb(nb_name):
        """Return a list of neighbors that should be transited
        to when the as receives routes from nb_name."""
        if nb_name == "CUST1" or nb_name == "CUST2":
            return [nb for nb in NB_CONN if nb != nb_name]
        else:
            return ["CUST1", "CUST2"]

    print("\nChecking the expected transit policies are satisfied...")
    check_count = 0
    vio_count = 0

    ext_intfs = get_valid_ext_link_intfs(asn)
    nb_ip_2_name = {
        ExtIntfs(*ext_intfs[nb_name]).r_ip: nb_name for nb_name in ext_intfs
    }
    not_checked = False
    if ext_intfs.keys() != NB_CONN.keys():
        not_checked = True

    else:
        asn_zone = get_as_to_zone(asn)
        nb_zone = random.choice(
            [zone for zone in range(1, MAX_ZONE + 1) if zone != asn_zone]
        )
        fake_asns = random.sample(get_zone_to_as_lst(nb_zone), len(NB_CONN))
        nb_names = list(NB_CONN.keys())
        nb_to_routes = {
            nb_names[i]: f"{fake_asns[i]}.0.0.0/8" for i in range(len(fake_asns))
        }
        # announce fake routes
        for nb_name in ext_intfs:
            r_ip = ext_intfs[nb_name][0]
            nb_asn, nb_r = get_nb_asn_r(asn, nb_name)
            fake_asn = int(nb_to_routes[nb_name].split(".")[0])
            if nb_asn in IXP_ASNS:
                fake_as_path = [random.choice(get_ixp_tranit_asns(asn)), fake_asn]
                announce_exabgp_route(
                    r_ip,
                    nb_to_routes[nb_name],
                    next_hop="self",
                    community=[f"{nb_asn}:{asn}"],
                    as_path=fake_as_path,
                )
            else:
                fake_as_path = [nb_asn, fake_asn]
                announce_exabgp_route(
                    r_ip, nb_to_routes[nb_name], next_hop="self", as_path=fake_as_path
                )
            print(
                f"  Announced network {nb_to_routes[nb_name]} to {NB_CONN[nb_name]} from {nb_name} with AS-PATH {fake_as_path}."
            )
        # check exabgp receives each route exactly from the expected transit
        # neighbor
        print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        time.sleep(BGP_CONV_WAIT)
        rib_in = get_exabgp_rib_in()
        for nb_name in ext_intfs:
            check_count += len(NB_CONN)
            ann_net = nb_to_routes[nb_name]
            act_transit_nb = [nb for nb in rib_in if ann_net in rib_in[nb]]
            exp_transit_nb = get_exp_transit_nb(nb_name)

            missed_nb = [
                nb
                for nb in exp_transit_nb
                if ExtIntfs(*ext_intfs[nb]).r_ip not in act_transit_nb
            ]
            wrong_nb = [
                nb_ip_2_name[nb_ip]
                for nb_ip in act_transit_nb
                if nb_ip_2_name[nb_ip] not in exp_transit_nb
            ]
            if (nb_name == "CUST1" or nb_name == "CUST2") and [nb_name] == wrong_nb:
                wrong_nb = []
            if missed_nb or wrong_nb:
                vio_count += len(missed_nb) + len(wrong_nb)
            for nb in missed_nb:
                print(f"  {nb_name}-->{nb} transit is missing.")
            for nb in wrong_nb:
                print(f"  {nb_name}-->{nb} transit should not exist.")

        # withdraw routes
        print()
        for nb_name in ext_intfs:
            r_ip = ExtIntfs(*ext_intfs[nb_name]).r_ip
            withdraw_exabgp_route(r_ip, nb_to_routes[nb_name])
            print(f"  Withdrew {nb_name}'s route.")

    if not_checked:
        print(
            "\n  Summary: Not all eBGP sessions are correctly established, not checked."
        )
        points = 0.0
    else:
        print(
            f"\n  Summary: {check_count - vio_count}/{check_count} transit checks"
            + " succeed."
        )
        points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_inbound_preference(asn, log_file=None):
    """Check exabgp prefers asn's network received from CUST1 over CUST2,
    and prefers asn's network received from PROV1 over PROV2."""
    print = partial(new_print, log_file=log_file)

    print("\nChecking the expected inbound policies are satisfied...")
    check_count = 0
    vio_count = 0

    ext_intfs = get_valid_ext_link_intfs(asn)
    not_checked = False
    if ext_intfs.keys() != NB_CONN.keys():
        not_checked = True

    else:
        ann_net = f"{asn}.0.0.0/8"
        print(
            f"\n  Checking the inbound preference between PROV1 and PROV2 for {ann_net}..."
        )
        check_count += 1
        # compare the preference
        # NOTE: assume prov1 should be preferred
        prov1_ip = ExtIntfs(*ext_intfs["PROV1"]).r_ip
        prov2_ip = ExtIntfs(*ext_intfs["PROV2"]).r_ip
        prefer = compare_route_preference(
            prov1_ip, prov2_ip, ann_net, log_file=log_file
        )
        expected_prefer_prov = prov2_ip if asn % 2 == 0 else prov1_ip
        if prefer != expected_prefer_prov:
            vio_count += 1
            print(
                f"  PROV1 is not preferred to PROV2 for {ann_net} (wrong as-path or MED config)."
            )
        print(
            f"\n  Checking the inbound preference between CUST1 and CUST2 for {ann_net}..."
        )
        check_count += 1
        cust1_ip = ExtIntfs(*ext_intfs["CUST1"]).r_ip
        cust2_ip = ExtIntfs(*ext_intfs["CUST2"]).r_ip
        prefer = compare_route_preference(
            cust1_ip, cust2_ip, ann_net, log_file=log_file
        )
        expected_prefer_cust = cust2_ip if asn % 2 == 0 else cust1_ip
        if prefer != expected_prefer_cust:
            vio_count += 1
            print(
                f"  CUST1 is not preferred to CUST2 for {ann_net} (wrong as-path or MED config)."
            )

    if not_checked:
        print(
            "\n  Summary: Not all eBGP sessions are correctly established, not checked."
        )
        points = 0.0
    else:
        print(
            f"\n  Summary: {check_count - vio_count}/{check_count} inbound checks"
            + " succeed."
        )
        points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_ixp_community(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\nChecking correct community values are configured for IXP...")
    ext_intfs = get_valid_ext_link_intfs(asn)
    not_checked = False
    if "IXP" not in ext_intfs:
        not_checked = True

    else:
        check_count = 0
        vio_count = 0
        # print(ext_intfs)
        ixp_asn, _ = get_nb_asn_r(asn, "IXP")
        r_ip = ExtIntfs(*ext_intfs["IXP"]).r_ip
        exp_ixp_comm = {
            f"{ixp_asn}:{peer_asn}" for peer_asn in get_ixp_tranit_asns(asn)
        }
        # NOTE: each as may have different number of routes advertised to IXP, so not
        # count them
        act_ixp_comm = {
            comm
            for _, attrs in get_exabgp_rib_in()[r_ip].items()
            for comm in attrs["community"]
        }
        check_count += 1
        if exp_ixp_comm != act_ixp_comm:
            vio_count += 1
            missed_comm = exp_ixp_comm - act_ixp_comm
            print(f"  Annoucements sent to IXP miss communities {missed_comm}.")
            wrong_comm = act_ixp_comm - exp_ixp_comm
            print(f"  Annoucements sent to IXP contain wrong communities {wrong_comm}.")

    if not_checked:
        print("\n  Summary: EBGP session with IXP is not established, not checked.")
        points = 0.0
    else:
        points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_ixp_transit(asn, log_file=None):
    """Check AS only transits specific peers' route to IXP."""
    # check the as peers with only expected peers via ixp, i.e., communities are
    # correct
    print = partial(new_print, log_file=log_file)
    print("\nChecking the expected transit policies are satisfied for IXP...")
    ext_intfs = get_valid_ext_link_intfs(asn)
    not_checked = False
    if "IXP" not in ext_intfs:
        not_checked = True

    else:
        check_count = 0
        vio_count = 0
        no_transit_at_all = False
        # print("  Checking correct community values are configured for IXP...")
        # # print(ext_intfs)
        ixp_asn, _ = get_nb_asn_r(asn, "IXP")
        r_ip = ExtIntfs(*ext_intfs["IXP"]).r_ip
        # exp_ixp_comm = {
        #     f"{ixp_asn}:{peer_asn}" for peer_asn in get_ixp_tranit_asns(asn)
        # }
        # # NOTE: each as may have different number of routes advertised to IXP, so not
        # # count them
        # act_ixp_comm = {
        #     comm
        #     for _, attrs in get_exabgp_rib_in()[r_ip].items()
        #     for comm in attrs["community"]
        # }
        # check_count += 1
        # if exp_ixp_comm != act_ixp_comm:
        #     vio_count += 1
        #     missed_comm = exp_ixp_comm - act_ixp_comm
        #     print(f"  Annoucements sent to IXP miss communities {missed_comm}.")
        #     wrong_comm = act_ixp_comm - exp_ixp_comm
        #     print(f"  Annoucements sent to IXP contain wrong communities {wrong_comm}.")

        print("  Checking AS accepts routes advertised by another zone via IXP...")
        check_count += 1
        asn_zone = get_as_to_zone(asn)
        nb_zone = random.choice(
            [zone for zone in range(1, MAX_ZONE + 1) if zone != asn_zone]
        )
        fake_asn = random.choice(get_zone_to_as_lst(nb_zone))
        fake_net = f"{fake_asn}.0.0.0/8"
        fake_as_path = [random.choice(get_ixp_tranit_asns(asn)), fake_asn]
        r_name = NB_CONN["IXP"]
        announce_exabgp_route(
            r_ip,
            fake_net,
            next_hop="self",
            as_path=fake_as_path,
            community=[f"{ixp_asn}:{asn}"],
        )
        print(
            f"  Announced network {fake_net} to {r_name} from IXP (AS{ixp_asn}) with as-path {fake_as_path}."
        )
        print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        time.sleep(BGP_CONV_WAIT)
        bgp_r_json = get_r_bgp_route_json(asn, r_name, new=True)
        ixp_ip = ExtIntfs(*ext_intfs["IXP"]).nb_ip
        if fake_net not in bgp_r_json:
            vio_count += 1
            no_transit_at_all = True
            # for route in bgp_r_json[fake_net]:
            #     if route["peerId"] == ixp_ip:
            #         vio_count += 1
            print(
                f"  {r_name} should not have dropped route {fake_net} originated by AS{fake_asn} via IXP."
            )
        withdraw_exabgp_route(r_ip, fake_net)
        print(f"  Withdrew route {fake_net} from IXP.")

        # check the as denies routes advertised by peers in the same region
        print(
            "  Checking AS denies routes advertised by peers in the same zone (the same side)..."
        )
        check_count += 1
        asn_zone = get_as_to_zone(asn)
        if asn % 2 == 0:
            fake_asn = random.choice(
                [
                    nb_asn
                    for nb_asn in get_zone_to_as_lst(asn_zone)
                    if asn != nb_asn and nb_asn % 2 == 0
                ]
            )
        else:
            fake_asn = random.choice(
                [
                    nb_asn
                    for nb_asn in get_zone_to_as_lst(asn_zone)
                    if asn != nb_asn and nb_asn % 2 == 1
                ]
            )
        fake_net = f"{fake_asn}.0.0.0/8"
        fake_as_path = [fake_asn]
        r_name = NB_CONN["IXP"]
        announce_exabgp_route(
            r_ip,
            fake_net,
            next_hop="self",
            as_path=fake_as_path,
            community=[f"{ixp_asn}:{asn}"],
        )
        print(
            f"  Announced network {fake_net} to {r_name} from IXP (AS{ixp_asn}) with as-path {fake_as_path}."
        )
        print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        time.sleep(BGP_CONV_WAIT)
        bgp_r_json = get_r_bgp_route_json(asn, r_name, new=True)
        ixp_ip = ExtIntfs(*ext_intfs["IXP"]).nb_ip
        if fake_net in bgp_r_json:
            for route in bgp_r_json[fake_net]:
                if route["peerId"] == ixp_ip:
                    vio_count += 1
                    print(
                        f"  {r_name} should not have accepted route {fake_net} originated by AS{fake_asn} via IXP."
                    )
                    break
        withdraw_exabgp_route(r_ip, fake_net)
        print(f"  Withdrew route {fake_net} from IXP.")

        print(
            "  Checking AS denies routes containing AS in the same zone (the same side)..."
        )
        check_count += 1
        nb_zone = random.choice(
            [zone for zone in range(1, MAX_ZONE + 1) if zone != asn_zone]
        )
        nb_asn = random.choice(get_zone_to_as_lst(nb_zone))
        fake_net = f"{nb_asn}.0.0.0/8"
        fake_as_path = [random.choice(get_ixp_tranit_asns(asn)), fake_asn, nb_asn]
        announce_exabgp_route(
            r_ip,
            fake_net,
            next_hop="self",
            as_path=fake_as_path,
            community=[f"{ixp_asn}:{asn}"],
        )
        print(
            f"  Announced network {fake_net} to {r_name} from IXP (AS{ixp_asn}) with as-path {fake_as_path}."
        )
        print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        time.sleep(BGP_CONV_WAIT)
        bgp_r_json = get_r_bgp_route_json(asn, r_name, new=True)
        ixp_ip = ExtIntfs(*ext_intfs["IXP"]).nb_ip
        if fake_net in bgp_r_json:
            for route in bgp_r_json[fake_net]:
                if route["peerId"] == ixp_ip:
                    vio_count += 1
                    print(
                        f"  {r_name} should not have accepted route {fake_net} relayed by AS{fake_asn} via IXP."
                    )
                    break
        withdraw_exabgp_route(r_ip, fake_net)
        print(f"  Withdrew route {fake_net} from IXP.")

        # # announce a route originated from a different region but replayed by an AS in the same region
        # # this fake as-path cannot exist, but it should be fine
        # print(
        #     "  Checking AS denies routes advertised by peers in the same zone (the other side)..."
        # )
        # check_count += 1
        # asn_zone = get_as_to_zone(asn)
        # if asn % 2 == 0:
        #     fake_asn = random.choice(
        #         [
        #             nb_asn
        #             for nb_asn in get_zone_to_as_lst(asn_zone)
        #             if asn != nb_asn and nb_asn % 2 == 1
        #         ]
        #     )
        # else:
        #     fake_asn = random.choice(
        #         [
        #             nb_asn
        #             for nb_asn in get_zone_to_as_lst(asn_zone)
        #             if asn != nb_asn and nb_asn % 2 == 0
        #         ]
        #     )
        # fake_net = f"{fake_asn}.0.0.0/8"
        # fake_as_path = [fake_asn]
        # r_name = NB_CONN["IXP"]
        # announce_exabgp_route(
        #     r_ip,
        #     fake_net,
        #     next_hop="self",
        #     as_path=fake_as_path,
        #     community=[f"{ixp_asn}:{asn}"],
        # )
        # print(
        #     f"  Announced network {fake_net} to {r_name} from IXP (AS{ixp_asn}) with as-path {fake_as_path}."
        # )
        # print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        # time.sleep(BGP_CONV_WAIT)
        # bgp_r_json = get_r_bgp_route_json(asn, r_name, new=True)
        # ixp_ip = ExtIntfs(*ext_intfs["IXP"]).nb_ip
        # if fake_net in bgp_r_json:
        #     for route in bgp_r_json[fake_net]:
        #         if route["peerId"] == ixp_ip:
        #             vio_count += 1
        #             print(
        #                 f"  {r_name} should not have accepted route {fake_net} originated by AS{fake_asn} via IXP."
        #             )
        #             break
        # withdraw_exabgp_route(r_ip, fake_net)
        # print(f"  Withdrew route {fake_net} from IXP.")

    if not_checked:
        print("\n  Summary: EBGP session with IXP is not established, not checked.")
        points = 0.0
    else:
        if no_transit_at_all:
            points = 0.0
            print("\n  Summary: AS does not have valid IXP transit.")
        else:
            print(
                f"\n  Summary: {check_count - vio_count}/{check_count} IXP transit checks"
                + " succeed."
            )
            points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_rpki_not_found(asn, log_file=None):
    """Check AS has configured RPKI."""
    # generate a random /32 fake route from one nb
    print = partial(new_print, log_file=log_file)
    print("\nChecking AS has correctly configured RPKI (not found)...")
    not_checked = False
    ext_intfs = get_valid_ext_link_intfs(asn)
    if len(ext_intfs) != len(NB_CONN):
        not_checked = True
    else:
        # advertise a not-found route
        check_count = 0
        vio_count = 0
        fake_asn = random.choice(range(MAX_AS, MAX_AS + 10))
        fake_net = f"{fake_asn}.0.0.0/8"
        nb_name = random.choice([nb_r for nb_r in NB_CONN if nb_r != "IXP"])
        nb_asn, _ = get_nb_asn_r(asn, nb_name)
        r_ip = ExtIntfs(*get_valid_ext_link_intfs(asn)[nb_name]).r_ip
        r_name = NB_CONN[nb_name]
        fake_asn_path = [nb_asn, fake_asn]
        announce_exabgp_route(
            r_ip, fake_net, next_hop="self", as_path=[nb_asn, fake_asn - 1]
        )
        print(
            f"  Announced network {fake_net} to {r_name} from {nb_name} (AS{nb_asn}) with as-path {fake_asn_path}."
        )
        print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        time.sleep(BGP_CONV_WAIT)
        # check each router does not accept the fake route
        for r_name in REGION_NAMES:
            check_count += 1
            bgp_json = get_r_bgp_route_json(asn, r_name, new=True)
            if fake_net not in bgp_json:
                vio_count += 1
                print(f"  {r_name} should not have dropped route {fake_net}.")

        withdraw_exabgp_route(r_ip, fake_net)
        print(f"  Withdrew route {fake_net} from {nb_name}.")

    if not_checked:
        print(
            "\n  Summary: Not all eBGP sessions are correctly established, not checked."
        )
        points = 0.0
    else:
        print(
            f"\n  Summary: {check_count - vio_count}/{check_count} RPKI checks"
            + " succeed."
        )
        points = (check_count - vio_count) * 1.0 / check_count
    return points


def check_rpki_invalid(asn, log_file=None):
    """Check AS has configured RPKI."""
    # generate a random /32 fake route from one nb
    print = partial(new_print, log_file=log_file)
    print("\nChecking AS has correctly configured RPKI (invalid)...")
    not_checked = False
    ext_intfs = get_valid_ext_link_intfs(asn)
    if len(ext_intfs) != len(NB_CONN):
        not_checked = True
    else:
        # NOTE: can only advertise fake route for as that have configured RPKI
        # fake_asn = random.choice(get_zone_to_as_lst(MAX_ZONE))
        fake_asn = 11
        fake_net = f"{fake_asn}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}/32"
        nb_name = random.choice([nb_r for nb_r in NB_CONN if nb_r != "IXP"])
        nb_asn, _ = get_nb_asn_r(asn, nb_name)
        r_ip = ExtIntfs(*get_valid_ext_link_intfs(asn)[nb_name]).r_ip
        r_name = NB_CONN[nb_name]
        fake_asn_path = [nb_asn, fake_asn - 1]
        announce_exabgp_route(
            r_ip, fake_net, next_hop="self", as_path=[nb_asn, fake_asn - 1]
        )
        print(
            f"  Announced network {fake_net} to {r_name} from {nb_name} (AS{nb_asn}) with as-path {fake_asn_path}."
        )
        print(f"\n  Waiting {BGP_CONV_WAIT} sec for AS to converge...")
        time.sleep(BGP_CONV_WAIT)
        # check each router does not accept the fake route
        check_count = 0
        vio_count = 0
        for r_name in REGION_NAMES:
            check_count += 1
            bgp_json = get_r_bgp_route_json(asn, r_name, new=True)
            if fake_net in bgp_json:
                vio_count += 1
                print(f"  {r_name} should not have accepted route {fake_net}.")

        withdraw_exabgp_route(r_ip, fake_net)
        print(f"  Withdrew route {fake_net} from {nb_name}.")

    if not_checked:
        print(
            "\n  Summary: Not all eBGP sessions are correctly established, not checked."
        )
        points = 0.0
    else:
        print(
            f"\n  Summary: {check_count - vio_count}/{check_count} RPKI checks"
            + " succeed."
        )
        points = (check_count - vio_count) * 1.0 / check_count
    return points

# --- Question Functions (Adapted from original grader.py) ---

def q1_1(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q1.1: L2 IP addresses, default gateway and VLAN.#####")
    return check_l2_conn_in_dc(asn, dcn=True, dcs=True, log_file=log_file)

def q1_2(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q1.2: L3 IP address and OSPF set up.#####")
    points_1 = check_l3_intf_config(asn, log_file=log_file)
    points_2 = check_l3_dcn_host_conn(asn, log_file=log_file)
    return points_1 * 0.5 + points_2 * 0.5

def q1_3(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q1.3: OSPF load balancing.#####")
    points_1 = check_l3_load_balancing(
        asn, "MILA", "MUNI",
        [["MILA", "MUNI"],["MILA", "ZURI", "MUNI"],["MILA", "ZURI", "FRAN", "MUNI"]],
        log_file=log_file)
    points_2 = check_l3_load_balancing(
        asn, "MUNI", "MILA",
        [["MUNI", "MILA"],["MUNI", "ZURI", "MILA"],["MUNI", "FRAN", "ZURI", "MILA"]],
        log_file=log_file)
    return (points_1 + points_2) / 2

def q1_4(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q1.4: IPv6 address and tunnel.#####")
    points_1 = check_l2_conn_in_dc(asn, v6=True, dcn=True, dcs=True, log_file=log_file)
    points_2 = check_across_dc_v6_conn(asn, log_file=log_file)
    return points_1 * 0.5 + points_2 * 0.5

def q2_1(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q2.1: iBGP full mesh.#####")
    return check_ibgp_full_mesh(asn, log_file=log_file)

def q2_2(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q2.2: eBGP sessions.#####")
    points_1 = check_as_intf_config(asn, log_file=log_file)
    points_2 = check_nb_route_send_rcv(asn, log_file=log_file)
    return points_1 * 0.5 + points_2 * 0.5

def q2_3(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q2.3: local preference and no transit.#####")
    points_1 = check_route_preference(
        asn,
        ["PROV2", "PROV1", "IXP", "PEER1", "CUST2", "CUST1", ""],
        {
            "": ["CUST1", "CUST2"], "CUST1": ["CUST2"], "CUST2": ["PEER1", "IXP"],
            "PEER1": ["IXP"], "IXP": ["PROV1", "PROV2"], "PROV1": ["PROV2"], "PROV2": [],
        },
        log_file=log_file,
    )
    points_2 = check_nb_transit_rules(asn, log_file=log_file)
    return points_1 * 0.5 + points_2 * 1.25

def q2_4(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q2.4: IXP community and filter.#####")
    points_1 = check_ixp_community(asn, log_file=log_file)
    points_2 = check_ixp_transit(asn, log_file=log_file)
    return points_1 * 0.5 + points_2 * 0.5

def q2_5(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q2.5: inbound preference.#####")
    return check_inbound_preference(asn, log_file=log_file)

def q2_6(asn, log_file=None):
    print = partial(new_print, log_file=log_file)
    print("\n#####Q2.6: RPKI.#####")
    points_1 = check_rpki_not_found(asn, log_file=log_file)
    points_2 = check_rpki_invalid(asn, log_file=log_file)
    return points_1 * 0.5 + points_2 * 0.5

def run_all_checks_for_as(asn, log_file):
    """Runs the full suite of grading checks for a single ASN."""
    total_points = []
    questions = [
        q1_1, q1_2, q1_3, q1_4,
        q2_1, q2_2, q2_3, q2_4, q2_5, q2_6
    ]
    for question in questions:
        try:
            points = question(asn, log_file=log_file)
            total_points.append(points)
        except Exception as e:
            new_print(f"Error running {question.__name__} for AS {asn}: {e}", log_file=log_file)
            total_points.append(0)
    return total_points
