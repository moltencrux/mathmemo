"""
SvgWebDisplay — show MathJax (or any) SVG via QWebEngineView / Chromium.

Also provides SvgPixmapRasterizer for list delegates: rasterize MathJax SVG to
QPixmap via Cairo (no WebEngine grab). Grabbing a QWebEngineView that is a
child of the main window can capture the whole app (recursive "mirror" effect).

Usage (display widget):
    w = SvgWebDisplay()
    w.load(svg_bytes)

Usage (list pixmap cache):
    ras = SvgPixmapRasterizer(parent)
    pm = ras.get(svg_bytes, logical_size, dpr)  # may be None once, then cached
"""

from __future__ import annotations

import hashlib
import logging
from collections import OrderedDict

from PyQt6.QtCore import Qt, QUrl, QSize, QByteArray, QObject, QTimer, QEventLoop, pyqtSignal
from PyQt6.QtGui import QPixmap, QGuiApplication
from PyQt6.QtWidgets import QSizePolicy, QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings


def _strip_xml_decl(svg_text: str) -> str:
    text = svg_text.lstrip()
    if text.startswith("<?xml"):
        text = text.split("?>", 1)[-1].lstrip()
    return text


def _force_dark_ink(svg_text: str) -> str:
    """Normalize currentColor / black rgb forms to solid #000000."""
    text = svg_text
    # Attribute and CSS forms seen in MathJax / cairo output
    for old, new in (
        ("currentColor", "#000000"),
        ("currentcolor", "#000000"),
        ("rgb(0%, 0%, 0%)", "#000000"),
        ("rgb(0%,0%,0%)", "#000000"),
        ("rgb(0, 0, 0)", "#000000"),
        ("rgb(0,0,0)", "#000000"),
    ):
        text = text.replace(old, new)
    return text


def svg_bytes_to_html(
    svg_bytes: bytes,
    *,
    bg: str = "#ffffff",
    padding_px: int = 4,
    h_align: str = "center",
    v_align: str = "center",
    ink: str = "#000000",
) -> str:
    """Minimal HTML page embedding the SVG for Chromium display (SvgWebDisplay)."""
    text = _force_dark_ink(_strip_xml_decl(svg_bytes.decode("utf-8", errors="replace")))
    justify = {
        "left": "flex-start",
        "center": "center",
        "right": "flex-end",
    }.get(h_align, "center")
    align = {
        "top": "flex-start",
        "center": "center",
        "bottom": "flex-end",
    }.get(v_align, "center")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: {bg};
    color: {ink};
    overflow: hidden;
  }}
  .wrap {{
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    display: flex;
    align-items: {align};
    justify-content: {justify};
    padding: {padding_px}px;
    color: {ink};
  }}
  .wrap svg {{
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
    display: block;
    color: {ink};
  }}
</style>
</head>
<body>
  <div class="wrap">
    {text}
  </div>
</body>
</html>
"""


class SvgWebDisplay(QWidget):
    """
    Drop-in style widget for accurate SVG display via Chromium.

    Use for previews / standalone cards — not for per-row list painting
    (see SvgPixmapRasterizer).
    """

    loadFinished = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._view = QWebEngineView(self)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        settings = self._view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, False)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view)

        self._svg_bytes: bytes | None = None
        self._bg = "#ffffff"
        self._padding_px = 4
        self._h_align = "center"
        self._v_align = "center"

        self._view.loadFinished.connect(self.loadFinished.emit)

    def load(self, source: bytes | QByteArray | str) -> bool:
        """
        Load SVG from bytes, QByteArray, or a filesystem path (str).

        Returns True if the content was accepted and handed to WebEngine.
        """
        if isinstance(source, QByteArray):
            data = bytes(source)
        elif isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        elif isinstance(source, str):
            with open(source, "rb") as f:
                data = f.read()
        else:
            raise TypeError(f"Unsupported source type: {type(source)!r}")

        self._svg_bytes = data
        self._apply()
        return True

    def loadSvg(self, svg_bytes: bytes) -> bool:
        """Alias for load(bytes) — matches mental model of QSvgRenderer.load."""
        return self.load(svg_bytes)

    def clear(self) -> None:
        self._svg_bytes = None
        self._view.setHtml("", QUrl("about:blank"))

    def svgData(self) -> bytes | None:
        return self._svg_bytes

    # --- presentation helpers ------------------------------------------------

    def setBackground(self, css_color: str) -> None:
        """CSS color for the page background, e.g. 'white', '#f8f8f8', 'transparent'."""
        self._bg = css_color
        if self._svg_bytes is not None:
            self._apply()

    def setPadding(self, px: int) -> None:
        self._padding_px = max(0, int(px))
        if self._svg_bytes is not None:
            self._apply()

    def setAlignment(self, horizontal: str = "center", vertical: str = "center") -> None:
        """horizontal: left|center|right; vertical: top|center|bottom"""
        self._h_align = horizontal
        self._v_align = vertical
        if self._svg_bytes is not None:
            self._apply()

    def webView(self) -> QWebEngineView:
        """Access the underlying view (zoomFactor, grab, etc.)."""
        return self._view

    def sizeHint(self) -> QSize:
        return QSize(400, 120)

    def minimumSizeHint(self) -> QSize:
        return QSize(40, 24)

    # --- internal ------------------------------------------------------------

    def _apply(self) -> None:
        if self._svg_bytes is None:
            return
        html = svg_bytes_to_html(
            self._svg_bytes,
            bg=self._bg if self._bg not in ("transparent", "none") else "#ffffff",
            padding_px=self._padding_px,
            h_align=self._h_align,
            v_align=self._v_align,
            ink="#000000",
        )
        self._view.setHtml(html, QUrl("about:blank"))


# ---------------------------------------------------------------------------
# List-delegate rasterizer — Cairo only (no WebEngine grab)
# ---------------------------------------------------------------------------


class SvgPixmapRasterizer(QObject):
    """
    Rasterize MathJax SVG to QPixmap for FormulaDelegate painting.

    Uses Cairo (cairosvg.svg2png), not QWebEngineView.grab(). Grabbing a
    WebEngine view parented under the main window can capture the whole UI
    and produce a recursive "mirror" effect in list cells.

    Cairo is not identical to Chromium, but it is far more faithful to MathJax
    SVG strokes than QSvgRenderer, and is safe/synchronous enough for a cache.
    """

    pixmapReady = pyqtSignal(bytes, QSize, float)

    def __init__(
        self,
        parent: QWidget | None = None,
        cache_size: int = 96,
        padding_px: int = 6,
    ):
        super().__init__(parent)
        self._cache_size = max(4, int(cache_size))
        # Logical-pixel margin around the formula inside each cell pixmap
        self._padding_px = max(0, int(padding_px))
        self._cache: OrderedDict[tuple, QPixmap] = OrderedDict()
        self._inflight: set[tuple] = set()
        self._queue: list[tuple] = []
        self._busy = False

    def setPadding(self, padding_px: int) -> None:
        """Logical pixels of whitespace around the formula (clears cache)."""
        padding_px = max(0, int(padding_px))
        if padding_px != self._padding_px:
            self._padding_px = padding_px
            self.clear()

    @staticmethod
    def cache_key(svg_bytes: bytes, logical_size: QSize, dpr: float) -> tuple:
        h = hashlib.sha1(svg_bytes).hexdigest()[:16]
        return (h, logical_size.width(), logical_size.height(), round(float(dpr), 3))

    def get(
        self,
        svg_bytes: bytes,
        logical_size: QSize,
        dpr: float | None = None,
    ) -> QPixmap | None:
        """
        Return a cached pixmap or None if not ready yet.

        On a miss, queues an asynchronous Chromium render. Connect to
        pixmapReady (or simply update the view viewport) to repaint when done.
        """
        if not svg_bytes or logical_size.width() < 1 or logical_size.height() < 1:
            return None
        if dpr is None:
            dpr = self._default_dpr()
        key = self.cache_key(svg_bytes, logical_size, dpr)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if key not in self._inflight:
            self._inflight.add(key)
            self._queue.append((key, svg_bytes, QSize(logical_size), float(dpr)))
            QTimer.singleShot(0, self._pump)
        return None

    def get_sync(
        self,
        svg_bytes: bytes,
        logical_size: QSize,
        dpr: float | None = None,
        timeout_ms: int = 5000,
    ) -> QPixmap | None:
        """Block (local event loop) until the pixmap is ready or timeout."""
        if dpr is None:
            dpr = self._default_dpr()
        key = self.cache_key(svg_bytes, logical_size, dpr)
        hit = self.get(svg_bytes, logical_size, dpr)
        if hit is not None:
            return hit
        # Cairo path is fast; process the queue synchronously
        self._pump_all()
        return self._cache.get(key)

    def invalidate(self, svg_bytes: bytes | None = None) -> None:
        """Drop cache entries. If svg_bytes is given, only that formula's sizes."""
        if svg_bytes is None:
            self._cache.clear()
            return
        h = hashlib.sha1(svg_bytes).hexdigest()[:16]
        for k in list(self._cache):
            if k[0] == h:
                del self._cache[k]

    def clear(self) -> None:
        self._cache.clear()
        self._queue.clear()
        self._inflight.clear()

    # --- internals -----------------------------------------------------------

    def _default_dpr(self) -> float:
        screen = QGuiApplication.primaryScreen()
        return float(screen.devicePixelRatio()) if screen else 1.0

    def _pump_all(self) -> None:
        while self._queue:
            self._pump_one()

    def _pump(self) -> None:
        if self._busy:
            return
        self._pump_one()
        if self._queue:
            QTimer.singleShot(0, self._pump)

    def _pump_one(self) -> None:
        if not self._queue:
            return
        self._busy = True
        key, svg_bytes, logical_size, dpr = self._queue.pop(0)
        try:
            pm = self._render_cairo(svg_bytes, logical_size, dpr)
            if pm is not None and not pm.isNull():
                pm.setDevicePixelRatio(dpr)
                self._cache[key] = pm
                self._cache.move_to_end(key)
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
                self.pixmapReady.emit(svg_bytes, logical_size, float(dpr))
            else:
                logging.warning(
                    "SvgPixmapRasterizer: Cairo render failed for %sx%s",
                    logical_size.width(),
                    logical_size.height(),
                )
        finally:
            self._inflight.discard(key)
            self._busy = False

    def _render_cairo(
        self, svg_bytes: bytes, logical_size: QSize, dpr: float
    ) -> QPixmap | None:
        """Rasterize via Cairo when WebEngine grab is blank. Still better than nothing."""
        try:
            from cairosvg import svg2png
        except ImportError:
            logging.error(
                "SvgPixmapRasterizer: cairosvg is required for list rendering"
            )
            return None
        try:
            from PyQt6.QtGui import QColor, QPainter

            pw = max(1, int(logical_size.width() * dpr))
            ph = max(1, int(logical_size.height() * dpr))
            pad = max(0, int(self._padding_px * dpr))
            # Keep a little room so the formula never sits flush on the cell edge
            inner_w = max(1, pw - 2 * pad)
            inner_h = max(1, ph - 2 * pad)

            text = _force_dark_ink(
                _strip_xml_decl(svg_bytes.decode("utf-8", errors="replace"))
            )
            png = svg2png(
                bytestring=text.encode("utf-8"),
                output_width=inner_w,
                output_height=inner_h,
                background_color="white",
            )
            content = QPixmap()
            if not content.loadFromData(png, "PNG"):
                return None

            # Full-size pixmap with white margin; center the formula content
            pm = QPixmap(pw, ph)
            pm.fill(QColor("white"))
            painter = QPainter(pm)
            x = (pw - content.width()) // 2
            y = (ph - content.height()) // 2
            painter.drawPixmap(x, y, content)
            painter.end()
            return pm
        except Exception as exc:
            logging.warning("SvgPixmapRasterizer: svg2png failed: %s", exc)
            return None
