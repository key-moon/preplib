
import json
from pathlib import Path
import re
import subprocess
import logging
import requests

from extractlib.logger import logger
from extractlib.index import ImageIndex, LibIndex, index_image

logger.setLevel(logging.INFO)

INDEX_DIR = Path("./preplib-data")
assert INDEX_DIR.is_dir(), f"index directory not found: {INDEX_DIR}"

IMAGE_INDEX_PATH = INDEX_DIR / "image_index.json"

def get_name_mapping(product: str):
  series = requests.get(f"https://endoflife.date/api/{product}.json").json()
  res = {}
  for val in series:
    res[val["codename"].split()[0].lower()] = val["cycle"]
  return res

print("[+] getting ubuntu series...")
name_to_version: dict[str, str] = get_name_mapping("ubuntu")
print("[+] getting debian series...")
debian_name_to_version: dict[str, str] = get_name_mapping("debian")

image_index = ImageIndex(INDEX_DIR)

# ubuntu
page = 1
for product in ["ubuntu", "debian"]:
  print("[+] getting mappings...")
  name_to_version: dict[str, str] = get_name_mapping("ubuntu")

  nxt = f"https://hub.docker.com/v2/repositories/amd64/{product}/tags"
  while nxt:
    logger.info(f'fetching {nxt}...')
    result = requests.get(
      nxt,
      params={
        "page_size": 100,
        "page": page,
        "ordering": "last_updated"
      }
    ).json()
    nxt = result["next"]
    has_new_tags = True
    for tag_info in result["results"]:
      tag_name = tag_info["name"]
      if not re.match(r"\w+-\d+", tag_name):
        continue
      version_name, image_date = tag_name.split('-')
      digest = [info["digest"] for info in tag_info["images"] if info["architecture"] == "amd64"][0]
      image_name = f"{product}@{digest}"
      if image_index.get(image_name):
        continue

      has_new_tags = True

      image_index.add(image_name, tag_name)
      image_index.add(image_name, version_name)
      if version_name in name_to_version:
        image_index.add(image_name, name_to_version[version_name])
      logger.info(f'indexing {tag_name}...')
      index_image(image_name, INDEX_DIR)
      logger.debug(f'removed: {image_name=}')
      subprocess.check_call(["docker", "image", "rm", image_name])
    if not has_new_tags:
      break
