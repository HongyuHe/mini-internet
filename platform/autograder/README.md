# Live Autograder System

This autograder is designed to test student AS configurations in a live, running Mini-Internet environment. It does **not** create or destroy student containers.

## Core Components

- **`run_live_grader.py`**: The main entry point for the grading system. It initializes the ExaBGP test peer and iterates through the list of student ASNs to grade each one.

- **`live_grader.py`**: Contains the main grading logic, with functions for each specific check (e.g., L2/L3 connectivity, BGP policies, RPKI). It's adapted from the original `grader.py`.

- **`exabgp_manager.py`**: A new module responsible for managing the ExaBGP test peer. It starts the container, dynamically configures it to peer with the student AS currently under test, and provides functions to announce/withdraw test routes.

- **`live_mnet_utils.py`**: A modified version of the original `mnet_utils.py`. This is a critical component. All functions that interact with containers have been updated to target the live student containers (e.g., `3_ZURIrouter`) instead of a temporary shadow container.

- **`ctn_utils.py` / `other_utils.py`**: Utility libraries for Docker interaction and other helper functions, mostly unchanged from the original.

- **`configs/`**: A directory containing necessary configuration files for the grader, such as the AS-level link definitions.
