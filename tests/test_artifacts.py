"""Offline transfer tests with controlled bytes; never download or deserialize a model."""

from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request

from scripts.download_artifacts import (MANIFEST, REPOSITORY_FILES, TARGETS,
    GitHubRedirectHandler, prepare_artifacts, sha256_file, validate_download_url, validate_manifest)


class Response(BytesIO):
    def __init__(self, data, url="https://release-assets.githubusercontent.com/test"):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.manifest = json.loads(MANIFEST.read_text())
        self.manifest.update(distribution_authorized=True, legal_status="cleared", repository="test-owner/test-project")
        self.payloads = {kind: f"controlled test bytes: {kind}".encode() for kind in TARGETS}
        for item in self.manifest["files"]:
            payload = self.payloads[item["id"]]
            item.update(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
        for relative in REPOSITORY_FILES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("controlled metadata fixture\n")
        model = next(item for item in self.manifest["files"] if item["id"] == "model")
        (self.root / "reports/ml/selection.json").write_text(json.dumps({"model_sha256": model["sha256"]}))
        self.manifest["repository_files"] = {
            relative: sha256_file(self.root / relative) for relative in REPOSITORY_FILES}

    def opener(self, alter=None):
        def open_response(url, timeout):
            self.assertEqual(timeout, 30)
            self.assertIn("/test-owner/test-project/releases/download/v1.0.0/", url)
            item = next(item for item in self.manifest["files"] if url.endswith('/' + item["asset"]))
            data = self.payloads[item["id"]]
            return Response(alter(data) if alter else data)
        return Mock(open=Mock(side_effect=open_response))

    def test_committed_manifest_is_a_pinned_authorized_release(self):
        manifest = json.loads(MANIFEST.read_text())
        validate_manifest(manifest)
        self.assertIs(manifest["distribution_authorized"], True)
        self.assertEqual(manifest["repository"], "Hugo-bordas/Ireland-Electricity-Demand-Forecasting")
        self.assertEqual(manifest["legal_status"], "cleared")
        self.assertEqual(manifest["permission_notice"], "docs/DATA_TERMS.md")
        self.assertIn("non-commercial", manifest["permission_scope"])
        self.assertEqual({item["id"] for item in manifest["files"]}, set(TARGETS))

    def test_default_plan_does_not_download_or_create_asset_directories(self):
        with patch("scripts.download_artifacts.build_opener") as opener:
            items = prepare_artifacts(self.manifest, self.root, "full")
        opener.assert_not_called()
        self.assertEqual(len(items), 3)
        self.assertFalse((self.root / "models").exists())

    def test_authorization_and_repository_required_before_network(self):
        changes = [{"distribution_authorized": False}, {"distribution_authorized": "true"},
                   {"legal_status": "pending_review"}, {"repository": None},
                   {"repository": "https://evil.example/project"}, {"repository": "../project"}]
        for change in changes:
            with self.subTest(change=change), patch("scripts.download_artifacts.build_opener") as opener:
                manifest = {**self.manifest, **change}
                with self.assertRaises(ValueError):
                    prepare_artifacts(manifest, self.root, download=True)
                opener.assert_not_called()

    def test_full_download_installs_exact_bytes_without_model_loading(self):
        with patch("scripts.download_artifacts.build_opener", return_value=self.opener()), \
             patch("joblib.load", side_effect=AssertionError("Deserialization forbidden")), \
             patch("pickle.load", side_effect=AssertionError("Deserialization forbidden")), \
             patch("pickle.loads", side_effect=AssertionError("Deserialization forbidden")), \
             patch("sklearn.ensemble.RandomForestRegressor.fit", side_effect=AssertionError("Training forbidden")):
            prepare_artifacts(self.manifest, self.root, "full", download=True)
        for item in self.manifest["files"]:
            self.assertEqual((self.root / item["destination"]).read_bytes(), self.payloads[item["id"]])
        self.assertEqual(list(self.root.rglob('*.part')), [])

    def test_historical_profile_does_not_install_the_model(self):
        with patch("scripts.download_artifacts.build_opener", return_value=self.opener()):
            prepare_artifacts(self.manifest, self.root, "historical", download=True)
        self.assertFalse((self.root / TARGETS["model"][1]).exists())
        self.assertTrue((self.root / TARGETS["historical"][1]).is_file())

    def test_truncated_oversized_or_tampered_download_leaves_no_final_file(self):
        for alter in (lambda data: data[:-1], lambda data: data+b'extra', lambda data: b'X'*len(data)):
            with self.subTest(alter=alter), patch("scripts.download_artifacts.build_opener", return_value=self.opener(alter)):
                with self.assertRaises(ValueError):
                    prepare_artifacts(self.manifest, self.root, download=True)
                self.assertFalse((self.root / TARGETS["historical"][1]).exists())
                self.assertEqual(list(self.root.rglob('*.part')), [])

    def test_interrupted_transfer_cleans_temporary_file(self):
        class InterruptedResponse(Response):
            def read(self, size=-1):
                if self.tell():
                    raise OSError("Simulated interruption after receiving bytes")
                return super().read(size)

        opener = Mock(open=Mock(return_value=InterruptedResponse(b"partial")))
        with patch("scripts.download_artifacts.build_opener", return_value=opener), self.assertRaises(OSError):
            prepare_artifacts(self.manifest, self.root, download=True)
        self.assertEqual(list(self.root.rglob('*.part')), [])
        self.assertFalse((self.root / TARGETS["historical"][1]).exists())

    def test_destination_created_during_transfer_is_never_overwritten(self):
        path = self.root / TARGETS["historical"][1]
        item = next(item for item in self.manifest["files"] if item["id"] == "historical")

        def response_with_competing_file(url, timeout):
            path.write_bytes(b"created concurrently")
            return Response(self.payloads[item["id"]])

        opener = Mock(open=Mock(side_effect=response_with_competing_file))
        with patch("scripts.download_artifacts.build_opener", return_value=opener), self.assertRaises(FileExistsError):
            prepare_artifacts(self.manifest, self.root, download=True)
        self.assertEqual(path.read_bytes(), b"created concurrently")
        self.assertEqual(list(self.root.rglob('*.part')), [])

    def test_existing_verified_files_are_reused_without_network(self):
        for item in self.manifest["files"]:
            path = self.root / item["destination"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.payloads[item["id"]])
        with patch("scripts.download_artifacts.build_opener") as opener:
            prepare_artifacts(self.manifest, self.root, "full", download=True)
            prepare_artifacts(self.manifest, self.root, "full", check=True)
        opener.assert_not_called()

    def test_existing_wrong_file_is_preserved_and_blocks_downloads(self):
        path = self.root / TARGETS["historical"][1]
        path.parent.mkdir(parents=True)
        path.write_bytes(b"keep this file")
        with patch("scripts.download_artifacts.build_opener") as opener, self.assertRaises(ValueError):
            prepare_artifacts(self.manifest, self.root, "full", download=True)
        self.assertEqual(path.read_bytes(), b"keep this file")
        opener.assert_not_called()
        self.assertFalse((self.root / "models").exists())

    def test_local_check_missing_file_fails_without_network(self):
        with patch("scripts.download_artifacts.build_opener") as opener, self.assertRaisesRegex(ValueError, "Missing local asset"):
            prepare_artifacts(self.manifest, self.root, check=True)
        opener.assert_not_called()

    def test_changed_repository_metadata_blocks_download(self):
        (self.root / "requirements.txt").write_text("changed")
        with patch("scripts.download_artifacts.build_opener") as opener, self.assertRaisesRegex(ValueError, "metadata differs"):
            prepare_artifacts(self.manifest, self.root, download=True)
        opener.assert_not_called()

    def test_manifest_model_digest_must_agree_with_selection(self):
        item = next(item for item in self.manifest["files"] if item["id"] == "model")
        item["sha256"] = '0'*64
        with self.assertRaisesRegex(ValueError, "saved selection"):
            prepare_artifacts(self.manifest, self.root)

    def test_unsafe_manifest_paths_names_sizes_and_versions_are_rejected(self):
        changes = [("destination", "../escape"), ("destination", "/tmp/escape"),
                   ("asset", "../model"), ("size_bytes", -1), ("size_bytes", True),
                   ("size_bytes", 2**31), ("sha256", "incorrect")]
        for key, value in changes:
            manifest = deepcopy(self.manifest)
            manifest["files"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_manifest(manifest)
        for tag in ("latest", "main", "v1/../main"):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                validate_manifest({**self.manifest, "planned_release_tag": tag})

    def test_symlink_destination_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "data").symlink_to(outside, target_is_directory=True)
            with patch("scripts.download_artifacts.build_opener") as opener, self.assertRaises(ValueError):
                prepare_artifacts(self.manifest, self.root, download=True)
            opener.assert_not_called()
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_redirects_and_final_urls_cannot_leave_https_github_hosts(self):
        bad_urls = ["http://github.com/asset", "https://evil.example/asset",
                    "https://github.com.evil.example/asset", "https://github.com:444/asset",
                    "https://user:secret@github.com/asset", "file:///tmp/asset"]
        for url in bad_urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_download_url(url)
            with self.subTest(redirect=url), self.assertRaises(ValueError):
                GitHubRedirectHandler().redirect_request(Request("https://github.com/asset"), None, 302, "Found", {}, url)
        opener = Mock(open=Mock(return_value=Response(b"irrelevant", "https://evil.example/asset")))
        with patch("scripts.download_artifacts.build_opener", return_value=opener), self.assertRaises(ValueError):
            prepare_artifacts(self.manifest, self.root, download=True)
        self.assertEqual(list(self.root.rglob('*.part')), [])


if __name__ == "__main__":
    unittest.main()
