#!/usr/bin/env python3

"""Provide functions for communicating with containers."""

import subprocess

import docker

# need to change docker permission to $user
client = docker.from_env()


# def read_ctn_file(ctn_name, file_path):
#     """Return the container file in string."""
#     ctn_obj = client.containers.get(ctn_name)
#     stream, _ = ctn_obj.get_archive(file_path)
#     file_obj = BytesIO()
#     for i in stream:
#         file_obj.write(i)
#     file_obj.seek(0)
#     tar = tarfile.open(mode="r", fileobj=file_obj)
#     text = tar.extractfile(os.path.basename(file_path))
#     return text.read()


def exec_ctn(ctn_name, cmds, shell="bash"):
    """
    Execute cmd in the container.

    Each single command is a string in the cmds list,
    the function returns the command output.
    """
    ctn_obj = client.containers.get(ctn_name)
    cmd_args = [shell]
    for cmd in cmds:
        cmd_args.extend(["-c", cmd])
    result = ctn_obj.exec_run(cmd_args)
    return result.output.decode("utf-8")


def remove_ctn(ctn_name):
    """Remove a container and its volumes."""
    # TODO don't throw error when the container is not running
    ctn_obj = client.containers.get(ctn_name)
    ctn_obj.remove(v=True, force=True)


def get_ctn_name_lst(pat):
    """Return all running ctn names based on pattern."""
    cmd = f"docker ps -a --filter 'name={pat}'" + " --format '{{.Names}}'"
    ctn_list = subprocess.check_output(cmd, shell=True, text=True).strip().split()
    return ctn_list


def copy_ctn_file(ctn_name, ctn_path, local_path):
    """Copy a container file at the given path to the local path."""
    cmd = ["docker", "cp", "-q", f"{ctn_name}:{ctn_path}", local_path]
    subprocess.run(cmd, check=True)


def copy_local_file(ctn_name, local_path, ctn_path):
    """Copy a local file to the container."""
    cmd = ["docker", "cp", "-q", local_path, f"{ctn_name}:{ctn_path}"]
    subprocess.run(cmd, check=True)
