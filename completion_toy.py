#!/usr/bin/env python3
"""Standalone demo for mathmemo.completion_edit.CompletionTextEdit.

Run from the artifacts directory (or anywhere on PYTHONPATH with mathmemo):

    python3 completion_toy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing mathmemo when run from artifacts/
_ROOT = Path(__file__).resolve().parent
_MM = _ROOT / "mathmemo"
if str(_MM) not in sys.path:
    sys.path.insert(0, str(_MM))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QApplication

from completion_edit import (  # type: ignore  # mathmemo on path
    COMPLETIONS,
    OPEN_CLOSE,
    CompletionTextEdit,
)


def main():
    app = QApplication(sys.argv)
    editor = CompletionTextEdit()
    editor.configure(words=COMPLETIONS, open_close=OPEN_CLOSE)
    editor.setWindowTitle("Atomic closers — dim / fold / mutate")
    editor.resize(780, 480)
    editor.setPlainText(
        "Atomic closers (orange = committed, dim = uncommitted suffix):\n"
        "  \\left(  →  \\left( | \\right)   real closer, atomic under Backspace\n"
        "  Backspace into closer → dim suffix; delim may become .\n"
        "  Matching keys → type-through / fold\n"
        "  \\r + m → \\rm\\right.   (abandon / push solid)\n"
        "  Fence \\ra → \\right\\rangle with dimmed tail\n"
        "  a^{\\}  → literal \\} inside braces\n"
        "\n--- try below ---\n"
    )
    c = editor.textCursor()
    c.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(c)
    editor.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
