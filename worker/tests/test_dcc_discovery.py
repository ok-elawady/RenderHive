import os
import tempfile
import unittest
from pathlib import Path

from core.dcc_discovery import (
    discover_houdini_installations,
    discover_maya_installations,
    select_installation,
)


class DCCDiscoveryTests(unittest.TestCase):
    def test_discovers_multiple_versions_and_selects_compatible_build(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            maya_2023 = root / "Maya2023"
            maya_2025 = root / "Maya2025"
            houdini_205 = root / "Houdini 20.5.278"
            houdini_210 = root / "Houdini 21.0.440"

            for folder, files in (
                (maya_2023 / "bin", ["Render.exe", "mayapy.exe"]),
                (maya_2025 / "bin", ["Render.exe", "mayapy.exe"]),
                (houdini_205 / "bin", ["hython.exe", "husk.exe"]),
                (houdini_210 / "bin", ["hython.exe", "husk.exe"]),
            ):
                folder.mkdir(parents=True)
                for name in files:
                    (folder / name).write_text("", encoding="utf-8")

            maya = discover_maya_installations([str(maya_2023), str(maya_2025)])
            houdini = discover_houdini_installations([str(houdini_205), str(houdini_210)])

            self.assertEqual([item.version for item in maya], ["2025", "2023"])
            self.assertEqual([item.version for item in houdini], ["21.0.440", "20.5.278"])
            self.assertEqual(select_installation(maya, "2023.2").version, "2023")
            self.assertEqual(select_installation(houdini, "20.5.999").version, "20.5.278")
            self.assertIsNone(select_installation(houdini, "19.5"))

    def test_duplicate_maya_version_is_collapsed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auto_root = root / "Auto" / "Maya2023"
            explicit_root = root / "Explicit" / "Maya2023"

            for folder, files in (
                (auto_root / "bin", ["Render.exe"]),
                (explicit_root / "bin", ["Render.exe", "mayapy.exe"]),
            ):
                folder.mkdir(parents=True)
                for name in files:
                    (folder / name).write_text("", encoding="utf-8")

            maya = discover_maya_installations([str(auto_root), str(explicit_root)])

            self.assertEqual([item.version for item in maya], ["2023"])
            self.assertEqual(Path(maya[0].root), explicit_root)
            self.assertTrue(maya[0].executables["mayapy"])

    def test_duplicate_houdini_build_is_collapsed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_root = root / "A" / "Houdini 20.5.278"
            second_root = root / "B" / "Houdini 20.5.278"

            for folder in (first_root / "bin", second_root / "bin"):
                folder.mkdir(parents=True)
                (folder / "hython.exe").write_text("", encoding="utf-8")

            houdini = discover_houdini_installations([str(first_root), str(second_root)])

            matching = [item for item in houdini if item.version == "20.5.278"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(Path(matching[0].root), second_root)

    def test_explicit_maya_root_overrides_richer_program_files_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            program_files = root / "ProgramFiles"
            auto_root = program_files / "Autodesk" / "Maya2023"
            explicit_root = root / "Manual" / "Maya2023"

            (auto_root / "bin").mkdir(parents=True)
            for name in ("Render.exe", "mayapy.exe", "maya.exe"):
                (auto_root / "bin" / name).write_text("", encoding="utf-8")
            (explicit_root / "bin").mkdir(parents=True)
            (explicit_root / "bin" / "Render.exe").write_text("", encoding="utf-8")

            old_program_files = os.environ.get("ProgramFiles")
            old_program_files_x86 = os.environ.get("ProgramFiles(x86)")
            try:
                os.environ["ProgramFiles"] = str(program_files)
                os.environ["ProgramFiles(x86)"] = str(root / "NoX86")
                maya = discover_maya_installations([str(explicit_root)])
            finally:
                if old_program_files is None:
                    os.environ.pop("ProgramFiles", None)
                else:
                    os.environ["ProgramFiles"] = old_program_files
                if old_program_files_x86 is None:
                    os.environ.pop("ProgramFiles(x86)", None)
                else:
                    os.environ["ProgramFiles(x86)"] = old_program_files_x86

            selected = next(item for item in maya if item.version == "2023")
            self.assertEqual(Path(selected.root), explicit_root)

    def test_explicit_houdini_root_overrides_richer_program_files_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            program_files = root / "ProgramFiles"
            auto_root = program_files / "Side Effects Software" / "Houdini 20.5.278"
            explicit_root = root / "Manual" / "Houdini 20.5.278"

            (auto_root / "bin").mkdir(parents=True)
            for name in ("hython.exe", "husk.exe", "hbatch.exe", "houdini.exe"):
                (auto_root / "bin" / name).write_text("", encoding="utf-8")
            (explicit_root / "bin").mkdir(parents=True)
            (explicit_root / "bin" / "hython.exe").write_text("", encoding="utf-8")

            old_program_files = os.environ.get("ProgramFiles")
            old_program_files_x86 = os.environ.get("ProgramFiles(x86)")
            try:
                os.environ["ProgramFiles"] = str(program_files)
                os.environ["ProgramFiles(x86)"] = str(root / "NoX86")
                houdini = discover_houdini_installations([str(explicit_root)])
            finally:
                if old_program_files is None:
                    os.environ.pop("ProgramFiles", None)
                else:
                    os.environ["ProgramFiles"] = old_program_files
                if old_program_files_x86 is None:
                    os.environ.pop("ProgramFiles(x86)", None)
                else:
                    os.environ["ProgramFiles(x86)"] = old_program_files_x86

            selected = next(item for item in houdini if item.version == "20.5.278")
            self.assertEqual(Path(selected.root), explicit_root)


if __name__ == "__main__":
    unittest.main()
