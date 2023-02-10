from argparse import ArgumentParser
from hashlib import md5
import os
import shutil
from subprocess import call, check_call, check_output
from pathlib import Path
import sys
from typing import List, Tuple

ROOT = Path(__file__).parent / "glibc-all-in-one"
LIBS_DIR = ROOT / "libs"
INDEX_DIR = ROOT / "index"

LIST_AND_DOWNLOADERS: List[Tuple[str, str]] = [("list", "download"), ("old_list", "download_old")]

def update():
  origdir = Path(os.curdir).absolute()
  os.chdir(ROOT)
  check_call(ROOT /  "update_list")
  os.chdir(origdir)

  for list_file, downloader in LIST_AND_DOWNLOADERS:
    for name in (ROOT / list_file).read_text().splitlines():
      name = name.strip()
      if len(name) == 0: continue
      call([ROOT / downloader, name]) # w/o check since 
      libs_dir = LIBS_DIR / name

      index_file = INDEX_DIR / name
      with open(index_file, "w") as ind_f:
        for file in libs_dir.iterdir():
          if file.name == ".debug": continue
          hash = md5(file.read_bytes()).hexdigest()
          ind_f.write(f'{file.name} {hash}\n')

def find_id_from_hash(hash):
  res = []
  for index_file in INDEX_DIR.iterdir():
    cur_id = index_file.name
    for index in index_file.read_text().splitlines():
      filename, filehash = index.split()
      if hash == filehash:
        res.append((cur_id, filename))
  return res

def main():
  parser = ArgumentParser()
  parser.add_argument("--update", action="store_true", help="update index")
  parser.add_argument("--output", "-o", help="output directory")
  # parser.add_argument("--binary", "-b", help="extract all of dependencies of binary")
  parser.add_argument("--no-dereference", "-P", dest="dereference", action="store_false", help="follow the symlink")
  parser.add_argument("--id", help="library path or version")
  parser.add_argument("library", nargs="?", default=None, help="library path or id")

  args = parser.parse_args()

  Path(INDEX_DIR).mkdir(exist_ok=True)

  if args.update:
    update()
  
  out_dir = Path(args.output if args.output is not None else "./lib")
  if out_dir.exists():
    while True:
      answer = input(f"[+] {out_dir} already exists. Can I overwrite it? [y/n]\n> ")
      if answer.lower()[0] == "n":
        exit(1)
      if answer.lower()[0] == "y":
        break
  
  """
  if args.binary:
    libs = []
    ldd_path = Path(__file__).parent.parent / "ldd.sh"
    
    output = check_output([ldd_path, args.binary]).decode()
    for line in output.splitlines():
      if " => " not in line:
        if "ld" in line:
          libs.append(line.strip().split(" (")[0].split('/')[-1])
        continue
      # TODO: handle unknown
      libs.append(line.split(" => ", 1)[0].strip())
  """

  lib_id = None
  if args.id:
    lib_id = args.id
  else:
    if args.library is None:
      print("[!] must specify --id or library", file=sys.stderr)
      exit(1)
    
    if not Path(args.library).exists():
      lib_id = args.library
    else:
      lib_path = Path(args.library)
      lib_name = lib_path.name
      lib_hash = md5(lib_path.read_bytes()).hexdigest()
      hash_and_name = find_id_from_hash(lib_hash)
      matched = [*filter(lambda item: item[1] == lib_name, hash_and_name)]
      similar = [*filter(lambda item: item[1] != lib_name, hash_and_name)]

      if len(matched) == 1:
        lib_id = matched[0][0]
      elif 1 < len(matched):
        print(
          "[!] found multiple candidates. Re-run this command with the id.",
          "    id: ",
          *['      ' + match for match in matched],
          sep="      \n",
          file=sys.stderr
        )
        exit(1)
      elif 1 <= len(similar):
        print(
          "[!] found similar candidates. Re-run this command with the id.",
          "    (id, name): ",
          *['      ' + match for match in similar],
          sep="    \n",
          file=sys.stderr
        )
        exit(1)
      else:
        print("[!] Version not found")
        exit(1)

  target_dir = LIBS_DIR / lib_id
  print(f'[+] {lib_id=}')
  print(f'[+] copying...')
  shutil.copytree(target_dir, out_dir, dirs_exist_ok=True, symlinks=args.dereference)

if __name__ == "__main__":
  main()
