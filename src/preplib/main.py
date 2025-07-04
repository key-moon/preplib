#!/bin/python
from argparse import ArgumentParser
import hashlib
import logging
import os
from subprocess import check_output
from pathlib import Path
from typing import Optional

from preplib.index import LibIndex, find_suitable_images, get_image_index, index_image, default_cache_dir

from preplib.logger import logger
from preplib.extract import find_libraries, list_libraries
from preplib.utils import parse_image_name, is_digest_like

# TODO: コンフィグファイルを作る / TUI でコンフィグをいじれるようにする
#       コンフィグ内容: index の位置s / デフォルトの output / index を自動で clone および pull するか / index server の URLs
#       debuginfod の URLs / 自動で 

# TODO: 複数の index を使うように（特にURL）
# TODO: debuginfod で引っ張ってきたシンボルを使ってpatch
# TODO: サーバーを使うようにする / サーバーの URL を configurable にする
# TODO: ierae CTF で壊れたやつの調査
LIBDIGESTINFO_SERVER = "https://key-moon.github.io/preplib-data"

# TODO: extract .debug into the same directory
def main():
  parser = ArgumentParser()
  parser.add_argument("--output", "-o", help="output directory", default="./lib")
  parser.add_argument("--binary", "-b", help="extract all of binary dependencies using ldd (exclusive to --libs)")
  parser.add_argument("--libs", "-l", nargs="*", help="specify library names to extract (exclusive to --binary)")
  parser.add_argument("--index", action="store_true", help="index libraries in the specified image and exit")
  parser.add_argument("--index-dir", nargs="?", help="index directory (default: user-cache-dir)", default=str(default_cache_dir))
  parser.add_argument("--verbose", "-v", action="store_true", help="enable verbose output")
  parser.add_argument("--quiet", "-q", action="store_true", help="enable quiet output")
  parser.add_argument("image_or_libinfo", nargs="+", help="image tag(ubuntu:jammy) | library path(/path/to/libc.so.6) | build-id(89c3cb85...) | md5sum")

  args = parser.parse_args()
  if args.verbose:
    logger.setLevel(logging.DEBUG)
  elif args.quiet:
    logger.setLevel(logging.WARN)
  else:
    logger.setLevel(logging.INFO)

  if args.index:
    index_image(args.image_or_libinfo[0], args.index_dir)
    exit(0)

  outdir = args.output

  lib_paths = []

  if len(args.image_or_libinfo) != 1 or os.path.exists(args.image_or_libinfo[0]) or is_digest_like(args.image_or_libinfo[0]):
    logger.info(f"searching images from indexed libraries...")
    image = None
    candidate_images: Optional[dict[str, dict[str, str]]] = None
    md5_digests = []
    buildid_digests = []
    for val in args.image_or_libinfo:
      val = str(val)
      if os.path.exists(val):
        md5_digests.append((val, hashlib.md5(open(val, "rb").read()).hexdigest()))
        try:
          flag = False
          # extract the line after the `NT_GNU_BUILD_ID`
          for line in check_output(["readelf", "-n", val]).decode().splitlines():
            if flag:
              buildid_digests.append((val, line.split(": ")[-1].strip()))
              break
            else:
              flag = "NT_GNU_BUILD_ID" in line
        except:
          pass
      elif is_digest_like(val):
        md5_digests.append((val, val))
        buildid_digests.append((val, val))
      else:
        logger.error("invalid library file or hash", val)

    lib_count = len(args.image_or_libinfo)
    index = LibIndex(cache_dir=args.index_dir) # ここで直接index触ってるのかなりキモい
    image_index = get_image_index(args.index_dir)
    def show_image(image_identifier: str, file_paths: dict[str, str], level=logging.INFO):
      repository, _, digest = parse_image_name(image_identifier)
      tags = [f"\"{tag}\"" for tag in image_index.get(image_identifier)]
      tags_str = ", ".join(tags) if len(tags) <= 3 else ", ".join(tags[:3]) + "..."

      logger.log(level, f"found in image \"{repository}\" once tagged as {tags_str} (image digest: {digest})")
      for val, path in file_paths.items():
        logger.log(level, f"- {val} => {path}")

    for digests, method in [(md5_digests, "md5"), (buildid_digests, "build_id")]:
      if lib_count != len(digests): continue
      candidate_images = find_suitable_images(digests, index)

      candidates: list[tuple[str, dict[str, str]]] = []
      for image_identifier, candidatess in candidate_images.items():
        if len(candidatess) == lib_count:
          candidates.append((image_identifier, candidatess))

      if len(candidates) == 0:
        logger.warning(f"no candidates found by {method}")
        continue
      elif len(candidates) == 1:
        show_image(*candidates[0])
        image = candidates[-1][0]
        break
      else:
        logger.warning(f"multiple images contains the same libraries:")
        for candidate in candidates:
          show_image(*candidate, level=logging.WARNING)
        logger.warning(f"for a now, use last(=usually latest) one") # TODO: affinityみたいなのを使う
        image = candidates[-1][0]
        break
    if image is None:
      logger.error(f"no candidates found")
      exit(1)
  else:
    image = args.image_or_libinfo[0]
    logger.debug(f"use {image} as a image name")

  if args.libs is not None:
    def checker(name: str):
      for lib in args.libs:
        if name.startswith(lib):
          return True
    lib_paths += list(filter(checker, list_libraries(image)))
  if args.binary is not None:
    lib_paths = find_libraries(image, args.binary)

  if args.binary is None and args.libs is None:
    lib_paths = find_libraries(image, None)

  if len(lib_paths) == 0:
    logger.error("library not found")
    exit(1)

  lib_paths = list(set(lib_paths))

  logger.info(f"spawning container for image {image}...")
  container_id = check_output(["docker", "run", "--rm", "-d", image, "sleep", "1000"]).strip().decode()
  logger.info(f"spawned. {container_id=}")

  Path(outdir).mkdir(exist_ok=True)
  for lib_path in lib_paths:
    logger.debug(f"cp {container_id}:{lib_path} -> {outdir}")
    check_output(["docker", "cp", "-L", f"{container_id}:{lib_path}", outdir]).strip().decode()

if __name__ == "__main__":
  main()
