"""Direct husk launcher for pre-generated USD files.

Most RenderHive Solaris jobs execute the USD Render ROP through hython so the
HIP file can generate its intermediate USD first. This module is retained for
jobs that submit an already-generated USD file.
"""

from __future__ import absolute_import, print_function

import argparse
import os
import subprocess
import sys


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Render a USD file with husk.")
    parser.add_argument("--husk", default="husk")
    parser.add_argument("--usd", required=True)
    parser.add_argument("--frame", required=True, type=float)
    parser.add_argument("--renderer", default="")
    parser.add_argument("--output", default="")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    usd = os.path.abspath(os.path.expandvars(args.usd))
    if not os.path.isfile(usd):
        print("USD file does not exist: {}".format(usd), file=sys.stderr)
        return 2
    command = [args.husk, usd, "--frame", str(args.frame), "--headless"]
    if args.renderer:
        command.extend(["--renderer", args.renderer])
    if args.output:
        command.extend(["--output", args.output])
    print("RENDERHIVE_FRAME_START {}".format(args.frame), flush=True)
    result = subprocess.call(command)
    if result == 0:
        print("RENDERHIVE_FRAME_DONE {}".format(args.frame), flush=True)
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
