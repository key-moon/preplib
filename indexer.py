
from functools import cache
from pathlib import Path
import re
import subprocess
import logging
import requests

from extractlib.logger import logger
from extractlib.index import ImageIndex, index_image
from extractlib.utils import get_image_digest

logger.setLevel(logging.INFO)

INDEX_DIR = Path("./preplib-data")
assert INDEX_DIR.is_dir(), f"index directory not found: {INDEX_DIR}"

IMAGE_INDEX_PATH = INDEX_DIR / "image_index.json"

@cache
def get_name_mapping(product: str):
  series = requests.get(f"https://endoflife.date/api/{product}.json").json()
  res = {}
  for val in series:
    res[val["codename"].split()[0].lower()] = val["cycle"]
  return res

def is_date_pinned_tag_name(tag_name: str):
  return re.match(r"\w+-\d+", tag_name)

image_index = ImageIndex(INDEX_DIR)
indexed_tags = set()
for tags in image_index.load().values():
  indexed_tags.update(filter(is_date_pinned_tag_name, tags))

# TODO: index arm image
ARCH = "amd64"
# TODO: index debian and alpine
for repository in ["amd64/ubuntu", "library/ubuntu"]:
  print("[+] getting the mapping...")
  product = repository.split("/")[1]
  name_to_version: dict[str, str] = get_name_mapping(product)

  nxt = f"https://hub.docker.com/v2/repositories/{repository}/tags?ordering=last_updated&page=1&page_size=100"
  while nxt:
    logger.info(f'fetching {nxt}...')
    # not using params={...} here because result.next already contains all query parameters
    result = requests.get(nxt).json()
    nxt = result["next"]
    for tag_info in result["results"]:
      tag_name = tag_info["name"]
      if not is_date_pinned_tag_name(tag_name):
        continue
      # prevent from pulling v1 image
      if "media_type" in tag_info and tag_info["media_type"] == "application/vnd.docker.distribution.manifest.v1+prettyjws":
        logger.info(f'skip v1 image {tag_name}')
        continue

      # parse [name]-[date] style tag like jammy-20250530
      # TODO: handle -slim image for debian
      version_name, image_date = tag_name.split('-')

      if "digest" in tag_info:
        digest = tag_info["digest"]
      else:
        # the old single-arch tag info does not have the digest for the tag....
        if len(tag_info["images"]) == 1 and tag_info["images"][0]["architecture"] == ARCH:
          digest = tag_info["images"][0]["digest"]
        else:
          digest = None

      # check to avoid indexing the multi-arch image
      is_single_arch = any([image_info["digest"] == digest and image_info["architecture"] == ARCH for image_info in tag_info["images"]])
      if not is_single_arch:
        continue

      if tag_name in indexed_tags:
        continue

      is_singlearch_repository = not repository.startswith("library")
      # For the index, use product instead of arch/product for the sake of the disambiguation.
      # product@digest exist if arch/product@digest exist, but opposite doesn't hold. so we prefer product@digest.
      if is_singlearch_repository:
        # for singlearch repository, use the digest to avoid pulling the multiarch image
        image_name = f"{product}@{digest}"
      else:
        # We are going to pull image using tag_name from product repository, not using the digest.
        # Because sometimes we could not pull the image from the digest that given by the Docker Hub. 
        # For example, digest given by the Docker Hub for the image yakkety-20170704 is `sha256:7d3f705d...`,
        # but `docker pull ubuntu@sha256:7d3f705d...` does not works for some reason.
        # Instead of, we need to use another digest, which is `sha256:8dc96528...`.
        image_name = f"{product}:{tag_name}"
      logger.info(f'indexing {tag_name}...')
      subprocess.check_call(["docker", "pull", image_name])
      index_image(image_name, INDEX_DIR)
      
      # add 
      digest = get_image_digest(image_name)
      image_name = f"{product}@{digest}"
      image_index.add(image_name, version_name)
      if version_name in name_to_version:
        image_index.add(image_name, name_to_version[version_name])
      
      subprocess.check_call(["docker", "image", "rm", image_name])
      logger.debug(f'removed image: {image_name=}')
