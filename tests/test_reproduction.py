"""Check experiment isolation without fitting models or reopening the test set."""

from pathlib import Path
import tempfile
import unittest

from scripts.create_reproduction import ROOT, create_workspace


class ReproductionTests(unittest.TestCase):
    def test_workspace_copies_code_and_protocol_but_no_results_or_models(self):
        with tempfile.TemporaryDirectory() as folder:
            # A controlled source fixture keeps this test independent of real artifacts.
            source = Path(folder) / "source"
            source.mkdir()
            for directory in ("scripts", "api", "dashboard", "tests", ".streamlit"):
                (source / directory).mkdir()
                (source / directory / "sample.py").write_text("# controlled test fixture\n")
            (source / ".streamlit/secrets.toml").write_text("private = true\n")
            for name in ("requirements-all.txt", ".python-version", ".gitignore"):
                (source / name).write_text("fixture\n")
            (source / "reports/ml").mkdir(parents=True)
            (source / "reports/ml/selection.json").write_text("{}")
            (source / "reports/phase3_protocol.md").write_text("protocol")
            (source / "data").mkdir()
            (source / "data/SOURCES.md").write_text("attribution")
            (source / "artifacts").mkdir()
            (source / "artifacts/manifest.json").write_text("{}")
            (source / "artifacts/private.joblib").write_bytes(b"controlled fixture")
            result = create_workspace(source / ".reproductions/run-01", source)
            self.assertTrue((result / "scripts/sample.py").is_file())
            self.assertEqual((result / "reports/phase3_protocol.md").read_text(), "protocol")
            self.assertFalse((result / "reports/ml").exists())
            self.assertFalse((result / "models").exists())
            self.assertFalse((result / ".streamlit/secrets.toml").exists())
            self.assertEqual((result / "artifacts/manifest.json").read_text(), "{}")
            self.assertFalse((result / "artifacts/private.joblib").exists())
            self.assertEqual(list((result / "data/raw").iterdir()), [])
            with self.assertRaises(FileExistsError):
                create_workspace(result, source)

    def test_original_and_source_subdirectories_cannot_be_destinations(self):
        for destination in (ROOT, ROOT / "scripts/nested", ROOT.parent / "elsewhere", ROOT / ".reproductions/nested/run"):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                create_workspace(destination)
