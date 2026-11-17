"""Create a separate, empty experiment without deleting published evaluation records."""

import argparse
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def create_workspace(destination, source=ROOT):
    """Copy only implementation/configuration and the frozen scientific protocol."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    # Keep new experiments together and out of the publication candidate.
    parent = source / ".reproductions"
    if destination.parent != parent or destination == source:
        raise ValueError("Choose a new direct child of .reproductions/, e.g. .reproductions/run-01.")
    destination.mkdir(parents=True, exist_ok=False)
    for directory in ("scripts", "api", "dashboard", "tests", ".streamlit"):
        shutil.copytree(source / directory, destination / directory,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "secrets.toml"))
    # Reference-only manifest for the downloader's offline tests; never copy binaries.
    if (source / "artifacts/manifest.json").is_file():
        (destination / "artifacts").mkdir()
        shutil.copy2(source / "artifacts/manifest.json", destination / "artifacts/manifest.json")
    for path in source.glob("requirements*.txt"):
        shutil.copy2(path, destination / path.name)
    for name in (".python-version", ".gitignore"):
        shutil.copy2(source / name, destination / name)
    (destination / "reports").mkdir()
    shutil.copy2(source / "reports/phase3_protocol.md", destination / "reports/phase3_protocol.md")
    (destination / "data/raw").mkdir(parents=True)
    shutil.copy2(source / "data/SOURCES.md", destination / "data/SOURCES.md")
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="New directory such as .reproductions/run-01")
    args = parser.parse_args()
    try:
        destination = create_workspace(args.destination)
    except (OSError, ValueError) as error:
        parser.exit(1, f"Cannot prepare reproduction: {error}\n")
    print(f"Workspace created: {destination}")
    print("No data downloaded, no model trained and no evaluation performed.")
    print("Follow the reproduction commands in the repository README from this workspace.")


if __name__ == "__main__":
    main()
