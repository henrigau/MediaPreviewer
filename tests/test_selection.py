import unittest
from pathlib import Path

from media_preview.selection import (
    parse_clipboard_payload,
    parse_gnome_copied_files,
    parse_plain_paths,
    parse_uri_list,
    path_from_uri,
)


class SelectionParsingTests(unittest.TestCase):
    def test_path_from_file_uri(self):
        self.assertEqual(path_from_uri("file:///home/henri/Pictures/a%20b.png"), Path("/home/henri/Pictures/a b.png"))

    def test_path_from_localhost_file_uri(self):
        self.assertEqual(path_from_uri("file://localhost/home/henri/%C3%9Cbung.pdf"), Path("/home/henri/Übung.pdf"))

    def test_reject_remote_uri(self):
        self.assertIsNone(path_from_uri("https://example.com/file.png"))
        self.assertIsNone(path_from_uri("file://server/share/file.png"))

    def test_parse_uri_list(self):
        payload = "# comment\nfile:///tmp/one.png\nfile:///tmp/two%202.mp4\n"
        self.assertEqual(parse_uri_list(payload), [Path("/tmp/one.png"), Path("/tmp/two 2.mp4")])

    def test_parse_gnome_copied_files(self):
        payload = "copy\nfile:///tmp/a.png\nfile:///tmp/b.pdf\n"
        self.assertEqual(parse_gnome_copied_files(payload), [Path("/tmp/a.png"), Path("/tmp/b.pdf")])

    def test_parse_plain_paths(self):
        payload = "~/Pictures/example.jpg\n/tmp/other.txt\n"
        self.assertEqual(parse_plain_paths(payload), [Path.home() / "Pictures/example.jpg", Path("/tmp/other.txt")])

    def test_sentinel_is_ignored(self):
        payload = b"media-preview-sentinel-123"
        self.assertEqual(parse_clipboard_payload("text/plain", payload, "media-preview-sentinel-123"), [])


if __name__ == "__main__":
    unittest.main()

