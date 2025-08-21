#!/usr/bin/env python3

"""Provides grading functions for separate questions on a LIVE environment."""

import random
from functools import partial

import live_mnet_utils as mnet
import exabgp_manager
from other_utils import new_print

# All the check functions (check_l2_conn_in_dc, check_l3_intf_config, etc.)
# from the original grader.py would be placed here. They should work with
# minimal changes, as the main modification is in the utility layer
# (live_mnet_utils.py) which they call into.

# Example of an adapted check function:
def q1_1(asn, log_file=None):
    print_func = partial(new_print, log_file=log_file)
    print_func("\n##### Q1.1: L2 IP addresses, default gateway and VLAN. #####")
    # The original check_l2_conn_in_dc function would be called here.
    # It will now automatically use live_mnet_utils to query live containers.
    # points = check_l2_conn_in_dc(asn, dcn=True, dcs=True, log_file=log_file)
    points = random.random() # Placeholder for actual check
    print_func(f"L2 Connectivity check points: {points:.2f}")
    return points

def q2_3(asn, log_file=None):
    print_func = partial(new_print, log_file=log_file)
    print_func("\n##### Q2.3: BGP Policies (Local Pref & Transit) #####")
    # This check would now use exabgp_manager to announce and withdraw routes
    # from the dedicated test peer.
    # For example:
    # exabgp_manager.announce_exabgp_route(neighbor_ip, test_prefix, ...)
    # best_path = mnet.get_best_ext_route_nh(asn, router, test_prefix)
    # ... comparison logic ...
    points = random.random() # Placeholder for actual check
    print_func(f"BGP Policy check points: {points:.2f}")
    return points


def run_all_checks_for_as(asn, log_file):
    """Runs the full suite of grading checks for a single ASN."""
    # This function replaces the main block from the original grader.py
    total_points = []
    
    # A simplified list of checks for demonstration
    questions = [q1_1, q2_3] # Add all other qX_Y functions here

    for question in questions:
        try:
            points = question(asn, log_file=log_file)
            total_points.append(points)
        except Exception as e:
            new_print(f"Error running {question.__name__} for AS {asn}: {e}", log_file=log_file)
            total_points.append(0)

    return total_points
