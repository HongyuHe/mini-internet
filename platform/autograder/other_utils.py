#!/usr/bin/env python3

"""Inner common helper functions."""

import ipaddress
import re
import sys

import networkx as nx


def mask_to_cidr(ip, mask):
    """Return the cidr subnet format given the ip and masks."""
    return str(ipaddress.ip_interface(f"{ip}/{mask}"))


def create_graph_from_link_cost(cost):
    """Return the directed graph constructed from the given cost dict."""
    g = nx.DiGraph()
    g.add_weighted_edges_from(cost)
    return g


def compute_all_shortest_paths(graph, src, dst):
    """Return a list of directed shortest paths from src to dst."""
    try:
        sp = list(nx.all_shortest_paths(graph, src, dst, weight="weight"))
        return sp
    except:
        return []


def is_v6_subnet(subnet):
    """Check whether the given subnet is ipv6."""
    # TODO: make it better
    return ":" in subnet


def is_v4_subnet(subnet):
    """Check whether the given subnet is ipv4."""
    pattern = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")
    if pattern.match(subnet):
        return True
    return False


def is_within_v4_subnet(subnet_a, subnet_b):
    """Check whether subunet_a is within subunet_b."""
    try:
        network_a = ipaddress.IPv4Network(subnet_a, strict=False)
        network_b = ipaddress.IPv4Network(subnet_b, strict=False)

        return network_a.subnet_of(network_b)
    except ValueError:
        # print("Invalid IPv4 subnet provided.")
        return False


class Logger(object):
    """A logger."""

    def __init__(self, log_file):
        self.terminal = sys.stdout
        self.log = open(log_file, "w")

    def write(self, message):
        """Specify where the log writes to."""
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        """Overloading flush."""
        pass


def new_print(*args, **kwargs):
    log_file = kwargs.pop("log_file", None)
    if log_file is not None:
        with open(log_file, "a") as f:
            print(*args, file=f, **kwargs)
    print(*args, **kwargs)
