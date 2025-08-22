#!/usr/bin/env python3

"""Inner functions for ExaBGP."""
from functools import partial
import re
from collections import defaultdict
from ctn_utils import exec_ctn
from other_utils import new_print
from sdas_utils import get_shadow_ctn_name


def announce_exabgp_route(
    neighbor, prefix, next_hop, local_pref=None, med=None, community=None, as_path=None
):
    """Announce route to shadow as."""
    ann = f"neighbor {neighbor} announce route {prefix} next-hop {next_hop} "
    if isinstance(local_pref, int):
        ann += f"local-preference {local_pref} "
    if isinstance(med, int):
        ann += f"med {med} "
    if isinstance(community, list):
        ann += f"community [ {' '.join(community)} ] "
    if isinstance(as_path, list):
        ann += f"as-path [ {' '.join(str(asn) for asn in as_path)} ] "
    cmd = [f"exabgpcli {ann}"]
    exec_ctn(get_shadow_ctn_name("EXABGP"), cmd, shell="bash")


def withdraw_exabgp_route(neighbor, prefix):
    """Withdraw route from shadow as."""
    ann = f"neighbor {neighbor} withdraw route {prefix}"
    cmd = [f"exabgpcli {ann}"]
    exec_ctn(get_shadow_ctn_name("EXABGP"), cmd, shell="bash")


def get_exabgp_rib_in():
    """Return and parse the result of `exabgpcli show adj-rib in extensive`."""
    # extenive: {neighbor: {route: {next_hop, med, as_path, community}}}
    rib_in = defaultdict(lambda: defaultdict(dict))
    cmd = ["exabgpcli show adj-rib in extensive"]
    output = (
        exec_ctn(get_shadow_ctn_name("EXABGP"), cmd, shell="bash").strip().split("\n")
    )
    if output == [""]:
        # not receive route from student as
        return rib_in
    for entry in output:
        neighbor = re.search(r"neighbor (\S+)", entry).group(1)
        route = re.search(r"ipv4 unicast (\S+)", entry).group(1)
        next_hop_match = re.search(r"next-hop (\S+)", entry)
        next_hop = next_hop_match.group(1) if next_hop_match else ""

        as_path_match = re.search(r"as-path \[ (.+?) \]", entry)
        as_path = (
            [int(i) for i in as_path_match.group(1).split()] if as_path_match else []
        )

        community_match = re.search(r"community \[ (.+?) \]", entry)
        community = community_match.group(1).split() if community_match else []

        med_match = re.search(r"med (\d+)", entry)
        # NOTE: assume default med is 0
        med = int(med_match.group(1)) if med_match else 0

        rib_in[neighbor][route] = {
            "next-hop": next_hop,
            "as-path": as_path,
            "community": community,
            "med": med,
        }
    return rib_in


def compare_route_preference(nb_a, nb_b, route, log_file=None):
    """Given two nb and a route, return the neighbor with higher
    prefer`ence in exabgp."""
    print = partial(new_print, log_file=log_file)
    rib_in = get_exabgp_rib_in()
    if nb_a not in rib_in or nb_b not in rib_in:
        return ""
    if route not in rib_in[nb_a] or route not in rib_in[nb_b]:
        return ""
    # assert nb_a in rib_in and nb_b in rib_in
    # assert route in rib_in[nb_a] and route in rib_in[nb_b]
    route_a = rib_in[nb_a][route]
    print(f"  route_1: {route_a}")
    route_b = rib_in[nb_b][route]
    print(f"  route_2: {route_b}")
    if len(route_a["as-path"]) < len(route_b["as-path"]):
        return nb_a
    elif len(route_a["as-path"]) > len(route_b["as-path"]):
        return nb_b
    elif route_a["med"] < route_b["med"]:
        return nb_a
    elif route_b["med"] < route_a["med"]:
        return nb_b
    else:
        return ""
