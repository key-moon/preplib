#!/bin/python
from argparse import ArgumentParser
import os
from subprocess import check_output
import sys
from pathlib import Path

def main():
  parser = ArgumentParser()
  parser.add_argument("--output", "-o", help="output directory")
  parser.add_argument("--binary", "-b", help="extract all of dependencies of binary")
  parser.add_argument("--libs", "-l", nargs="*", help="extract all of dependencies of binary")
  parser.add_argument("image", help="image")

  args = parser.parse_args()

  outdir = args.output if args.output is not None else "./lib"

  if args.binary is not None and args.libs is not None:
    print("[!] can't specify --binary and --libs at once", file=sys.stderr)
    exit(1)

  lib_paths = []
  if args.libs is not None:
    output = check_output(["docker", "run", args.image, "ldconfig", "-p"]).decode()
    for line in output.splitlines():
      if " => " not in line: continue
      lib, path = line.split(" => ", 1)
      lib = lib.strip().split()[0]
      if lib not in args.libs: continue
      lib_paths.append(path.strip().split(" (")[0])
  else:
    command = ["docker", "run"]
    
    ldd_path = Path(__file__).parent.parent / "ldd.sh"
    command += ["-v", f'{ldd_path}:/ldd']

    bin_name = None
    if args.binary is not None:
      target_path = Path(args.binary).absolute()
      command += ["-v", f'{target_path}:/target']
      bin_name = "/target"
    else:
      bin_name = "/bin/cat"

    command += [args.image, "/ldd", bin_name]

    output = check_output(command).decode()
    for line in output.splitlines():
      if " => " not in line:
        if "ld" in line:
          lib_paths.append(line.strip().split(" (")[0])
        continue
      # TODO: handle unknown
      lib_paths.append(line.split(" => ", 1)[1].strip().split(" (")[0])

  if len(lib_paths) == 0:
    print("[!] library not found")
    exit(0)

  print("[+] spawning container...")
  container_id = check_output(["docker", "run", "-d", args.image, "sleep", "1000"]).strip().decode()
  print(f"[+] spawned. {container_id=}")

  Path(outdir).mkdir(exist_ok=True)
  for lib_path in lib_paths:
    check_output(["docker", "cp", "-L", f"{container_id}:{lib_path}", outdir]).strip().decode()

if __name__ == "__main__":
  main()
