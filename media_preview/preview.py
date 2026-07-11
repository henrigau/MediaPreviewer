from __future__ import annotations

import csv
import mimetypes
import os
import signal
import subprocess
import tempfile
from pathlib import Path

import cairo
import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")
gi.require_version("Poppler", "0.18")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Poppler  # noqa: E402

from .config import APP_ID, APP_NAME
from .state import clear_preview_pid, close_preview, current_preview_pid, write_preview_pid

OFFICE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".odp",
    ".ods",
    ".odt",
    ".ppt",
    ".pptx",
    ".rtf",
    ".xls",
    ".xlsx",
}

TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".css",
    ".ini",
    ".js",
    ".json",
    ".log",
    ".md",
    ".py",
    ".rs",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def guess_mime(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    result = subprocess.run(
        ["file", "--mime-type", "-b", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return "application/octet-stream"


def format_size(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        return "unknown size"

    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def load_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(
        b"""
        window {
          background: #0f1115;
          color: #f5f7fb;
        }
        .app-shell {
          background: #0f1115;
        }
        .topbar {
          background: linear-gradient(135deg, #151923, #11151d);
          padding: 12px 14px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.09);
        }
        .close-button {
          min-width: 36px;
          min-height: 36px;
          padding: 0;
          border-radius: 8px;
          color: #ffffff;
          background: rgba(255, 255, 255, 0.10);
          border: 1px solid rgba(255, 255, 255, 0.10);
        }
        .close-button:hover {
          background: rgba(239, 68, 68, 0.85);
        }
        .filename {
          font-weight: 700;
          font-size: 16px;
        }
        .muted {
          color: rgba(245, 247, 251, 0.62);
        }
        .type-badge {
          background: rgba(96, 165, 250, 0.18);
          color: #bfdbfe;
          border: 1px solid rgba(96, 165, 250, 0.30);
          border-radius: 999px;
          padding: 3px 9px;
          font-size: 11px;
          font-weight: 700;
        }
        .content {
          background: #0f1115;
        }
        .empty-state {
          padding: 32px;
        }
        .pdf-scroll {
          background: #20242d;
        }
        .pdf-page {
          background: #ffffff;
          color: #111111;
          margin: 18px;
          box-shadow: 0 8px 24px rgba(0, 0, 0, 0.30);
        }
        .media-controls {
          background: rgba(15, 17, 21, 0.96);
          padding: 10px;
          border-top: 1px solid rgba(255, 255, 255, 0.10);
        }
        .csv-grid {
          background: #10131a;
        }
        .csv-cell {
          padding: 7px 10px;
          border-right: 1px solid rgba(255, 255, 255, 0.07);
          border-bottom: 1px solid rgba(255, 255, 255, 0.07);
          color: #edf2f7;
          font-family: monospace;
          font-size: 12px;
        }
        .csv-header {
          background: #1d2430;
          color: #ffffff;
          font-weight: 700;
        }
        .csv-index {
          background: #151a23;
          color: rgba(245, 247, 251, 0.58);
        }
        textview, text {
          background: #10131a;
          color: #f5f7fb;
          font-family: monospace;
          font-size: 13px;
        }
        """
    )
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class PdfPage(Gtk.DrawingArea):
    def __init__(self, page: Poppler.Page, page_number: int, scale: float = 1.45) -> None:
        super().__init__()
        self.page = page
        self.page_number = page_number
        self.scale = scale
        width, height = page.get_size()
        self.set_content_width(max(1, int(width * scale)))
        self.set_content_height(max(1, int(height * scale)))
        self.set_hexpand(False)
        self.set_halign(Gtk.Align.CENTER)
        self.add_css_class("pdf-page")
        self.set_draw_func(self._draw)

    def _draw(self, _area: Gtk.DrawingArea, context: cairo.Context, width: int, height: int) -> None:
        context.set_source_rgb(1, 1, 1)
        context.rectangle(0, 0, width, height)
        context.fill()
        context.save()
        context.scale(self.scale, self.scale)
        self.page.render(context)
        context.restore()


class PdfPreview(Gtk.ScrolledWindow):
    def __init__(self, pdf_path: Path) -> None:
        super().__init__()
        self.pdf_path = pdf_path
        uri = GLib.filename_to_uri(str(self.pdf_path), None)
        self.document = Poppler.Document.new_from_file(uri, None)

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.add_css_class("pdf-scroll")
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        pages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        pages.set_halign(Gtk.Align.CENTER)
        pages.set_margin_top(10)
        pages.set_margin_bottom(10)

        for index in range(self.document.get_n_pages()):
            page = self.document.get_page(index)
            pages.append(PdfPage(page, index + 1))

        self.set_child(pages)


class PreviewWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, path: Path) -> None:
        super().__init__(application=app)
        self.path = path
        self.mime_type = guess_mime(path) if path.exists() else "missing"
        self.cleanups: list[object] = []
        self.released_app_hold = False

        self.set_title(path.name)
        self.set_default_size(1100, 780)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        root.add_css_class("app-shell")
        self.set_content(root)

        topbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        topbar.add_css_class("topbar")
        topbar.set_hexpand(True)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        title_box.set_hexpand(True)
        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_row.set_hexpand(True)

        filename = Gtk.Label(label=path.name, xalign=0)
        filename.add_css_class("filename")
        filename.set_ellipsize(3)
        filename.set_hexpand(True)

        type_badge = Gtk.Label(label=self._display_type())
        type_badge.add_css_class("type-badge")

        title_row.append(filename)
        title_row.append(type_badge)

        meta = Gtk.Label(label=f"{format_size(path)} · {path.parent}", xalign=0)
        meta.add_css_class("muted")
        meta.set_ellipsize(3)
        title_box.append(title_row)
        title_box.append(meta)

        close_button = Gtk.Button()
        close_label = Gtk.Label(label="×")
        close_label.add_css_class("title-2")
        close_button.set_child(close_label)
        close_button.add_css_class("close-button")
        close_button.set_tooltip_text("Close")
        close_button.connect("clicked", lambda _button: self.close())

        topbar.append(title_box)
        topbar.append(close_button)
        root.append(topbar)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.add_css_class("content")
        content.set_hexpand(True)
        content.set_vexpand(True)
        root.append(content)

        content.append(self._build_content())

        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_controller)
        self.connect("close-request", self._on_close_request)

    def _display_type(self) -> str:
        if self.path.suffix:
            return self.path.suffix.lstrip(".").upper()
        if "/" in self.mime_type:
            return self.mime_type.split("/", 1)[1].upper()
        return self.mime_type.upper()

    def _on_key_pressed(self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state: Gdk.ModifierType) -> bool:
        if keyval in (Gdk.KEY_Escape, Gdk.KEY_space):
            self.close()
            return True
        return False

    def _on_close_request(self, _window: Gtk.Window) -> bool:
        for item in self.cleanups:
            cleanup = getattr(item, "cleanup", None)
            if callable(cleanup):
                cleanup()
        clear_preview_pid(os.getpid())
        app = self.get_application()
        if app is not None and not self.released_app_hold:
            self.released_app_hold = True
            app.release()
        return False

    def _build_content(self) -> Gtk.Widget:
        try:
            if not self.path.exists():
                return self._status_widget("File not found", str(self.path))
            if self.path.is_dir():
                return self._status_widget("Directory preview is not supported", str(self.path))
            if self.mime_type.startswith("image/"):
                return self._image_widget(self.path)
            if self.mime_type.startswith(("video/", "audio/")):
                return self._video_widget(self.path)
            if self.mime_type == "application/pdf":
                return self._pdf_widget(self.path)
            if self.path.suffix.lower() in OFFICE_EXTENSIONS:
                return self._office_widget(self.path)
            if self.path.suffix.lower() == ".csv" or self.mime_type in {"text/csv", "application/csv"}:
                return self._csv_widget(self.path)
            if self.mime_type.startswith("text/") or self.path.suffix.lower() in TEXT_EXTENSIONS:
                return self._text_widget(self.path)
            return self._text_widget(self.path, force_text=True)
        except Exception as exc:
            return self._status_widget("Preview failed", str(exc))

    def _image_widget(self, path: Path) -> Gtk.Widget:
        picture = Gtk.Picture.new_for_file(Gio.File.new_for_path(str(path)))
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        picture.set_can_shrink(True)
        if hasattr(picture, "set_content_fit"):
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        return picture

    def _video_widget(self, path: Path) -> Gtk.Widget:
        media = Gtk.MediaFile.new_for_file(Gio.File.new_for_path(str(path)))
        media.set_loop(True)
        media.set_playing(True)

        video = Gtk.Video()
        video.set_media_stream(media)
        video.set_hexpand(True)
        video.set_vexpand(True)
        if hasattr(video, "set_controls"):
            video.set_controls(True)
        if hasattr(video, "set_autoplay"):
            video.set_autoplay(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)
        box.set_vexpand(True)
        box.append(video)
        return box

    def _pdf_widget(self, path: Path) -> Gtk.Widget:
        pdf = PdfPreview(path)
        self.cleanups.append(pdf)
        return pdf

    def _office_widget(self, path: Path) -> Gtk.Widget:
        tmpdir = tempfile.TemporaryDirectory(prefix="media-preview-office-")
        self.cleanups.append(tmpdir)
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir.name, str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=60,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "LibreOffice conversion failed"
            raise RuntimeError(error)

        candidates = sorted(Path(tmpdir.name).glob("*.pdf"))
        if not candidates:
            raise RuntimeError("LibreOffice did not produce a PDF")
        return self._pdf_widget(candidates[0])

    def _csv_widget(self, path: Path) -> Gtk.Widget:
        max_rows = 2000
        max_columns = 80

        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as sample_handle:
            sample = sample_handle.read(8192)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        rows: list[list[str]] = []
        truncated = False
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            reader = csv.reader(handle, dialect)
            for row_index, row in enumerate(reader):
                if row_index >= max_rows:
                    truncated = True
                    break
                if len(row) > max_columns:
                    row = row[:max_columns]
                    truncated = True
                rows.append(row)

        if not rows:
            return self._status_widget("Empty CSV", str(path))

        column_count = max(len(row) for row in rows)
        grid = Gtk.Grid()
        grid.add_css_class("csv-grid")
        grid.set_column_spacing(0)
        grid.set_row_spacing(0)
        grid.set_hexpand(True)
        grid.set_vexpand(True)

        def attach_cell(text: str, column: int, row: int, css_classes: tuple[str, ...]) -> None:
            label = Gtk.Label(label=text, xalign=0)
            label.set_selectable(True)
            label.set_ellipsize(3)
            label.set_width_chars(14)
            label.set_max_width_chars(36)
            for css_class in css_classes:
                label.add_css_class(css_class)
            grid.attach(label, column, row, 1, 1)

        attach_cell("#", 0, 0, ("csv-cell", "csv-header", "csv-index"))
        header = rows[0]
        for column in range(column_count):
            label = header[column] if column < len(header) and header[column] else f"Column {column + 1}"
            attach_cell(label, column + 1, 0, ("csv-cell", "csv-header"))

        for row_number, row in enumerate(rows[1:], start=1):
            attach_cell(str(row_number), 0, row_number, ("csv-cell", "csv-index"))
            for column in range(column_count):
                attach_cell(row[column] if column < len(row) else "", column + 1, row_number, ("csv-cell",))

        if truncated:
            attach_cell("Preview truncated", 0, len(rows), ("csv-cell", "csv-index"))
            attach_cell(f"Showing first {max_rows} rows and {max_columns} columns.", 1, len(rows), ("csv-cell",))

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(grid)
        return scrolled

    def _text_widget(self, path: Path, force_text: bool = False) -> Gtk.Widget:
        max_bytes = 512 * 1024
        data = path.read_bytes()
        truncated = len(data) > max_bytes
        text = data[:max_bytes].decode("utf-8", "replace")
        if force_text:
            text = f"[{self.mime_type} rendered as text]\n\n{text}"
        if truncated:
            text += "\n\n[Preview truncated]"

        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(text)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        scrolled.set_child(view)
        return scrolled

    def _status_widget(self, title: str, detail: str) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.add_css_class("empty-state")
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        heading = Gtk.Label(label=title)
        heading.add_css_class("title-2")
        heading.set_wrap(True)
        body = Gtk.Label(label=detail)
        body.add_css_class("muted")
        body.set_wrap(True)
        body.set_selectable(True)
        box.append(heading)
        box.append(body)
        return box


class PreviewApp(Adw.Application):
    def __init__(self, path: Path) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.path = path
        self.window: PreviewWindow | None = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        load_css()

    def do_activate(self) -> None:
        self.hold()
        self.window = PreviewWindow(self, self.path)
        self.window.present()


def run_preview(path: Path) -> int:
    existing_pid = current_preview_pid()
    if existing_pid is not None and existing_pid != os.getpid():
        close_preview()

    app = PreviewApp(path)

    def terminate(_signum: int, _frame: object) -> None:
        app.quit()

    signal.signal(signal.SIGTERM, terminate)
    write_preview_pid(os.getpid())
    try:
        return app.run([APP_NAME])
    finally:
        clear_preview_pid(os.getpid())
