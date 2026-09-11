from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from typing import NamedTuple, Optional
from enum import StrEnum, auto
from dataclasses import dataclass, field
import re

mathjax_grammar_def = r'''
expr = (triode / diode / monode / env_node)*
sub = subscript monode
subscript = "_"
power = superscript monode
superscript = "^"
triode = (node sub power) / (node power sub)
diode = (node power) / (node sub)
node = monode / env_node
monode = null ((token) / ("{" null expr null  "}") / (left_bkt null expr null right_bkt)) null
env_node = null "\\begin ws {" environment "}" expr "\\end ws {" environment "}" null
left_bkt = "\\left" ws bkt_delim
right_bkt = "\\right" ws bkt_delim
bkt_delim = "(" / ")" / "[" / "]" / "\\{" / "\\}" / "|" / "."
environment = "bmatrix" / "matrix" / "align"
command = "\\" (letter+ / "\\" / " " / "%" / "#" / "&" / "_" / "{" / "}")
token = variable / symbols / digit / command
variable = ~"[A-Za-z]"
letter = ~"[A-Za-z]"
symbols = "+" / "-" / "*" / "/" / "=" / "(" / ")" / "[" / "]" / "|" / "`" / "$" / "'" / "," / "." / ":" / ";" / "@" / "?"
digit = "0" / "1" / "2" / "3" / "4" / "5" / "6" / "7" / "8" / "9"
null = (comment / ws)*
ws = ~"[ \\t\\n\\r]*"
comment = ~r"%[^\r\n]*"
'''


class MathJaxVisitorTest(NodeVisitor):
    grammar = Grammar(mathjax_grammar_def)
    def __init__(self):
        super().__init__()

    def set_command(self, command):
        self.command = command

    def visit_expr(self, node, visited_children):
        """ Returns the overall output. """
        print('visit_expr: called:')
        return ('##EXPR##', node.text, '##EXPR##',)

    def visit_node(self, node, visited_children):
        """ Returns the node output. """
        print('')
        if len(visited_children) >= 3:
            _, expr, *_ = visited_children
        elif len(visited_children) > 0:
            expr, *_ = visited_children
        else:
            expr = None
        pass
        return ('[***NODE***]', expr, '[***NODE***]')

    def visit_command(self, node, visited_children):
        backslash, command, *_ = visited_children
        pass
        return ('[***NODE***]', command, '[***NODE***]')

    def visit_variable(self, node, visited_children):
        print("visit_variable: called")
        pass
        return node.text

    def visit_letter(self, node, visited_children):
        print("visit_letter: called")
        pass
        return node.text

    def generic_visit(self, node, visited_children):
        """ The generic visit method. """
        return visited_children or node

    def visit(self, node):
        pass
        return super().visit(node)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class MJTokenType(StrEnum):
    COMMENT = auto()
    COMMAND = auto()
    STARTGROUP = auto()
    ENDGROUP = auto()
    DIGIT = auto()
    SUPERSCRIPT = auto()
    SUBSCRIPT = auto()
    VARIABLE = auto()
    SYMBOL = auto()
    NEWLINE = auto()
    SKIP = auto()
    MISMATCH = auto()


class Token(NamedTuple):
    type: MJTokenType
    text: str
    line: int
    pos: int  # absolute document offset


def tokenize(code: str, ignore_mismatch: bool = False):
    """Yield tokens with absolute document positions and correct line numbers.

    Positions are offsets into *code* (0-based). Line numbers are 1-based.
    """
    token_spec = (
        (MJTokenType.COMMENT,      r'%[^\n]*\n?'),                    # Comment
        (MJTokenType.COMMAND,      r'\\(?:[A-Za-z]+|[ %#&_{}\\$])'),  # Command
        (MJTokenType.STARTGROUP,   r'\{'),                            # Group left delimiter
        (MJTokenType.ENDGROUP,     r'\}'),                            # Group right delimiter
        (MJTokenType.DIGIT,        r'\d'),                            # Decimal digit
        (MJTokenType.SUPERSCRIPT,  r'\^'),                            # Superscript/Power
        (MJTokenType.SUBSCRIPT,    r'_'),                             # Subscript
        (MJTokenType.VARIABLE,     r'[A-Za-z]'),                      # Identifiers
        (MJTokenType.SYMBOL,       r'[+\-*\/=()\[\]|`\$\',.:;@?]'),   # Symbols
        (MJTokenType.NEWLINE,      r'\n'),                            # Line endings
        (MJTokenType.SKIP,         r'[ \t]+'),                        # Spaces and tabs
        (MJTokenType.MISMATCH,     r'(?:\\.)|.'),                     # Any other character
    )
    tok_regex = '|'.join(f'(?P<{kind}>{regex})' for (kind, regex) in token_spec)
    line_num = 1
    for match in re.finditer(tok_regex, code):
        kind = MJTokenType(match.lastgroup)
        value = match.group()
        pos = match.start()  # absolute document offset
        if kind == MJTokenType.MISMATCH and not ignore_mismatch:
            raise RuntimeError(f'{value!r} unexpected on line {line_num}')
        yield Token(kind, value, line_num, pos)
        if kind == MJTokenType.NEWLINE or (kind == MJTokenType.COMMENT and value.endswith('\n')):
            line_num += 1


# ---------------------------------------------------------------------------
# Bracket / delimiter matching
# ---------------------------------------------------------------------------

# Delimiters that may follow \left / \right / \middle
_LEFT_RIGHT_DELIMS = frozenset({
    '(', ')', '[', ']', '|', '.',
    r'\{', r'\}', r'\|',
})

# Map of opener text -> expected closer text for simple pairs
_SIMPLE_OPEN_CLOSE = {
    '{': '}',
    '[': ']',
    '(': ')',
}

# Commands that open a left/right pair
_LEFT_CMDS = frozenset({r'\left', r'\bigl', r'\Bigl', r'\biggl', r'\Biggl'})
_RIGHT_CMDS = frozenset({r'\right', r'\bigr', r'\Bigr', r'\biggr', r'\Biggr'})


def _is_left_cmd(text: str) -> bool:
    return text in _LEFT_CMDS


def _is_right_cmd(text: str) -> bool:
    return text in _RIGHT_CMDS


def gen_bracket_match_map(token_list, ignore_unmatched=True):
    """Pair matching open/close tokens.

    Handles:
      - { } groups
      - ( ) [ ] simple brackets
      - \\left ... \\right  (matched by command, not by the following delimiter)
      - \\begin ... \\end

    Returns dict Token -> matching Token (bidirectional).
    """
    bracket_map = {}

    # Stacks keyed by the "open" side we push
    group_stack = []          # {
    paren_stack = []          # (
    bracket_stack = []        # [
    left_stack = []           # \left / \bigl / ...
    begin_stack = []          # \begin

    for token in token_list:
        t = token.text

        if t == '{':
            group_stack.append(token)
        elif t == '}':
            if group_stack:
                open_tok = group_stack.pop()
                bracket_map[token] = open_tok
                bracket_map[open_tok] = token
            elif not ignore_unmatched:
                raise RuntimeError('Unmatched }', token)

        elif t == '(':
            paren_stack.append(token)
        elif t == ')':
            if paren_stack:
                open_tok = paren_stack.pop()
                bracket_map[token] = open_tok
                bracket_map[open_tok] = token
            elif not ignore_unmatched:
                raise RuntimeError('Unmatched )', token)

        elif t == '[':
            bracket_stack.append(token)
        elif t == ']':
            if bracket_stack:
                open_tok = bracket_stack.pop()
                bracket_map[token] = open_tok
                bracket_map[open_tok] = token
            elif not ignore_unmatched:
                raise RuntimeError('Unmatched ]', token)

        elif _is_left_cmd(t):
            left_stack.append(token)
        elif _is_right_cmd(t):
            if left_stack:
                open_tok = left_stack.pop()
                bracket_map[token] = open_tok
                bracket_map[open_tok] = token
            elif not ignore_unmatched:
                raise RuntimeError('Unmatched \\right', token)

        elif t == r'\begin':
            begin_stack.append(token)
        elif t == r'\end':
            if begin_stack:
                open_tok = begin_stack.pop()
                bracket_map[token] = open_tok
                bracket_map[open_tok] = token
            elif not ignore_unmatched:
                raise RuntimeError('Unmatched \\end', token)

    return bracket_map


# ---------------------------------------------------------------------------
# Structural model for completion / auto-close
# ---------------------------------------------------------------------------

class OpenKind(StrEnum):
    GROUP = auto()          # {
    LEFT_RIGHT = auto()     # \left ... \right
    ENV = auto()            # \begin{...} ... \end{...}
    PAREN = auto()          # (
    BRACKET = auto()        # [
    COMMAND_ARG = auto()    # expected { after a multi-arg command
    SUP_SUB = auto()        # after ^ or _


@dataclass
class OpenContext:
    kind: OpenKind
    open_token: Token
    expected_close: str           # text that should close this context
    delimiter: Optional[str] = None  # e.g. '(' for \left(
    env_name: Optional[str] = None   # for \begin{matrix}
    arg_index: Optional[int] = None  # for multi-arg commands (0-based)


@dataclass
class Structure:
    tokens: list[Token]
    pairs: dict                 # Token -> Token
    open_stack: list[OpenContext] = field(default_factory=list)
    # tokens that are still open at the end of the (prefix of the) document
    unmatched_opens: list[Token] = field(default_factory=list)


# Commands that take N braced arguments. Used for auto-insert of {} placeholders.
COMMAND_ARITY = {
    r'\frac': 2,
    r'\dfrac': 2,
    r'\tfrac': 2,
    r'\binom': 2,
    r'\dbinom': 2,
    r'\sqrt': 1,          # optional [] handled separately; we only auto-close the {}
    r'\overline': 1,
    r'\underline': 1,
    r'\mathbf': 1,
    r'\mathrm': 1,
    r'\mathit': 1,
    r'\mathsf': 1,
    r'\mathtt': 1,
    r'\mathbb': 1,
    r'\mathcal': 1,
    r'\mathfrak': 1,
    r'\text': 1,
    r'\textrm': 1,
    r'\textbf': 1,
    r'\textit': 1,
    r'\operatorname': 1,
    r'\overset': 2,
    r'\underset': 2,
}


def _peek_env_name(tokens: list[Token], start_index: int) -> Optional[str]:
    """If tokens[start_index] is '{', collect letters until '}' and return the name."""
    if start_index >= len(tokens) or tokens[start_index].type != MJTokenType.STARTGROUP:
        return None
    name_chars = []
    i = start_index + 1
    while i < len(tokens) and tokens[i].type == MJTokenType.VARIABLE:
        name_chars.append(tokens[i].text)
        i += 1
    if i < len(tokens) and tokens[i].type == MJTokenType.ENDGROUP:
        return ''.join(name_chars) or None
    return None


def _peek_left_delim(tokens: list[Token], start_index: int) -> Optional[str]:
    """Return the delimiter character/token that follows a \\left-family command."""
    if start_index >= len(tokens):
        return None
    tok = tokens[start_index]
    if tok.type in (MJTokenType.SYMBOL, MJTokenType.COMMAND) and tok.text in _LEFT_RIGHT_DELIMS:
        return tok.text
    return None


def _is_delim_of_left_cmd(tokens: list[Token], index: int) -> bool:
    """True if tokens[index] is the delimiter that immediately follows a \\left-family cmd."""
    if index <= 0:
        return False
    prev = tokens[index - 1]
    if not _is_left_cmd(prev.text):
        return False
    tok = tokens[index]
    return tok.type in (MJTokenType.SYMBOL, MJTokenType.COMMAND) and tok.text in _LEFT_RIGHT_DELIMS


def build_structure(tokens: list[Token], up_to_pos: Optional[int] = None) -> Structure:
    """Walk tokens and build pair map + open stack.

    If *up_to_pos* is given, only consider tokens that start at or before that
    position (useful for "what is still open at the cursor").

    A delimiter that immediately follows ``\\left`` / ``\\bigl`` / etc. is *not*
    treated as a standalone paren/bracket; it belongs to the left-right pair.
    """
    if up_to_pos is not None:
        # Tokens that *start* at the cursor are still ahead of it (the cursor
        # sits before that character), so use strict < .
        relevant = [t for t in tokens if t.pos < up_to_pos]
    else:
        relevant = list(tokens)

    pairs = gen_bracket_match_map(relevant)
    open_stack: list[OpenContext] = []

    # Indices of delimiters that belong to a \left and must not open a PAREN/BRACKET
    left_delim_indices = set()
    for i, tok in enumerate(relevant):
        if _is_left_cmd(tok.text):
            if i + 1 < len(relevant) and _is_delim_of_left_cmd(relevant, i + 1):
                left_delim_indices.add(i + 1)

    i = 0
    while i < len(relevant):
        tok = relevant[i]
        t = tok.text
        matched = pairs.get(tok)

        def still_open() -> bool:
            return matched is None or (up_to_pos is not None and matched.pos > up_to_pos)

        if t == '{':
            if still_open():
                open_stack.append(OpenContext(
                    kind=OpenKind.GROUP,
                    open_token=tok,
                    expected_close='}',
                ))

        elif t == '(' and i not in left_delim_indices:
            if still_open():
                open_stack.append(OpenContext(
                    kind=OpenKind.PAREN,
                    open_token=tok,
                    expected_close=')',
                ))

        elif t == '[' and i not in left_delim_indices:
            if still_open():
                open_stack.append(OpenContext(
                    kind=OpenKind.BRACKET,
                    open_token=tok,
                    expected_close=']',
                ))

        elif _is_left_cmd(t):
            delim = _peek_left_delim(relevant, i + 1)
            if still_open():
                open_stack.append(OpenContext(
                    kind=OpenKind.LEFT_RIGHT,
                    open_token=tok,
                    expected_close=r'\right' + matching_right_delim(delim),
                    delimiter=delim,
                ))

        elif t == r'\begin':
            env = _peek_env_name(relevant, i + 1)
            if still_open():
                open_stack.append(OpenContext(
                    kind=OpenKind.ENV,
                    open_token=tok,
                    expected_close=r'\end{' + (env or '') + '}',
                    env_name=env,
                ))

        elif t in ('}', ')', ']') or _is_right_cmd(t) or t == r'\end':
            if open_stack and pairs.get(tok) is open_stack[-1].open_token:
                open_stack.pop()
            elif open_stack:
                for j in range(len(open_stack) - 1, -1, -1):
                    if pairs.get(tok) is open_stack[j].open_token:
                        del open_stack[j]
                        break

        i += 1

    unmatched = [ctx.open_token for ctx in open_stack]
    return Structure(
        tokens=relevant,
        pairs=pairs,
        open_stack=open_stack,
        unmatched_opens=unmatched,
    )


# ---------------------------------------------------------------------------
# Auto-close / completion helpers
# ---------------------------------------------------------------------------

def matching_right_delim(left_delim: Optional[str]) -> str:
    """Map a \\left delimiter to the usual \\right delimiter."""
    if left_delim is None:
        return ''
    table = {
        '(': ')',
        '[': ']',
        r'\{': r'\}',
        '|': '|',
        r'\|': r'\|',
        '.': '.',
        ')': '(',   # rare, but legal
        ']': '[',
        r'\}': r'\{',
    }
    return table.get(left_delim, left_delim)


@dataclass(frozen=True)
class AutoCloseResult:
    """What to insert after the typed character, and where to leave the cursor.

    *insert* is placed immediately after the just-typed character.
    *cursor_offset* is the number of characters into *insert* where the cursor
    should end up (0 = right before the inserted closer, i.e. between opener
    and closer).
    """
    insert: str
    cursor_offset: int = 0


def auto_close_for_text(just_typed: str, preceding_text: str = '') -> Optional[AutoCloseResult]:
    """Decide what closer (if any) to insert after *just_typed*.

    Returns an :class:`AutoCloseResult`, or ``None`` if nothing should be
    auto-inserted.  Cursor placement:

      '{' / '\\left(' / '\\begin{...}'  → offset 0  (between opener and closer)
      '^' / '_'                         → offset 1  (inside the ``{}``)
      '\\frac' / multi-arg commands     → offset 1  (inside the first ``{}``)
    """
    # Single-character triggers
    if just_typed == '{':
        return AutoCloseResult('}', cursor_offset=0)
    if just_typed in ('^', '_'):
        return AutoCloseResult('{}', cursor_offset=1)

    # Multi-character: look at a short window ending with just_typed
    window = (preceding_text + just_typed)[-20:]

    # \left + delimiter
    m = re.search(r'\\left\s*([(\[{|.]|\\[{}|])$', window)
    if m:
        delim = m.group(1)
        return AutoCloseResult(r'\right' + matching_right_delim(delim), cursor_offset=0)

    # \bigl / \Bigl / etc.
    m = re.search(r'\\([bB]igg?[lr])\s*([(\[{|.]|\\[{}|])$', window)
    if m:
        # map \bigl -> \bigr, \Bigl -> \Bigr, ...
        size = m.group(1)
        right_size = size[:-1] + 'r' if size.endswith('l') else size
        delim = m.group(2)
        return AutoCloseResult('\\' + right_size + matching_right_delim(delim), cursor_offset=0)

    # \begin{envname}
    m = re.search(r'\\begin\{([A-Za-z*]+)\}$', window)
    if m:
        env = m.group(1)
        return AutoCloseResult(r'\end{' + env + '}', cursor_offset=0)

    # Commands with known arity — insert braced argument slots
    m = re.search(r'(\\[A-Za-z]+)$', window)
    if m:
        cmd = m.group(1)
        arity = COMMAND_ARITY.get(cmd)
        if arity:
            # cursor inside the first {}
            return AutoCloseResult('{}' * arity, cursor_offset=1)

    return None


def expected_closers_at(tokens: list[Token], cursor_pos: int) -> list[str]:
    """Expected closer strings from innermost to outermost at *cursor_pos*."""
    structure = build_structure(tokens, up_to_pos=cursor_pos)
    return [ctx.expected_close for ctx in reversed(structure.open_stack)]


def text_after_matches(document_text: str, cursor_pos: int, candidate: str) -> bool:
    """True if *candidate* is exactly the text starting at *cursor_pos*."""
    if not candidate:
        return False
    return document_text.startswith(candidate, cursor_pos)


# Multi-char closers that may have been auto-inserted.  Used both for the
# start-of-closer check and for mid-closer continuation (type-through).
_MULTI_CLOSER_RE = re.compile(
    r'\\right[(\[{|.\)]?|'
    r'\\end\{[A-Za-z*]*\}?|'
    r'\\bigr[(\[{|.\)]?|'
    r'\\Bigr[(\[{|.\)]?|'
    r'\\biggr[(\[{|.\)]?|'
    r'\\Biggr[(\[{|.\)]?'
)


def skip_over_if_matches(document_text: str, cursor_pos: int, typed: str) -> Optional[int]:
    """If *typed* matches the text right after the cursor *and* the cursor is
    at the start of or inside an auto-inserted closer, return how many
    characters to advance; otherwise ``None``.

    Enables both:
      - typing ``}`` when ``}`` is already ahead → skip over it
      - typing ``\\right)`` character-by-character when it was auto-inserted
    """
    if not typed:
        return None
    rest = document_text[cursor_pos:]
    if not rest.startswith(typed):
        return None

    # Single-character closers
    if rest[0] in '})]':
        return len(typed)

    # Multi-character closer: allow type-through at the start *or* in the middle.
    # Look at a short window so we can detect that the cursor sits inside e.g.
    # ``\right)`` even after the leading ``\`` has already been skipped.
    lookback = 16
    window_start = max(0, cursor_pos - lookback)
    window = document_text[window_start: cursor_pos + 16]
    for m in _MULTI_CLOSER_RE.finditer(window):
        abs_start = window_start + m.start()
        abs_end = abs_start + len(m.group(0))
        if abs_start <= cursor_pos < abs_end:
            return len(typed)

    return None


@dataclass(frozen=True)
class TabAction:
    """Result of a Tab key at a given cursor position.

    *kind* is ``'skip'`` (move cursor forward by *n* chars) or ``'insert'``
    (insert *text* and then move past it / to *cursor_offset*).
    """
    kind: str                 # 'skip' | 'insert'
    text: str = ''            # for insert: the closer to insert
    n: int = 0                # for skip: how many chars to advance
    cursor_offset: int = 0    # for insert: where to leave cursor relative to text


def tab_action(document_text: str, cursor_pos: int) -> Optional[TabAction]:
    """Decide what Tab should do at *cursor_pos*.

    Priority:
      1. If we are sitting right before an empty ``{}`` argument slot that is
         followed by another ``{}``, jump into the next slot
         (``\\frac{|}{}`` → ``\\frac{}{|}``).
      2. If the innermost expected closer is already right after the cursor,
         skip over it.
      3. Otherwise insert the innermost expected closer and move past it.
      4. If nothing is open, do nothing (return ``None``).
    """
    # --- 1. Jump from one empty {} slot to the next (frac-style) ---
    # Pattern: cursor is just after '{', next chars are '}{'  → skip '}{' and
    # land inside the following group.  More generally: after '{...}|}{'
    # when the current group is empty or the cursor is at its end.
    rest = document_text[cursor_pos:]
    # Sitting at  \frac{|{}{}}  or  \frac{x|}{}  → advance to next group
    m = re.match(r'\}(\{\})', rest)
    if m:
        # move past '}' and the following '{', land inside next {}
        return TabAction(kind='skip', n=2)  # skip '}{'

    # --- 2 / 3. Structural closers ---
    tokens = list(tokenize(document_text, ignore_mismatch=True))
    closers = expected_closers_at(tokens, cursor_pos)
    if not closers:
        return None

    innermost = closers[0]

    # Already present right after cursor → skip over it
    if text_after_matches(document_text, cursor_pos, innermost):
        return TabAction(kind='skip', n=len(innermost))

    # Also accept skip if a leading single-char closer is present
    # (e.g. user is inside `{...|}` and Tab should jump over the `}`)
    if rest and rest[0] in '})]':
        # only if that char is a prefix of the expected closer, or is itself a closer
        if innermost.startswith(rest[0]) or rest[0] in '})]':
            return TabAction(kind='skip', n=1)

    # Insert the expected closer
    return TabAction(kind='insert', text=innermost, cursor_offset=len(innermost))


def suggest_completion_prefix(tokens: list[Token], cursor_pos: int) -> Optional[str]:
    """If the cursor is in the middle of a command, return the partial text
    for filtering a completion list.
    """
    candidates = [t for t in tokens if t.pos < cursor_pos]
    if not candidates:
        return None
    last = candidates[-1]
    end = last.pos + len(last.text)
    if last.type == MJTokenType.COMMAND and last.pos < cursor_pos <= end:
        return last.text[: cursor_pos - last.pos]
    return None


# ---------------------------------------------------------------------------
# Demo / self-test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    test_formula = r'''a + {a + b} \left( x \right)'''
    print('tokens for', repr(test_formula))
    toks = list(tokenize(test_formula, ignore_mismatch=True))
    for tok in toks:
        print(f'  {tok.type.name:12} {tok.text!r:20} line={tok.line} pos={tok.pos}')

    print('\npairs:')
    bm = gen_bracket_match_map(toks)
    seen = set()
    for k, v in bm.items():
        if id(k) not in seen:
            print(f'  {k.text!r}@{k.pos} <-> {v.text!r}@{v.pos}')
            seen.add(id(k))
            seen.add(id(v))

    print('\nstructure (full):')
    st = build_structure(toks)
    print('  open_stack:', [(c.kind, c.expected_close) for c in st.open_stack])

    print('\nauto_close examples:')
    for typed, prev in [
        ('{', 'a + '),
        ('(', r'\left'),
        ('[', r'\left'),
        (r'\{', r'\left'),
        ('}', r'\begin{matrix'),  # not a trigger
        ('x', r'\frac'),          # command just finished? window ends with \fracx — no
        ('c', r'\fra'),           # still typing
    ]:
        result = auto_close_for_text(typed, prev)
        print(f'  typed={typed!r} prev={prev!r} -> {result!r}')

    # Better command test: whole command typed at once is uncommon; simulate
    # the moment the last letter of \frac is typed.
    print('  typed="c" prev=r"\\fra" ->', auto_close_for_text('c', r'\fra'))
    print('  typed="c" prev=r"\\begin{matri" ->', auto_close_for_text('c', r'\begin{matri'))
    print('  typed="}" prev=r"\\begin{matrix" ->', auto_close_for_text('}', r'\begin{matrix'))
