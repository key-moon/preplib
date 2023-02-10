#!/bin/python
from argparse import ArgumentParser
from subprocess import check_call, check_output
from pathlib import Path

def main():
  parser = ArgumentParser()
  parser.add_argument("--output", "-o", help="output directory")
  # TODO: parser.add_argument("--image", "-i", help="image")
  parser.add_argument("--relative", action="store_true", help="force libpath to relative")
  parser.add_argument("--lib", "-l", default="./lib", help="path to libs")
  parser.add_argument("--ld", help="path to ld(default: [lib]/ld...)")
  parser.add_argument("--no-ld", dest="no_ld", action="store_true", help="Do not patch ld")
  parser.add_argument("--force", "-f", action="store_true", help="Patch the binary even if the binary already patched.")

  parser.add_argument("binary", help="binary to patch")
  args = parser.parse_args()

  rpath = check_output(["patchelf", "--print-rpath", args.binary]).strip().decode()
  if not args.force:
    # TODO: check ld
    if 1 <= len(rpath):
      print(f"[!] the binary already patched. ({rpath=})")
      print(f"    if you still want to patch this binary, put --force option")
      exit(1)

  patchelf_args = ["patchelf"]
  if args.output:
    patchelf_args += ["--output", args.output]

  libpath = Path(args.lib)
  if not args.relative:
    libpath = libpath.absolute()
  patchelf_args += ["--set-rpath", f'{libpath}:{rpath}']

  if not args.no_ld:
    if args.ld is not None:
      ldpath = Path(args.ld)
    else:
      ld_candidates = []
      for path in libpath.iterdir():
        if not path.is_file(): continue
        if path.name.startswith("ld"):
          ld_candidates.append(path)
      if len(ld_candidates) == 0:
        print("[!] ld does not exists")
      if 2 <= len(ld_candidates):
        print("[!] multiple ld candidates found. specify ld with --ld option.\n    founds:")
        for ld in ld_candidates:
          print("      " + str(ld))
      ldpath = Path(ld_candidates[0])
    patchelf_args += ["--set-interpreter", ldpath]

  patchelf_args += [args.binary]
  print("$", *patchelf_args)
  check_call(patchelf_args)

if __name__ == "__main__":
  main()
