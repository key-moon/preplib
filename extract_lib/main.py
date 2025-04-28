#!/bin/python
from argparse import ArgumentParser
import hashlib
from hmac import digest
import logging
import os
from subprocess import check_output
import sys
from pathlib import Path
from typing import Optional

from extract_lib.index import LibInfo, find_image, get_image_index, index_image, default_cache_dir

from extract_lib.logger import logger
from extract_lib.extract import find_libraries, list_libraries
from extract_lib.utils import MountOption, get_script_path, parse_image_name, run_docker, is_digest_like

# TODO: extract .debug into the same directory
def main():
  parser = ArgumentParser()
  parser.add_argument("--output", "-o", help="output directory", default="./lib")
  parser.add_argument("--binary", "-b", help="extract all of dependencies of binary")
  parser.add_argument("--libs", "-l", nargs="*", help="specify library names to extract")
  parser.add_argument("--index", action="store_true", help="index libraries in the specified image and exit")
  parser.add_argument("--index-dir", nargs="?", help="index directory (default: user-cache-dir)", default=str(default_cache_dir))
  parser.add_argument("--verbose", "-v", action="store_true", help="enable verbose output")
  parser.add_argument("--vverbose", "-vv", action="store_true", help="enable debug output")
  parser.add_argument("--quiet", "-q", action="store_true", help="enable quiet output")
  parser.add_argument("image_or_libpaths", nargs="+", help="image")

  args = parser.parse_args()
  if args.vverbose:
    logger.setLevel(logging.DEBUG)
  elif args.verbose:
    logger.setLevel(logging.INFO)
  elif args.quiet:
    logger.setLevel(logging.ERROR)
  else:
    logger.setLevel(logging.WARN)

  if args.index:
    index_image(args.image_or_libpaths[0], args.index_dir)
    exit(0)

  outdir = args.output

  lib_paths = []

  if len(args.image_or_libpaths) != 1 or os.path.exists(args.image_or_libpaths[0]) or is_digest_like(args.image_or_libpaths[0]):
    logger.info(f"searching images from indexed libraries...")
    candidate_images: Optional[dict[str, dict[str, str]]] = None
    for val in args.image_or_libpaths:
      val = str(val)
      digests = []
      if os.path.exists(val):
        digests.append(hashlib.md5(open(val, "rb").read()).hexdigest())
        try:
          flag = False
          for line in check_output(["readelf", "-n", val]).decode().splitlines():
            if flag:
              print(line.split(": ")[-1])
              digests.append(line.split(": ")[-1].strip())
              break
            else:
              flag = "NT_GNU_BUILD_ID" in line
        except:
          pass
      if is_digest_like(val):
        digests.append(val)

      logger.debug(f"{digests=}")
      for digest in digests:
        images = find_image(digest, index_dir=args.index_dir)
        logger.debug(f"{digest} -> {images}")
        if candidate_images is None:
          candidate_images = {}
          for image in images:
            candidate_images[image.image_identifier] = { val: image.path }
        else:
          for image in images:
            if image.image_identifier not in candidate_images:
              continue
            candidate_images[image.image_identifier][val] = image.path
    assert candidate_images is not None
    lib_count = len(args.image_or_libpaths)
    candidates: list[tuple[str, dict[str, str]]] = []
    for image_identifier, candidatess in candidate_images.items():
      if len(candidatess) == lib_count:
        candidates.append((image_identifier, candidatess))

    image_index = get_image_index(args.index_dir)
    def show_image(image_identifier: str, file_paths: dict[str, str], level=logging.INFO):
      repository, _, digest = parse_image_name(image_identifier)
      tags = [f"\"{tag}\"" for tag in image_index.get(image_identifier)]
      tags_str = ", ".join(tags) if len(tags) <= 3 else ", ".join(tags[:3]) + "..."

      logger.log(level, f"found in image \"{repository}\" once tagged as {tags_str} (image digest: {digest})")
      for val, path in file_paths.items():
        logger.log(level, f"- {val} => {path}")

    if len(candidates) == 0:
      logger.warning(f"no candidates found")
    elif len(candidates) == 1:
      show_image(*candidates[0])
    else:
      logger.warning(f"multiple images contains the same libraries:")
      for candidate in candidates:
        show_image(*candidate, level=logging.WARNING)
      logger.warning(f"for a now, use last(=usually latest) one")

    image = candidates[-1][0]
      
      


  else:
    logger.debug(f"use {args.image} as a image name")
    image = args.image

  if args.libs is not None:
    def checker(name: str):
      for lib in args.libs:
        if name.startswith(lib):
          return True
    lib_paths += list(filter(checker, list_libraries(image)))
  if args.binary is not None:
    lib_paths = find_libraries(image, args.binary)

  if args.binary is None and args.libs is None:
    lib_paths = find_libraries(image, "/bin/cat")

  if len(lib_paths) == 0:
    logger.error("library not found")
    exit(1)

  lib_paths = list(set(lib_paths))

  logger.info("spawning container...")
  container_id = check_output(["docker", "run", "--rm", "-d", image, "sleep", "1000"]).strip().decode()
  logger.info(f"spawned. {container_id=}")

  Path(outdir).mkdir(exist_ok=True)
  for lib_path in lib_paths:
    logger.debug(f"cp {container_id}:{lib_path} -> {outdir}")
    check_output(["docker", "cp", "-L", f"{container_id}:{lib_path}", outdir]).strip().decode()

if __name__ == "__main__":
  main()
