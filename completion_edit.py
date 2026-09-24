"""Atomic closer / delimiter completion for formula editing.

CompletionTextEdit (QPlainTextEdit subclass) provides:
  - pair tracking with semi-atomic closers
  - dimmed uncommitted closer suffixes
  - fold / abandon for \\right type-through
  - fence mutation (e.g. ) -> \\rangle)
  - QCompleter popup for \\commands

Used by FormulaEdit and by the standalone completion_toy.py demo.
"""

from __future__ import annotations

import sys
import re
from dataclasses import dataclass, field

from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import (
    QFontDatabase,
    QTextCursor,
    QKeyEvent,
    QColor,
    QTextCharFormat,
)
from PyQt6.QtWidgets import QApplication, QCompleter, QPlainTextEdit, QTextEdit

# PyQt6 only exposes ExtraSelection on QTextEdit; PlainTextEdit accepts it.
_ExtraSelection = QTextEdit.ExtraSelection


LEFT_RIGHT_DELIMS = [
    "(", ")", "[", "]", r"\{", r"\}",
    "|", r"\|",
    r"\langle", r"\rangle",
    r"\lvert", r"\rvert",
    r"\lVert", r"\rVert",
    r"\lfloor", r"\rfloor",
    r"\lceil", r"\rceil",
    ".",
]

_LEFT_RIGHT_DEFAULTS = {
    "(": ")",
    ")": "(",
    "[": "]",
    "]": "[",
    r"\{": r"\}",
    r"\}": r"\{",
    "|": "|",
    r"\|": r"\|",
    r"\langle": r"\rangle",
    r"\rangle": r"\langle",
    r"\lvert": r"\rvert",
    r"\rvert": r"\lvert",
    r"\lVert": r"\rVert",
    r"\rVert": r"\lVert",
    r"\lfloor": r"\rfloor",
    r"\rfloor": r"\lfloor",
    r"\lceil": r"\rceil",
    r"\rceil": r"\lceil",
    ".": ".",
}

OPEN_CLOSE: dict[str, str] = {
    "{": "}",
    r"\sqrt": "{}",
    r"\frac": "{}{}",
    r"\begin{matrix}": r"\end{matrix}",
}
for _d, _m in _LEFT_RIGHT_DEFAULTS.items():
    OPEN_CLOSE[r"\left" + _d] = r"\right" + _m

COMPLETIONS = (
    [r"\left" + d for d in LEFT_RIGHT_DELIMS]
    + [r"\right" + d for d in LEFT_RIGHT_DELIMS]
    + [
        r"\sqrt", r"\sum", r"\frac", r"\partial",
        r"\alpha", r"\beta", r"\gamma", r"\rm",
        r"\begin{matrix}", r"\end{matrix}", r"\operatorname",
    ]
)


def is_right_closer(s: str) -> bool:
    return s.startswith(r"\right")


# Preferred when several \-command fences share a stem (e.g. only "\" typed).
PREFERRED_CMD_DELIMS = [
    r"\rangle",
    r"\langle",
    r"\rvert",
    r"\lvert",
    r"\rVert",
    r"\lVert",
    r"\rfloor",
    r"\lfloor",
    r"\rceil",
    r"\lceil",
    r"\|",
    r"\{",
    r"\}",
]

VALID_RIGHT_CLOSERS = {r"\right" + d for d in LEFT_RIGHT_DELIMS}


def closer_substitutes(expected: str) -> list[str]:
    """Valid ``\\right…`` forms only; incomplete stems like ``\\right\\`` omitted."""
    if not is_right_closer(expected):
        return [expected]
    alts = [r"\right" + d for d in LEFT_RIGHT_DELIMS]
    delim = right_delim_of(expected)
    # Prefer fences that continue the typed delim stem
    if delim and delim not in LEFT_RIGHT_DELIMS:
        ranked = [r"\right" + d for d in LEFT_RIGHT_DELIMS if d.startswith(delim)]
        rest = [c for c in alts if c not in ranked]
        return ranked + rest if ranked else alts
    if expected in VALID_RIGHT_CLOSERS:
        return [expected] + [c for c in alts if c != expected]
    return alts


def right_delim_of(closer: str) -> str:
    if not closer.startswith(r"\right"):
        return closer[-1] if closer else "."
    return closer[len(r"\right"):] or "."


def with_right_delim(closer: str, delim: str) -> str:
    if is_right_closer(closer):
        return r"\right" + delim
    return delim


@dataclass
class TokenPair:
    opener_left: QTextCursor
    opener_right: QTextCursor
    closer_left: QTextCursor
    closer_right: QTextCursor
    opener_expected: str
    closer_expected: str
    dim_mark: QTextCursor | None = None

    def opener_span(self) -> tuple[int, int]:
        a, b = self.opener_left.position(), self.opener_right.position()
        return min(a, b), max(a, b)

    def closer_span(self) -> tuple[int, int]:
        a, b = self.closer_left.position(), self.closer_right.position()
        return min(a, b), max(a, b)

    def dim_from(self) -> int:
        if self.dim_mark is None:
            return self.closer_span()[1]
        return self.dim_mark.position()

    def opener_text(self, doc: str) -> str:
        a, b = self.opener_span()
        return doc[a:b]


class CompletionTextEdit(QPlainTextEdit):
    """Designer-friendly: ``__init__(parent)`` only; call ``configure()`` after.

    The .ui file can promote QPlainTextEdit → CompletionTextEdit.  Catalog and
    open/close maps are applied from FormulaEdit (or the toy) via configure().
    """

    def __init__(self, parent=None, words=None, open_close=None):
        # Accept optional words/open_close for the standalone toy; designer
        # only passes parent.
        self.completer = None
        super().__init__(parent)
        self.open_close: dict[str, str] = {}
        self.pairs: list[TokenPair] = []
        self._guard = False
        self._all_completions: list[str] = []
        self._configured = False

        self._fmt_opener = QTextCharFormat()
        self._fmt_opener.setBackground(QColor(180, 220, 255, 120))
        self._fmt_closer = QTextCharFormat()
        self._fmt_closer.setBackground(QColor(255, 200, 150, 140))
        self._fmt_dim = QTextCharFormat()
        self._fmt_dim.setForeground(QColor(160, 160, 160))
        self._fmt_dim.setBackground(QColor(255, 200, 150, 60))

        if words is not None or open_close is not None:
            self.configure(words or [], open_close or {})

    def configure(self, words=None, open_close=None):
        """Attach completion catalog and opener/closer map (safe to call twice)."""
        if words is not None:
            self._all_completions = list(words)
        if open_close is not None:
            self.open_close = dict(open_close)

        if self.completer is None:
            self.completer = QCompleter(self._all_completions, self)
            self.completer.setWidget(self)
            self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
            self.completer.activated.connect(self.insert_completion)
            self.completer.popup().installEventFilter(self)
            self.document().contentsChange.connect(self._on_contents_change)
            self.setTabChangesFocus(False)
        else:
            self.completer.setModel(QStringListModel(self._all_completions, self.completer))

        self._configured = True

    def _make_mark(self, pos: int, keep_on_insert: bool) -> QTextCursor:
        c = QTextCursor(self.document())
        c.setPosition(pos)
        c.setKeepPositionOnInsert(keep_on_insert)
        return c

    def _span_cursor(self, start: int, end: int) -> QTextCursor:
        c = QTextCursor(self.document())
        c.setPosition(start)
        c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        return c

    def register_pair(self, opener_start: int, opener_text: str,
                      closer_start: int, closer_text: str):
        oe = opener_start + len(opener_text)
        ce = closer_start + len(closer_text)
        pair = TokenPair(
            opener_left=self._make_mark(opener_start, False),
            opener_right=self._make_mark(oe, True),
            closer_left=self._make_mark(closer_start, False),
            closer_right=self._make_mark(ce, True),
            opener_expected=opener_text,
            closer_expected=closer_text,
            dim_mark=self._make_mark(ce, True),
        )
        self.pairs.append(pair)
        self._refresh_highlights()

    def _solidify_closer(self, pair: TokenPair):
        """Fully commit the closer visually (no dim) but *keep tracking* it.

        Closers remain semi-atomic for life; only opener damage retracts them.
        """
        _ca, cb = pair.closer_span()
        pair.dim_mark = self._make_mark(cb, True)
        self._refresh_highlights()

    def _retract_pair(self, pair: TokenPair):
        if pair in self.pairs:
            self.pairs.remove(pair)
        self._guard = True
        try:
            a, b = pair.closer_span()
            text = self.toPlainText()
            if 0 <= a < b <= len(text):
                self._span_cursor(a, b).removeSelectedText()
        finally:
            self._guard = False
        self._refresh_highlights()

    def _refresh_highlights(self):
        sels = []
        for pair in self.pairs:
            oa, ob = pair.opener_span()
            if ob > oa:
                sel = _ExtraSelection()
                sel.cursor = self._span_cursor(oa, ob)
                sel.format = self._fmt_opener
                sels.append(sel)
            ca, cb = pair.closer_span()
            dim = max(ca, min(pair.dim_from(), cb))
            if dim > ca:
                sel = _ExtraSelection()
                sel.cursor = self._span_cursor(ca, dim)
                sel.format = self._fmt_closer
                sels.append(sel)
            if cb > dim:
                sel = _ExtraSelection()
                sel.cursor = self._span_cursor(dim, cb)
                sel.format = self._fmt_dim
                sels.append(sel)
        self.setExtraSelections(sels)

    def _on_contents_change(self, position, removed, added):
        if self._guard or not self.pairs:
            return
        text = self.toPlainText()
        doomed = [p for p in self.pairs if p.opener_text(text) != p.opener_expected]
        for p in doomed:
            self._retract_pair(p)
        if not doomed:
            self._refresh_highlights()

    def insert_opener_with_closer(self, opener, closer, replace_start=None, replace_end=None):
        self._guard = True
        try:
            cursor = self.textCursor()
            if replace_start is not None and replace_end is not None:
                cursor.setPosition(replace_start)
                cursor.setPosition(replace_end, QTextCursor.MoveMode.KeepAnchor)
            opener_start = cursor.selectionStart() if cursor.hasSelection() else cursor.position()
            cursor.insertText(opener)
            opener_end = opener_start + len(opener)
            closer_start = opener_end
            cursor.setPosition(closer_start)
            cursor.insertText(closer)
            if closer.startswith("{}"):
                cursor.setPosition(closer_start + 1)
            else:
                cursor.setPosition(closer_start)
            self.setTextCursor(cursor)
        finally:
            self._guard = False
        self.register_pair(opener_start, opener, closer_start, closer)

    def _pair_at_closer(self, pos: int) -> TokenPair | None:
        for p in self.pairs:
            a, b = p.closer_span()
            if a <= pos < b or (pos == b and a < b):
                return p
        return None

    def try_atomic_backspace(self) -> bool:
        cursor = self.textCursor()
        if cursor.hasSelection():
            return False
        pos = cursor.position()
        pair = self._pair_at_closer(pos - 1) if pos > 0 else None
        if pair is None:
            pair = self._pair_at_closer(pos)
        if pair is None:
            return False

        ca, cb = pair.closer_span()
        if not (ca < pos <= cb):
            return False

        new_pos = max(ca, pos - 1)
        closer_text = self.toPlainText()[ca:cb]
        delim = right_delim_of(pair.closer_expected)

        if is_right_closer(pair.closer_expected):
            delim_start = cb - len(delim)
        else:
            delim_start = cb - 1
        if delim_start < ca:
            delim_start = ca

        # Stepping onto/over delimiter (and not already .) → rewrite to .
        if (
            is_right_closer(pair.closer_expected)
            and delim != "."
            and new_pos >= delim_start
            and new_pos < cb
        ):
            self._guard = True
            try:
                self._span_cursor(delim_start, cb).insertText(".")
                pair.closer_expected = with_right_delim(pair.closer_expected, ".")
                pair.closer_right = self._make_mark(delim_start + 1, True)
                cb = delim_start + 1
            finally:
                self._guard = False
            new_pos = min(new_pos, cb)

        pair.dim_mark = self._make_mark(new_pos, True)
        cursor.setPosition(new_pos)
        self.setTextCursor(cursor)
        self._refresh_highlights()
        self.show_completions()
        return True

    def _delim_start(self, pair: TokenPair) -> int:
        """Document offset of the fence glyph after ``\\right`` (or last char)."""
        ca, cb = pair.closer_span()
        if is_right_closer(pair.closer_expected):
            delim = right_delim_of(pair.closer_expected)
            return max(ca, cb - len(delim))
        return max(ca, cb - 1)

    @staticmethod
    def _delim_lcp(candidates: list[str]) -> str:
        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]
        first = candidates[0]
        i = 0
        while i < len(first) and all(
            i < len(c) and c[i] == first[i] for c in candidates
        ):
            i += 1
        return first[:i]

    def _apply_delim(
        self,
        pair: TokenPair,
        new_delim: str,
        caret_in_delim: int | None = None,
    ):
        """Rewrite the delimiter of a ``\\right…`` closer in place.

        *caret_in_delim* = offset within *new_delim* for the caret.  Default is
        end of delim (fully committed).  When partially typed, pass the typed
        length so the remainder stays dimmed (valid tentative fence).
        """
        ca, _cb = pair.closer_span()
        body = r"\right"
        new_closer = body + new_delim
        self._guard = True
        try:
            self._span_cursor(ca, pair.closer_span()[1]).insertText(new_closer)
            end = ca + len(new_closer)
            pair.closer_expected = new_closer
            pair.closer_left = self._make_mark(ca, False)
            pair.closer_right = self._make_mark(end, True)
            if caret_in_delim is None:
                caret = end
            else:
                caret = ca + len(body) + min(caret_in_delim, len(new_delim))
            # Dim uncommitted delim suffix (and keep dim_mark at caret)
            pair.dim_mark = self._make_mark(caret, True)
            cursor = self.textCursor()
            cursor.setPosition(caret)
            self.setTextCursor(cursor)
        finally:
            self._guard = False
        self._refresh_highlights()
        self.show_completions()

    def _tentative_delim(self, typed_prefix: str) -> str | None:
        """A *complete* delimiter for *typed_prefix*, or None if invalid.

        Unique match expands fully (``\\ra`` → ``\\rangle``).  Several matches
        still pick a full preferred fence (e.g. ``\\`` → ``\\rangle``) so the
        buffer never holds an incomplete stem like ``\\right\\`` alone.
        """
        candidates = [
            d for d in LEFT_RIGHT_DELIMS if d.startswith(typed_prefix)
        ]
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        for pref in PREFERRED_CMD_DELIMS:
            if pref in candidates:
                return pref
        # Fallback: first catalog entry that matches (always a full delim)
        return candidates[0]

    def _try_mutate_delim_key(self, pair: TokenPair, typed: str) -> bool:
        """Change the fence of ``\\right…`` in place — never bump the closer out.

        Partial command fences always expand to a *valid* tentative delimiter
        (dimmed suffix).  Keys that match no fence are ignored (beep).
        """
        if not is_right_closer(pair.closer_expected):
            return False

        pos = self.textCursor().position()
        ca, cb = pair.closer_span()
        delim_start = self._delim_start(pair)
        if not (ca <= pos <= cb):
            return False

        old_delim = right_delim_of(pair.closer_expected)
        off = max(0, pos - delim_start) if pos >= delim_start else 0
        on_fence = pos >= delim_start

        if typed == "\\" and on_fence:
            tentative = self._tentative_delim("\\")
            if tentative is None:
                QApplication.beep()
                return True
            self._apply_delim(pair, tentative, caret_in_delim=1)
            return True

        if (
            on_fence
            and old_delim.startswith("\\")
            and (typed.isalpha() or typed in "{}")
        ):
            # Typed prefix = stem before caret + new char (ignore dimmed tail)
            kept = old_delim[:off] if off <= len(old_delim) else old_delim
            if pos >= cb:
                kept = old_delim
            # If previous tentative was full \rangle and caret mid-way, kept is
            # the committed prefix only (off tracks caret in delim).
            typed_prefix = kept + typed
            tentative = self._tentative_delim(typed_prefix)
            if tentative is None:
                QApplication.beep()
                return True  # consume key; do not insert / push
            self._apply_delim(
                pair, tentative, caret_in_delim=len(typed_prefix)
            )
            return True

        if not on_fence:
            return False
        simple = {"(", ")", "[", "]", "|", ".", "{", "}"}
        if typed not in simple:
            # On a simple fence, non-fence keys are not delimiter mutation
            return False
        delim = r"\{" if typed == "{" else (r"\}" if typed == "}" else typed)
        if r"\right" + delim == pair.closer_expected:
            return False
        self._apply_delim(pair, delim, caret_in_delim=None)
        return True

    def try_type_through_or_abandon(self, typed: str) -> bool:
        cursor = self.textCursor()
        pos = cursor.position()
        pair = self._pair_at_closer(pos)
        if pair is None:
            return False

        ca, cb = pair.closer_span()
        dim = max(ca, min(pair.dim_from(), cb))
        text = self.toPlainText()

        # Fence mutation only on the delimiter glyph (not at content edge).
        if is_right_closer(pair.closer_expected):
            if self._try_mutate_delim_key(pair, typed):
                return True

        def _fold_to(new_pos: int):
            pair.dim_mark = self._make_mark(new_pos, True)
            cursor.setPosition(new_pos)
            self.setTextCursor(cursor)
            self._refresh_highlights()
            self.show_completions()

        # --- Fold into closer from the content edge ---
        # \left(x| \right)  + "\"  →  \left(x\|right)   (caret inside closer)
        # then + "r"        →  \left(x\r|ight)
        # then + "m"        →  \left(x\rm|\right)  (abandon / push)
        #
        # Exception: \} \{ \| are literal symbols, not group boundaries.
        # a^{|} + \ + } → a^{\}|}  (content + still-open closer), not a^{\}|.
        if pos == ca and ca < cb and text[ca] == typed:
            if typed in "{}|" and pos > 0 and text[pos - 1] == "\\":
                return False  # normal insert before the closer
            _fold_to(ca + 1)
            return True

        # Caret at dim boundary inside closer (after folding or backspace)
        if pos == dim and ca < dim < cb:
            next_ch = text[dim]
            if typed == next_ch:
                _fold_to(dim + 1)
                return True

            # Abandon: typed breaks the closer prefix (e.g. \r + m)
            self._guard = True
            try:
                c = QTextCursor(self.document())
                c.setPosition(dim)
                c.insertText(typed)
                caret = dim + len(typed)
                ca2, cb2 = pair.closer_span()
                end = max(cb2, caret)
                self._span_cursor(caret, end).insertText(pair.closer_expected)
                new_ca = caret
                new_cb = caret + len(pair.closer_expected)
                pair.closer_left = self._make_mark(new_ca, False)
                pair.closer_right = self._make_mark(new_cb, True)
                pair.dim_mark = self._make_mark(new_cb, True)
                cursor.setPosition(caret)
                self.setTextCursor(cursor)
            finally:
                self._guard = False
            self._refresh_highlights()
            self.show_completions()
            return True

        # Type-through when already inside a solid closer (pos > ca)
        if ca < pos < cb and text[pos] == typed:
            if typed in "{}|" and text[pos - 1] == "\\":
                return False
            _fold_to(pos + 1)
            return True

        return False

    def try_fold_after_delete(self) -> bool:
        cursor = self.textCursor()
        pos = cursor.position()
        text = self.toPlainText()
        before = text[:pos]
        for pair in list(self.pairs):
            ca, cb = pair.closer_span()
            if ca != pos:
                continue
            expected = pair.closer_expected
            best = 0
            for n in range(1, len(expected) + 1):
                if before.endswith(expected[:n]):
                    best = n
            if best == 0:
                continue
            absorb_start = pos - best
            self._guard = True
            try:
                self._span_cursor(absorb_start, pos).removeSelectedText()
                pair.closer_left = self._make_mark(absorb_start, False)
                pair.closer_right = self._make_mark(absorb_start + len(expected), True)
                pair.dim_mark = self._make_mark(absorb_start + best, True)
                cursor.setPosition(absorb_start + best)
                self.setTextCursor(cursor)
            finally:
                self._guard = False
            self._refresh_highlights()
            self.show_completions()
            return True
        return False

    def mutate_closer(self, pair: TokenPair, new_closer: str):
        ca, cb = pair.closer_span()
        self._guard = True
        try:
            self._span_cursor(ca, cb).insertText(new_closer)
            end = ca + len(new_closer)
            pair.closer_expected = new_closer
            pair.closer_left = self._make_mark(ca, False)
            pair.closer_right = self._make_mark(end, True)
            pair.dim_mark = self._make_mark(end, True)
            # Land after the closer so editing continues past the pair
            cursor = self.textCursor()
            cursor.setPosition(end)
            self.setTextCursor(cursor)
        finally:
            self._guard = False
        self._refresh_highlights()

    def latex_prefix(self) -> str:
        """Command-ish text left of the caret used as the completion prefix.

        Special case: ``\\left`` / ``\\right`` may be followed by a delimiter
        that is itself a command (``\\langle``, ``\\{``, …).  The naive
        ``\\\\[A-Za-z]*$`` pattern would only see the *last* ``\\l…`` and treat
        it as a new command — so ``\\left\\l`` would look like ``\\l`` and
        ``\\left\\langle`` would never rank correctly.
        """
        cursor = self.textCursor()
        text = cursor.block().text()
        position = cursor.positionInBlock()
        before = text[:position]

        m = re.search(r"\\(?:begin|end)\{[A-Za-z]*$", before)
        if m:
            return m.group(0)

        # \left\langle / \left\l / \left\{ / \left\| / \left( / \left
        for pat in (
            r"\\(?:left|right)\\[A-Za-z]*$",   # \left\lang …
            r"\\(?:left|right)\\[{}]$",        # \left\{  \left\}
            r"\\(?:left|right)\\\|$",          # \left\|
            r"\\(?:left|right)[()\[\]|.]$",    # \left(  \left|
            r"\\(?:left|right)$",              # \left  \right
        ):
            m = re.search(pat, before)
            if m:
                return m.group(0)

        m = re.search(r"\\[A-Za-z]*$", before)
        return m.group(0) if m else ""

    def _in_closer_fence(self, pair: TokenPair | None, pos: int) -> bool:
        """True only when caret is *inside* a closer (not the content edge).

        At the start of ``\\right…`` the user is still typing interior content
        (e.g. ``\\partial``); closer-substitute mode must not steal that.
        """
        if pair is None or not is_right_closer(pair.closer_expected):
            return False
        ca, cb = pair.closer_span()
        return ca < pos <= cb

    def matching_completions(self, prefix: str) -> list[str]:
        pos = self.textCursor().position()
        pair = self._pair_at_closer(pos)
        # Fence / mid-closer only — not the interior edge at ca
        if self._in_closer_fence(pair, pos):
            ranked = closer_substitutes(pair.closer_expected)
            if not prefix:
                return ranked
            pl = prefix.lower()
            return [c for c in ranked if c.lower().startswith(pl)]
        if not prefix:
            return []
        pl = prefix.lower()
        matches = [w for w in self._all_completions if w.lower().startswith(pl)]

        # After \left / \right, prefer delimiter forms (including \langle)
        if re.match(r"\\(?:left|right)", prefix, re.I):
            matches.sort(
                key=lambda w: (
                    0 if w.lower().startswith(prefix.lower()) else 1,
                    0 if w.lower().startswith(r"\left") or w.lower().startswith(r"\right") else 1,
                    len(w),
                    w.lower(),
                )
            )
        return matches

    def show_completions(self):
        prefix = self.latex_prefix()
        pos = self.textCursor().position()
        pair = self._pair_at_closer(pos)
        if not prefix and not self._in_closer_fence(pair, pos):
            self.completer.popup().hide()
            return
        matches = self.matching_completions(prefix)
        if not matches:
            self.completer.popup().hide()
            return
        if len(matches) == 1 and prefix and matches[0].lower() == prefix.lower():
            self.completer.popup().hide()
            return
        self.completer.setModel(QStringListModel(matches, self.completer))
        self.completer.setCompletionPrefix("")
        popup = self.completer.popup()
        popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
        rect = self.cursorRect()
        rect.setWidth(
            popup.sizeHintForColumn(0)
            + popup.verticalScrollBar().sizeHint().width()
            + 8
        )
        self.completer.complete(rect)

    def replace_prefix(self, prefix: str, new_text: str):
        cursor = self.textCursor()
        end = cursor.position()
        start = end - len(prefix)
        self._guard = True
        try:
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(new_text)
            self.setTextCursor(cursor)
        finally:
            self._guard = False

    def insert_completion(self, completion: str):
        if not completion:
            return
        pos = self.textCursor().position()
        pair = self._pair_at_closer(pos)
        # Also treat caret just after closer as "on closer" for mutation
        if pair is None and pos > 0:
            pair = self._pair_at_closer(pos - 1)
        if pair and is_right_closer(completion):
            self.mutate_closer(pair, completion)
            self.completer.popup().hide()
            return
        prefix = self.latex_prefix()
        if not prefix:
            return
        end = self.textCursor().position()
        start = end - len(prefix)
        closer = self.open_close.get(completion)
        if closer is not None:
            self.insert_opener_with_closer(completion, closer, start, end)
        else:
            self.replace_prefix(prefix, completion)
        self.completer.popup().hide()

    def tab_complete(self) -> bool:
        """Bash-style Tab: unique accept, else LCP; on closer popup accept highlight.

        Never cycles the list — use Up/Down for that.  Tab on an idle closer
        (no popup) jumps past while keeping the pair tracked.
        """
        prefix = self.latex_prefix()
        pos = self.textCursor().position()
        pair = self._pair_at_closer(pos)
        popup = self.completer.popup()
        popup_open = popup is not None and popup.isVisible()

        matches = self.matching_completions(prefix) if (prefix or pair) else []

        # Closer + popup: Tab accepts the *highlighted* row (same as Enter/click)
        if (
            popup_open
            and pair is not None
            and is_right_closer(pair.closer_expected)
        ):
            if self.activate_current_completion():
                return True

        if matches:
            if len(matches) == 1:
                self.insert_completion(matches[0])
                return True
            low = [s.lower() for s in matches]
            first = low[0]
            i = 0
            while i < len(first) and all(
                i < len(s) and s[i] == first[i] for s in low
            ):
                i += 1
            lcp = matches[0][:i]
            if prefix and len(lcp) > len(prefix):
                # Do not splice LCP into the middle of a solid closer token
                if pair is not None and is_right_closer(pair.closer_expected):
                    self.show_completions()
                    return True
                self.replace_prefix(prefix, lcp)
                self.show_completions()
                return True
            self.show_completions()
            return True

        # Idle closer: jump past (still tracked)
        if pair is not None:
            ca, cb = pair.closer_span()
            if ca <= pos <= cb:
                self._solidify_closer(pair)
                cursor = self.textCursor()
                cursor.setPosition(cb)
                self.setTextCursor(cursor)
                self.completer.popup().hide()
                return True
        return False

    def activate_current_completion(self) -> bool:
        popup = self.completer.popup()
        model = self.completer.completionModel()
        if model is None or model.rowCount() == 0:
            return False
        idx = popup.currentIndex()
        if not idx.isValid():
            idx = model.index(0, 0)
        completion = model.data(idx, Qt.ItemDataRole.DisplayRole)
        if not completion:
            return False
        self.insert_completion(str(completion))
        return True

    def _backslash_run_before(self, pos: int) -> int:
        """Count consecutive ``\\`` characters immediately before *pos*."""
        text = self.toPlainText()
        n = 0
        i = pos - 1
        while i >= 0 and text[i] == "\\":
            n += 1
            i -= 1
        return n

    def _brace_opens_group_at_cursor(self) -> bool:
        """TeX rule: ``{`` opens a group only after an *even* backslash run.

        ``{`` / ``\\\\{`` → group; ``\\{`` / ``\\\\\\{`` → literal brace token.
        """
        pos = self.textCursor().position()
        return self._backslash_run_before(pos) % 2 == 0

    def try_typed_opener(self, typed: str) -> bool:
        if len(typed) != 1:
            return False
        closer = self.open_close.get(typed)
        if closer is None:
            return False
        # Do not pair-close \{  (odd backslashes) — only real groups
        if typed == "{" and not self._brace_opens_group_at_cursor():
            return False
        self.insert_opener_with_closer(typed, closer)
        return True

    def try_finish_typed_opener(self) -> bool:
        cursor = self.textCursor()
        pos = cursor.position()
        before = self.toPlainText()[:pos]
        candidates = [(op, cl) for op, cl in self.open_close.items() if len(op) > 1]
        candidates.sort(key=lambda x: -len(x[0]))
        for opener, closer in candidates:
            if not before.endswith(opener):
                continue
            opener_start = pos - len(opener)
            if any(p.opener_right.position() == pos for p in self.pairs):
                return False
            text = self.toPlainText()
            if text[pos: pos + len(closer)] == closer:
                return False
            self._guard = True
            try:
                cursor.setPosition(pos)
                cursor.insertText(closer)
                if closer.startswith("{}"):
                    cursor.setPosition(pos + 1)
                else:
                    cursor.setPosition(pos)
                self.setTextCursor(cursor)
            finally:
                self._guard = False
            self.register_pair(opener_start, opener, pos, closer)
            return True
        return False

    def eventFilter(self, obj, event):
        completer = getattr(self, "completer", None)
        if completer is None:
            return super().eventFilter(obj, event)
        if obj is completer.popup() and event.type() == event.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                if self.tab_complete():
                    return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.activate_current_completion():
                    return True
            if key == Qt.Key.Key_Escape:
                completer.popup().hide()
                self.setFocus()
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        popup = self.completer.popup()
        key = event.key()
        popup_visible = popup is not None and popup.isVisible()

        if popup_visible:
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down,
                       Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                QApplication.sendEvent(popup, event)
                return
            if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                if self.tab_complete():
                    return
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.activate_current_completion():
                    return
            if key == Qt.Key.Key_Escape:
                popup.hide()
                return

        if key == Qt.Key.Key_Space and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.show_completions()
            return

        if key == Qt.Key.Key_Tab:
            if self.tab_complete():
                return
            return

        if key == Qt.Key.Key_Backspace:
            if self.try_atomic_backspace():
                return
            super().keyPressEvent(event)
            self.try_fold_after_delete()
            self.show_completions()
            return

        typed = event.text()
        if typed and self.try_type_through_or_abandon(typed):
            return
        if typed and self.try_typed_opener(typed):
            self.show_completions()
            return

        super().keyPressEvent(event)
        self.try_finish_typed_opener()
        self.show_completions()


def default_completion_words(extra=None) -> list:
    """Catalog used by the completer; *extra* is merged (e.g. MATHJAX_COMMANDS)."""
    words = list(COMPLETIONS)
    if extra:
        seen = set(words)
        for w in extra:
            if w not in seen:
                words.append(w)
                seen.add(w)
    return words
