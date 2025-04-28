from ast import literal_eval
from collections import namedtuple
from dataclasses import dataclass
import json
from os import PathLike
from pathlib import Path
from subprocess import check_output
from typing import NamedTuple, Optional, Union
import appdirs

from extract_lib.utils import get_image_digest, get_script_path, parse_image_name, run_docker, dest_scripts_path
from extract_lib.logger import logger

class LibInfo(NamedTuple):
  image_name: str
  image_digest: str
  path: str
  @property
  def image_identifier(self):
    return f"{self.image_name}@{self.image_digest}"

class LibDigest(NamedTuple):
  path: str
  digest: str

def hash_parser(output: str):
  res: list[LibDigest] = []
  for l in output.strip().splitlines():
    s = l.strip().split()
    if len(s) < 2:
      continue
    res.append(LibDigest(s[1], s[0]))
  return res

index_commands = {
  "build-id": ([get_script_path("build-id")], hash_parser, True),
  "md5": (["md5sum"], hash_parser, False),
  "sha1": (["sha1sum"], hash_parser, False),
  "sha256": (["sha256sum"], hash_parser, False),
  "sha512": (["sha512sum"], hash_parser, False),
}

default_cache_dir = Path(appdirs.user_cache_dir("extract-lib"))

# each line should be: <image@image-digest> <path>

class LibIndex:
  def __init__(self, cache_dir: Union[PathLike, str]):
    self.cache_dir = Path(cache_dir)

  def _get_cache_path(self, digest: str):
    return self.cache_dir / "cache" / digest

  def load(self, digest: str) -> list[LibInfo]:
    cache_path = self._get_cache_path(digest)
    if not cache_path.exists(): return []
    res = []
    for l in cache_path.read_text().splitlines():
      splitted = l.strip().split(" ", maxsplit=1)
      if len(splitted) < 2: continue # TODO: report error?
      image, path = splitted[0], splitted[1]
      splitted = image.split("@", maxsplit=1)
      if len(splitted) < 2: continue # TODO: report error?
      name, digest = splitted[0], splitted[1]
      res.append(LibInfo(name, digest, str(literal_eval(path))))
    return res

  def dump(self, digest: str, info: list[LibInfo]):
    cache_path = self._get_cache_path(digest)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("\n".join([f"{i.image_name}@{i.image_digest} {repr(i.path)}" for i in info]))

  def add(self, digest: str, new_info: LibInfo):
    caches = self.load(digest)
    if any(cache == new_info for cache in caches):
      return
    caches.append(new_info)
    self.dump(digest, caches)

class ImageIndex:
  def __init__(self, cache_dir: Union[PathLike, str]):
    self.cache_dir = Path(cache_dir)

  def _get_cache_path(self):
    return self.cache_dir / "image_index.json"

  def load(self) -> dict[str, list[str]]:
    cache_path = self._get_cache_path()
    if not cache_path.exists(): return {}
    try:
      return json.loads(cache_path.read_text())
    except:
      # TODO: report error
      cache_path.rename(self._get_cache_path() / ".corrupt")
      return {}

  def dump(self, cache: dict[str, list[str]]):
    cache_path = self._get_cache_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache))

  def get(self, image_name: str):
    return self.load().get(image_name, [])

  def add(self, image_name: str, new_tag: str):
    caches = self.load()
    if image_name not in caches or not isinstance(caches[image_name], list):
      caches[image_name] = []
    caches[image_name].append(new_tag)
    self.dump(caches)


def index_image(image_name: str, index_dir: Union[PathLike, str]=default_cache_dir, index_types=["build-id", "md5"]):
  repository_name, image_tag, image_digest = parse_image_name(image_name)

  if image_tag is not None:
    ImageIndex(index_dir).add(f"{repository_name}@{image_digest}", image_tag)

  index = LibIndex(index_dir)

  output = run_docker(image_name, "sh", "-c", "ldconfig; ldconfig -p").decode()
  lib_paths = []
  for line in output.splitlines():
    if " => " not in line: continue
    lib, path = line.split(" => ", 1)
    lib = lib.strip().split()[0]
    lib_paths.append(path)
  
  for index_type in index_types:
    commands, parser, mount_scripts = index_commands[index_type]
    logger.debug(f"{index_type=} {commands=}")
    command_res = run_docker(image_name, *commands, *lib_paths, mount_scripts=mount_scripts)
    for path, digest in parser(command_res.decode()):
      logger.debug(f"{path=} {digest=}")
      index.add(digest, LibInfo(repository_name, image_digest, path))

def find_image(library_digest: str, index_dir: Union[PathLike, str]=default_cache_dir):
  lib_index = LibIndex(index_dir)
  return lib_index.load(library_digest)

def get_image_index(index_dir: Union[PathLike, str]=default_cache_dir):
  return ImageIndex(index_dir)
