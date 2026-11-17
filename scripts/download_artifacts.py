"""Plan, check or explicitly download a pinned, owner-authorized GitHub Release.

Uses only the standard library. Never imports joblib/pickle, trains, or loads a model.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "artifacts/manifest.json"
TARGETS = {
    "model": ("RandomForest.joblib", "models/phase3/RandomForest.joblib"),
    "historical": ("test_predictions.csv", "data/processed/phase3/test_predictions.csv"),
    "example": ("example_request.json", "data/processed/phase3/example_request.json"),
}
PROFILES = {"historical": ["historical"], "full": ["model", "historical", "example"]}
REPOSITORY_FILES = (
    "reports/ml/selection.json", "reports/ml/test_completion.json",
    "reports/ml/validation_metrics.csv", "reports/ml/test_metrics.csv",
    "reports/ml/validation_by_horizon.csv", "reports/ml/test_by_horizon.csv",
    "reports/ml/split_counts.csv", "requirements.txt", "reports/phase3_protocol.md",
)
DOWNLOAD_HOSTS = {"github.com", "release-assets.githubusercontent.com",
                  "objects.githubusercontent.com"}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(manifest):
    """Reject arbitrary filenames/paths, ambiguous versions and incomplete manifests."""
    if manifest["schema_version"] != 1 or manifest["profiles"] != PROFILES:
        raise ValueError("Unsupported manifest schema or profiles.")
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?", manifest["planned_release_tag"]):
        raise ValueError("Use a pinned version tag such as v1.0.0, never latest or main.")
    files = manifest["files"]
    if len(files) != len(TARGETS) or {item["id"] for item in files} != set(TARGETS):
        raise ValueError("The manifest must describe exactly the three supported assets.")
    for item in files:
        if (item["asset"], item["destination"]) != TARGETS[item["id"]]:
            raise ValueError("Unexpected asset name or destination.")
        if type(item["size_bytes"]) is not int or not 0 < item["size_bytes"] < 2**31:
            raise ValueError("Asset size must be a positive integer below 2 GiB.")
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Invalid SHA-256 digest.")
    if set(manifest["repository_files"]) != set(REPOSITORY_FILES):
        raise ValueError("Missing or unexpected repository metadata files.")
    for digest in manifest["repository_files"].values():
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("Invalid metadata SHA-256 digest.")


def safe_destination(root, relative):
    """Fixed manifest targets must remain inside a trusted local project directory."""
    root = Path(root).resolve()
    path = root / relative
    if not path.resolve().is_relative_to(root):
        raise ValueError("Destination escapes the project directory.")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError("Symlink destinations are not supported.")
    return path


def verify_repository(manifest, root):
    """Pin small tracked metadata to the reference experiment before installing assets."""
    for relative, digest in manifest["repository_files"].items():
        path = safe_destination(root, relative)
        if not path.is_file() or sha256_file(path) != digest:
            raise ValueError(f"Repository metadata differs from the manifest: {relative}")
    selection = json.loads((Path(root) / "reports/ml/selection.json").read_text())
    model = next(item for item in manifest["files"] if item["id"] == "model")
    if selection["model_sha256"] != model["sha256"]:
        raise ValueError("Model digest differs from the saved selection.")


def verify_file(path, item):
    if Path(path).stat().st_size != item["size_bytes"] or sha256_file(path) != item["sha256"]:
        raise ValueError(f"Size or SHA-256 mismatch: {item['asset']}")


def require_authorized_release(manifest):
    if manifest.get("distribution_authorized") is not True or manifest.get("legal_status") != "cleared":
        raise ValueError("Downloads disabled: redistribution review and owner publication authorization are pending.")
    repository = manifest.get("repository")
    if not isinstance(repository, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository):
        raise ValueError("Set the approved GitHub owner/repository in the reviewed manifest.")


def validate_download_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in DOWNLOAD_HOSTS
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise ValueError("Only HTTPS GitHub Release asset hosts are permitted.")


class GitHubRedirectHandler(HTTPRedirectHandler):
    """Check redirect destinations before making the redirected network request."""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        validate_download_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def download_file(url, destination, item):
    """Bounded streaming; install only a complete verified file, never deserialize it."""
    validate_download_url(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=f".{item['asset']}.",
                                         suffix=".part", delete=False) as output:
            temporary = Path(output.name)
            with build_opener(GitHubRedirectHandler()).open(url, timeout=30) as response:
                validate_download_url(response.geturl())
                received = 0
                while chunk := response.read(64 * 1024):
                    received += len(chunk)
                    if received > item["size_bytes"]:
                        raise ValueError(f"Download exceeds declared size: {item['asset']}")
                    output.write(chunk)
        verify_file(temporary, item)
        # No overwrite, including a destination created while the transfer was running.
        destination.hardlink_to(temporary)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def prepare_artifacts(manifest, root=ROOT, profile="historical", *, download=False, check=False):
    """A plain invocation plans only; check is local-only; download requires authorization."""
    validate_manifest(manifest)
    if profile not in PROFILES or (download and check):
        raise ValueError("Choose one supported profile and one action.")
    verify_repository(manifest, root)
    items = [item for item in manifest["files"] if item["id"] in PROFILES[profile]]
    if download:
        require_authorized_release(manifest)  # before network or filesystem mutations
    # Preflight every existing destination before downloading anything.
    for item in items:
        path = safe_destination(root, item["destination"])
        if path.exists():
            verify_file(path, item)
        elif check:
            raise ValueError(f"Missing local asset: {item['asset']}")
    if download:
        for item in items:
            path = safe_destination(root, item["destination"])
            if not path.exists():
                url = (f"https://github.com/{manifest['repository']}/releases/download/"
                       f"{manifest['planned_release_tag']}/{item['asset']}")
                download_file(url, path, item)
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="historical")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="Verify existing local files; no network")
    action.add_argument("--download", action="store_true", help="Explicitly download an authorized pinned Release")
    args = parser.parse_args()
    try:
        manifest = json.loads(MANIFEST.read_text())
        items = prepare_artifacts(manifest, profile=args.profile, download=args.download, check=args.check)
    except (OSError, URLError, ValueError, KeyError, TypeError, StopIteration) as error:
        parser.exit(1, f"Artifact preparation failed: {error}\n")
    for item in items:
        print(f"{item['asset']}: {item['size_bytes']:,} bytes -> {item['destination']}")
    if args.check:
        print("Local integrity checks passed. No model loaded and no network request made.")
    elif args.download:
        print("Verified assets installed. No model loaded or trained.")
    else:
        print("Plan only. No downloads performed; see docs/ARTIFACTS.md for authorization requirements.")


if __name__ == "__main__":
    main()
