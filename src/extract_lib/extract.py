
from os import PathLike
from pathlib import Path
from typing import Optional, Union

from extract_lib.utils import MountOption, get_script_path, run_docker

def list_musl_libraries(image_name: str):
  lib_paths: list[str] = []
  for path in ["/lib", "/usr/lib"]:
    output = run_docker(image_name, "ls", "-la", path).decode()
    for line in output.splitlines():
      # extract like like -rwxr-xr-x
      if not line.startswith("-r"): continue
      # ignore the case that name has space
      name = line.split()[-1]
      if ".so" in name:
        lib_paths.append(f"{path}/{name}")
  return lib_paths

def list_libraries(image_name: str):
  try:
    output = run_docker(image_name, "sh", "-c", "ldconfig; ldconfig -p").decode()
  except:
    return list_musl_libraries(image_name)

  lib_paths: list[str] = []
  for line in output.splitlines():
    if " => " not in line: continue
    lib, path = line.split(" => ", 1)
    lib = lib.strip().split()[0] # TODO: アーキテクチャをどうにかする
    lib_paths.append(path.strip().split()[0])
  return lib_paths

def find_libraries(image_name: str, binary_path: Optional[Union[PathLike, str]]):
  mounts = []
  bin_name = None
  if binary_path is not None:
    target_path = Path(binary_path).absolute()
    bin_name = "/target"
    mounts.append(MountOption(target_path, bin_name))
  else:
    bin_name = "/bin/cat"

  output = run_docker(
    image_name,
    get_script_path("ldd"),
    bin_name,
    mounts=mounts,
    mount_scripts=True
  ).decode()

  lib_paths: list[str] = []
  for line in output.splitlines():
    if " => " not in line:
      if "ld" in line:
        lib_paths.append(line.strip().split(" (")[0])
      continue
    # TODO: handle unknown
    lib_paths.append(line.split(" => ", 1)[1].strip().split(" (")[0])
  return lib_paths

