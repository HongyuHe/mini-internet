### How to run a batch of group configs

1. fill the list of group numbers in `asn_all.txt`, the full group list can be found in `complete_asns.txt`
2. run `python3 pull_and_parse_gitlab_configs.py`, it clones gitlab configs to `gitlab_configs` and parse
3. manually move actual configs under `groupX/`, and record the config date shown in the config folder/tar in the google doc, if there is no tar or nested folder, use the last commit date
4. `cd gitlab_configs` and run `./scripts.sh` to replace correct switch or L2 host folders from `history_config/`
5. backup `gitlab_configs` to `gitlab_configs_backup` 
6. run `./parse_gitlab_config.sh` to parse the configs again
7. run `./start_grader.sh asn_all.txt` to grade all groups.


### TODO

- [ ] change `unsafe-vrps` to `"accept"` in routinator image