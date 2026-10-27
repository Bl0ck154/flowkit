import json
import stat
import sys
from pathlib import Path

from scripts import install_extension_policy as policy
from scripts import package_extension as package

EXPECTED_EXTENSION_ID = "omninmfjkhecnelaeokchhmfflakpdae"


def test_manifest_key_preserves_extension_identity():
    manifest = json.loads(
        (Path(__file__).parents[2] / "extension" / "manifest.json").read_text(encoding="utf-8")
    )
    assert package.extension_id_from_manifest_key(manifest["key"]) == EXPECTED_EXTENSION_ID


def test_policy_writer_is_readable_by_unprivileged_chrome(tmp_path, monkeypatch):
    release = tmp_path / "release.json"
    target = tmp_path / "managed" / "flowkit.json"
    release.write_text(
        json.dumps({"extension_id": EXPECTED_EXTENSION_ID, "version": "0.3.1"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "install_extension_policy.py",
            "--release-json",
            str(release),
            "--policy-file",
            str(target),
            "--update-url",
            "http://127.0.0.1:8110/updates.xml",
        ],
    )

    assert policy.main() == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data == {
        "ExtensionInstallForcelist": [
            f"{EXPECTED_EXTENSION_ID};http://127.0.0.1:8110/updates.xml"
        ]
    }
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
