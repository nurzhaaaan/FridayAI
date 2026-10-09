from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from desktop.tools import Workspace, open_application


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_read_list_search_and_docx(self):
        (self.root / "brief.txt").write_text(
            "Жоба бюджеті 900 теңге.", encoding="utf-8"
        )
        (self.root / "sub").mkdir()
        (self.root / "sub" / "notes.md").write_text("notes")
        with zipfile.ZipFile(self.root / "report.docx", "w") as z:
            z.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>DOCX text</w:t></w:r></w:p></w:body></w:document>',
            )
        self.assertIn("900", self.workspace.read_file("brief.txt")["text"])
        self.assertEqual(self.workspace.read_file("report.docx")["text"], "DOCX text")
        self.assertIn("sub/notes.md", self.workspace.search_files("notes")["paths"])
        self.assertEqual(len(self.workspace.list_directory()["items"]), 3)

    def test_escape_secrets_and_symlinks(self):
        with tempfile.TemporaryDirectory() as outside:
            file = Path(outside) / "secret.txt"
            file.write_text("secret")
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            for path in (
                "../outside",
                str(file),
                "escape/secret.txt",
                ".env",
                ".ENV",
                ".SSH/id_RSA",
                ".netrc",
                ".ssh/id_rsa",
            ):
                with self.assertRaises(ValueError):
                    self.workspace.path(path)
        with self.assertRaises(ValueError):
            Workspace().read_file("brief.txt")

    def test_file_limits_and_formats(self):
        (self.root / "large.txt").write_bytes(b"x" * 2_000_001)
        with self.assertRaises(ValueError):
            self.workspace.read_file("large.txt")
        (self.root / "data.bin").write_bytes(b"\0")
        with self.assertRaises(ValueError):
            self.workspace.read_file("data.bin")
        (self.root / "truncated.md").write_text("x" * 24001)
        self.assertTrue(self.workspace.read_file("truncated.md")["truncated"])

    def test_atomic_write_and_conflict(self):
        file = self.root / "brief.txt"
        file.write_text("old")
        file.chmod(0o640)
        proposal = self.workspace.propose_write("brief.txt", "new")
        self.assertEqual(file.read_text(), "old")
        self.workspace.apply_write(proposal)
        self.assertEqual(file.read_text(), "new")
        self.assertEqual(file.stat().st_mode & 0o777, 0o640)
        pending = self.workspace.propose_write("brief.txt", "next")
        file.write_text("concurrent change")
        with self.assertRaises(ValueError):
            self.workspace.apply_write(pending)
        self.assertEqual(file.read_text(), "concurrent change")
        fresh = self.workspace.propose_write("summary.md", "summary")
        self.workspace.apply_write(fresh)
        self.assertEqual((self.root / "summary.md").read_text(), "summary")

    def test_symlink_swap_after_approval_cannot_write_outside(self):
        (self.root / "sub").mkdir()
        proposal = self.workspace.propose_write("sub/new.txt", "new")
        (self.root / "sub").rmdir()
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "sub").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.workspace.apply_write(proposal)
            self.assertFalse((Path(outside) / "new.txt").exists())

    @patch("desktop.tools.platform.system", return_value="Darwin")
    @patch(
        "desktop.tools.applications",
        return_value={"Calculator": "/System/Applications/Calculator.app"},
    )
    @patch("desktop.tools.subprocess.run")
    def test_application_uses_catalog_not_command_text(self, run, catalog, platform):
        self.assertEqual(
            open_application("calculator")["opened_application"], "Calculator"
        )
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/bin/open", "-a", "/System/Applications/Calculator.app"],
        )
        with self.assertRaises(ValueError):
            open_application("Calculator; rm -rf /")
        run.assert_called_once()
