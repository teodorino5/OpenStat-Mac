"""Package a local contributor app. It intentionally does not bundle an unaudited Python runtime."""

import argparse
import json
import plistlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--configuration", default="debug", choices=["debug", "release"])
    arguments = parser.parse_args()
    binary_dir = Path(
        subprocess.check_output(
            ["swift", "build", "-c", arguments.configuration, "--show-bin-path"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    output = ROOT / "build" / "OpenStat Mac.app"
    if output.exists():
        shutil.rmtree(output)
    macos = output / "Contents/MacOS"
    resources = output / "Contents/Resources"
    macos.mkdir(parents=True)
    resources.mkdir()
    shutil.copy2(binary_dir / "OpenStatMac", macos / "OpenStatMac")
    bundle = next(binary_dir.glob("*OpenStatApp.bundle"))
    shutil.copytree(bundle, resources / bundle.name)
    config = {"python": str(ROOT / "engine/.venv/bin/python"), "source": str(ROOT / "engine/src")}
    (resources / "development-runtime.json").write_text(json.dumps(config, indent=2) + "\n")
    info = {
        "CFBundleName": "OpenStat Mac",
        "CFBundleDisplayName": "OpenStat Mac",
        "CFBundleIdentifier": "org.openstat.mac",
        "CFBundleExecutable": "OpenStatMac",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "1",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "OpenStat Project",
                "CFBundleTypeRole": "Editor",
                "LSItemContentTypes": ["org.openstat.project"],
                "LSTypeIsPackage": True,
                "NSDocumentClass": "OpenStatApp.OpenStatDocument",
            }
        ],
        "UTExportedTypeDeclarations": [
            {
                "UTTypeIdentifier": "org.openstat.project",
                "UTTypeDescription": "OpenStat Project",
                "UTTypeConformsTo": ["com.apple.package"],
                "UTTypeTagSpecification": {"public.filename-extension": ["openstat"]},
            }
        ],
    }
    (output / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    subprocess.run(["codesign", "--force", "--sign", "-", str(output)], check=True)
    subprocess.run(["codesign", "--verify", "--strict", str(output)], check=True)
    print(output)
    print("Contributor app: requires this checkout and engine/.venv. Not a standalone release.")


if __name__ == "__main__":
    main()
