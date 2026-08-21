from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release_manifest.json"


def test_release_manifest_matches_production_tree():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["name"] == "RenderHive Houdini"
    assert data["version"] == "2.0.5"
    assert data["release_status"] == "production"
    assert data["api_contract"] == "0.2.0"
    assert data["api_contract_sha256"] == "b77bdeb330bb15cf73fe37f659b67187989d6134f5757cf678acd6f22723172d"
    files = data.get("files") or {}
    assert data["file_count"] == len(files)
    for relative, expected in files.items():
        path = ROOT / relative
        assert path.is_file(), relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative
