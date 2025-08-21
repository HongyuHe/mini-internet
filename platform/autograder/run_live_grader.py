#!/usr/bin/env python3

"""Main entry point for the live autograder."""

import sys
import time
import os
from functools import partial

import exabgp_manager
import live_grader
from other_utils import new_print, Logger

REPORT_DIR = f"reports/{time.strftime('%Y-%m-%d_%H-%M-%S')}"


def main():
    """Initializes the test environment and grades all ASNs from the input file."""
    if len(sys.argv) < 2:
        print("Usage: python3 run_live_grader.py <asn_file>")
        sys.exit(1)

    asn_path = sys.argv[1]
    with open(asn_path, "r") as f:
        asn_lst = [int(asn) for asn in f.read().split()]

    print("Starting the live autograder system...")
    os.makedirs(REPORT_DIR, exist_ok=True)

    # Start a single ExaBGP container for all test sessions
    exabgp_manager.start_exabgp_container()

    for cur_asn in asn_lst:
        log_file = os.path.join(REPORT_DIR, f"g{cur_asn}.txt")
        with open(log_file, "w") as f:
            pass  # Clear old log
        
        print_func = partial(new_print, log_file=log_file)
        start_time = time.time()
        print_func(f"############# Analyzing AS {cur_asn} ################")

        try:
            # Configure ExaBGP to peer with the current AS
            print_func("\nConfiguring ExaBGP for AS {cur_asn}...")
            exabgp_manager.configure_exabgp_for_as(cur_asn)
            time.sleep(15) # Wait for BGP sessions to establish

            # Run all checks
            total_points = live_grader.run_all_checks_for_as(cur_asn, log_file)

            # Print final grade
            print_func(f"\n############# Grades for AS {cur_asn} ##############")
            for i, p in enumerate(total_points):
                if i <= 3:
                    print_func(f"    Task 1.{i+1}: {p:.2f}")
                else:
                    print_func(f"    Task 2.{i-3}: {p:.2f}")
            grade = (1.0 + sum(total_points) / 2)
            print_func(f"    Grade: {grade:.2f}")

        except Exception as e:
            print_func(f"\n!!!!!! An error occurred while grading AS {cur_asn}: {e} !!!!!!")
        finally:
            # Clear the ExaBGP configuration for the current AS
            exabgp_manager.clear_exabgp_config()
            time_lapse = time.time() - start_time
            print_func(
                "############# Analyzing AS {} takes {:.3f}s #############".format(
                    cur_asn,
                    time_lapse,
                )
            )
            print_func()

    print("\nAll specified ASNs have been graded.")
    print(f"Reports are available in the {REPORT_DIR} directory.")

if __name__ == "__main__":
    main()
