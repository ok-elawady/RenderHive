"""Delegate to the package root installer."""
from __future__ import print_function
import os
import runpy

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
runpy.run_path(os.path.join(ROOT, "install.py"), run_name="__main__")
