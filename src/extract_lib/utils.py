from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from subprocess import check_output
from typing import Union

@dataclass
class MountOption:
  source: Union[str, PathLike]
  dest: Union[str, PathLike]
  allow_write: bool=False

source_scripts_path = Path(__file__).parent / "scripts"
dest_scripts_path = Path("/extractlib_scripts")

def get_script_path(script_name):
  return str(dest_scripts_path / script_name)

def run_docker(image_name: str, *commands: str, extra_args=[], mounts: list[MountOption]=[], mount_scripts=False):
  run_command = ["docker", "run", *extra_args, "--rm"]
  if mount_scripts:
    mounts = mounts + [MountOption(source_scripts_path, dest_scripts_path)]
  print(mount_scripts, mounts)
  for mount in mounts:
    assert ":" not in f"{mount.source}" and ":" not in f"{mount.dest}"
    if mount.allow_write:
      run_command += ["-v", f"{mount.source}:{mount.dest}"]
    else:
      run_command += ["-v", f"{mount.source}:{mount.dest}:ro"]
  run_command += [image_name]
  run_command += commands
  
  return check_output(run_command)

def get_image_digest(image_name: str):
  return check_output(["docker", "inspect", "--format={{index .RepoDigests 0}}", image_name]).decode().strip()

def parse_image_name(image_name: str):
  last_part = image_name.split("/")[-1]
  if "@" in last_part:
    repository_and_tag, image_digest = image_name.rsplit("@", maxsplit=1)
  else:
    repository_and_tag = image_name
    image_digest = get_image_digest(image_name)
  if ":" in repository_and_tag.split("/")[-1]:
    repository_name, image_tag = repository_and_tag.split(":", maxsplit=1)
  else:
    repository_name = repository_and_tag
    image_tag = None
  return repository_name, image_tag, image_digest

def is_digest_like(s: str):
  if not all(c in "0123456789abcdef" for c in s):
    return False
  return len(s) in [32, 40, 64, 128]
