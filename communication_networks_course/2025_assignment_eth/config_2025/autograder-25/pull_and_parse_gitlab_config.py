import requests
import datetime
import pytz
import subprocess
import os
import shutil

GITLAB_API_BASE_URL = "https://gitlab.ethz.ch/api/v4"
ACCESS_TOKEN = "V-zCAxDdfzVAGKtFx7Vo"
GROUP_ID = 82329
TIME_T = "2025-04-29T23:59:59Z"


def get_projects(group_id):
    url = f"{GITLAB_API_BASE_URL}/groups/{group_id}/projects"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers, params={"per_page": 100})
    response.raise_for_status()
    return response.json()


def get_last_commit(project_id):
    url = f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers, params={"per_page": 1})

    response.raise_for_status()
    commits = response.json()

    if commits:
        return commits[0]  # Return the first commit in the list
    else:
        return None  # Return None if there are no commits


# def get_commits_before_time_t(project_id, time_t):
#     url = f"{GITLAB_API_BASE_URL}/projects/{project_id}/repository/commits"
#     headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
#     response = requests.get(
#         url, headers=headers, params={"per_page": 100, "until": time_t}
#     )
#     response.raise_for_status()
#     return response.json()


# def find_closest_commit(commits, time_t):
#     time_t_datetime = datetime.datetime.fromisoformat(time_t.rstrip("Z")).replace(
#         tzinfo=pytz.UTC
#     )
#     closest_commit = None
#     closest_time_diff = None

#     for commit in commits:
#         commit_time = datetime.datetime.fromisoformat(
#             commit["committed_date"].rstrip("Z")
#         ).replace(tzinfo=pytz.UTC)
#         time_diff = time_t_datetime - commit_time

#         if closest_time_diff is None or time_diff < closest_time_diff:
#             closest_time_diff = time_diff
#             closest_commit = commit

#     return closest_commit


def clone_and_checkout_commit(project, commit_id, target_directory):
    repo_url = project["ssh_url_to_repo"]
    project_name = f"group{project['name'].split(' ')[1]}"
    project_directory = os.path.join(target_directory, project_name)

    print(f"Cloning project {project_name}...")
    subprocess.run(["git", "clone", repo_url, project_directory], check=True)

    print(f"Checking out commit {commit_id}...")
    subprocess.run(["git", "checkout", commit_id], cwd=project_directory, check=True)

    configs_directory = os.path.join(project_directory, "configs")

    default_directory = os.path.join(configs_directory, "CAIR")

    if os.path.exists(configs_directory) and os.path.exists(default_directory):
        print(
            f"Default folder found, moving subfolders from configs/ to project path..."
        )
        for item in os.listdir(configs_directory):
            item_path = os.path.join(configs_directory, item)
            if os.path.isdir(item_path):
                shutil.move(item_path, project_directory)

    else:
        print("configs/ folder not found. Skipping move and removal.")
    print()


def main():
    asn_path = "asn_all.txt"
    with open(asn_path, "r") as f:
        project_names = [f"Group {asn}" for asn in f.read().split()]
    projects = get_projects(GROUP_ID)
    time_t = TIME_T
    target_directory = "gitlab_configs"

    for project in projects:
        # print(project['name'])
        if project["name"] not in project_names:
            continue
        print(f"Processing project {project['name']}...")

        # commits = get_commits_before_time_t(project["id"], time_t)
        last_commit = get_last_commit(project["id"])
        # closest_commit = find_closest_commit(commits, time_t)
        # compare with time_t
        commit_time = datetime.datetime.fromisoformat(
            last_commit["committed_date"].rstrip("Z")
        ).replace(tzinfo=pytz.UTC)
        time_t_datetime = datetime.datetime.fromisoformat(TIME_T.rstrip("Z")).replace(
            tzinfo=pytz.UTC
        )
        if commit_time > time_t_datetime:
            print(f"Commit time {commit_time} is after time T {time_t_datetime}")

        if last_commit:
            # print(f"Closest commit for project {project['name']} before time T is:")
            print(f"Latest commit for project {project['name']} is:")
            print(f"Commit ID: {last_commit['id']}")
            print(f"Commit message: {last_commit['message']}")
            print(f"Commit time: {last_commit['committed_date']}")

            clone_and_checkout_commit(project, last_commit["id"], target_directory)
        else:
            print(f"No commits found for project {project['name']} before time T.")

        print()

    # parse gitlab_configs
    parse_script = os.path.join(os.getcwd(), "parse_gitlab_config.sh")
    subprocess.check_call(["bash", parse_script])


if __name__ == "__main__":
    main()
