import sys

# from PySide2 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import (QSyntaxHighlighter, QTextBlock, QTextCursor, QTextDocument,
                         QTextCharFormat, QColor, QFont)
from PyQt5.QtCore import QRegExp
from mjparse import mathjax_grammar_def, tokenize, MJTokenType, gen_bracket_match_map

from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor, Node
from parsimonious.exceptions import (ParseError, IncompleteParseError, VisitationError, UndefinedLabel, BadGrammar)
from bisect import bisect, bisect_left
from operator import attrgetter


def format(color='', style='', background='', underline_color='', underline_style=None,
           base: QTextCharFormat = None):
    """Return a QTextCharFormat with the given attributes."""

    _format = QTextCharFormat(base) if base else QTextCharFormat()
    _format.setUnderlineStyle(QTextCharFormat.WaveUnderline)

    if color:
        _color = QColor()
        _color.setNamedColor(color)
        _format.setForeground(_color)

    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)
    if background:
        _bg_color = QColor()
        _bg_color.setNamedColor(background)
        _format.setBackground(_bg_color)
    if underline_color:
        _ul_color = QColor()
        _ul_color.setNamedColor(underline_color)
        _format.setUnderlineColor(QColor(underline_color))
        _format.setUnderlineStyle(QTextCharFormat.SingleUnderline)
    if underline_style:
        _format.setUnderlineStyle(underline_style)

    return _format



# Syntax styles that can be shared by all languages
OLDSTYLES = {
    'keyword': format('blue'),
    'operator': format('red'),
    'brace': format('darkGray'),
    'defclass': format('black', 'bold'),
    'string': format('magenta'),
    'string2': format('darkMagenta'),
    'comment': format('darkGreen', 'italic'),
    'self': format('black', 'italic'),
    'numbers': format('brown'),
}

STYLES = {
    'keyword': format('darkcyan'),
    'defclass': format('black', 'bold'),
    'string': format('magenta'),
    'string2': format('darkMagenta'),
    'self': format('black', 'italic'),

    'brace': format('cyan'),
    'group': format('magenta'),
    'superscript': format('magenta'),
    'subscript': format('magenta'),
    'numbers': format('darkcyan'),
    'digit': format('darkcyan'),
    'variable': format('cyan'),
    'operator': format('red'),
    'command': format('red'),
    'supersub': format('red'),
    'comment': format('darkGray', 'italic'),
}

TOKEN_STYLES = {
    'keyword': format('darkcyan'),
    'defclass': format('black', 'bold'),
    'string': format('magenta'),
    'string2': format('darkMagenta'),
    'self': format('black', 'italic'),
    'brace': format('cyan'),
    MJTokenType.STARTGROUP.value: format('magenta'),
    MJTokenType.ENDGROUP.value: format('magenta'),
    MJTokenType.DIGIT.value: format('darkcyan'),
    MJTokenType.VARIABLE.value: format('cyan'),
    'operator': format('red'),
    MJTokenType.COMMAND.value: format('red'),
    MJTokenType.SUBSCRIPT.value: format('magenta'),
    MJTokenType.SUPERSCRIPT.value: format('magenta'),
    MJTokenType.COMMENT.value: format('darkGray', 'italic'),
    MJTokenType.SYMBOL.value: format('white'),
    MJTokenType.MISMATCH.value: format('white', 'bold', background='orange'),
}

TOKEN_STYLES_UNDERLINE = {key: format('yellow', underline_color='yellow', base=val,
                                      underline_style=QTextCharFormat.WaveUnderline)
                          for key, val in TOKEN_STYLES.items()}

class MathJaxHighlighter (QSyntaxHighlighter):
    """Syntax highlighter for MathJax Syntax.
    """

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)
        self.visitor = MathJaxHightlightVisitor(self)

        # Multi-line strings (expression, flag, style)
        self.tri_single = (QRegExp("'''"), 1, STYLES['string2'])
        self.tri_double = (QRegExp('"""'), 2, STYLES['string2'])
        self.parse_rev = self.document().revision() - 1
        self.update_parsing()
        self.text_tokens = []
        self.previous_cursor_pos = 0


        self.bracket_map = {}

    def set_bracket_map(self, map):
        self.bracket_map = map


    def update_cursor(self, text_cursor:QTextCursor):
        self.text_cursor = text_cursor
        rehighlight: set = {self.previous_cursor_pos}
        if self.text_tokens:
            for pos in [text_cursor.position(), self.previous_cursor_pos]:
                text_cursor.position()
                token_index = bisect(self.text_tokens, pos, key=attrgetter('pos')) - 1

                token = self.text_tokens[token_index]
                match = self.bracket_map.get(token, None)

                if match is not None:
                    match_block = self.document().findBlock(match.pos)
                    rehighlight.add(text_cursor.block().blockNumber())
                    rehighlight.add(match_block.blockNumber())

            for block_number in rehighlight:
                block = self.document().findBlockByNumber(block_number)
                self.rehighlightBlock(block)

    def update_parsing(self):
        current_rev = self.document().revision()
        if self.parse_rev != current_rev:
            self.text_tokens = list(tokenize(self.document().toPlainText(), ignore_mismatch=True))
            self.bracket_map = gen_bracket_match_map(self.text_tokens)
            self.parse_rev = current_rev



    # thoughts about paren matching: how should we match and resolve ambiguity?
    # cursor directly on, definitly highlight that.
    # check cursor to the left/right.. maybe only highlight it only if token cursor is on directly
    # did not/would not be highlighted.


    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """

        self.update_parsing()
        block_start =  self.currentBlock().position()
        block_end = block_start + len(self.currentBlock().text())

        cursor_pos = self.text_cursor.position()
        #match_ranges = self.bracket_map[self.text_cursor.position()]

        #for token in self.text_tokens:  # this looks through all tokens. seems inefficient
        for token in self.get_tokens_in_block(self.currentBlock()):
            token_format = TOKEN_STYLES.get(token.type.value, None)
            match = self.bracket_map.get(token, None)

            if match is not None:
                # checks if the cursor position is within the range of a token in the block or its
                # match.
                if ((cursor_pos >= token.pos and cursor_pos < token.pos + len(token.text)) or
                        (cursor_pos >= match.pos and cursor_pos < match.pos + len(match.text))):

                    token_format = TOKEN_STYLES_UNDERLINE.get(token.type.value, None)

            if token_format is not None:
                # adjust the token range to be clipped by the bounds of the current block
                # and make the positions relative to the current block
                token_start = max(token.pos, block_start) - block_start
                token_end = min(token.pos + len(token.text), block_end) - block_start
                if token_format is not None and token_start < token_end:
                    self.setFormat(token_start, token_end - token_start, token_format)



    def get_tokens_in_block(self, block:QTextBlock):
        # given a position in the document, find the token that contains it
        token_start_index = bisect(self.text_tokens, block.position(), key=attrgetter('pos')) - 1
        token_end_index = bisect(self.text_tokens, block.position() + block.length(),
                                 key=attrgetter('pos')) - 1
        return self.text_tokens[token_start_index:token_end_index + 1]




    def highlightBlock_old(self, text):
        """Apply syntax highlighting to the given block of text.
        """

        try:
            if not self.visitor.revision() == self.document().revision():
                node = self.visitor.parse(self.document().toPlainText())
                self.visitor.set_revision(self.document().revision())
                # maybe we should have this be conditional
                # or maybe done by signal. but how do we guarantee that it's done by the time this
                # block is called?
        except (ParseError, IncompleteParseError, VisitationError) as e:
            print('caught zz', e)
            pass
        else:
            print('Parsing Successful, setting formats')
            for (start, length, format) in self.visitor.get_formats_for_block(self.currentBlock()):
                self.setFormat(start, length, STYLES[format])



    def generic_visit(self, node, visited_children):
        """ The generic visit method. """
        return visited_children or node


class MathJaxHightlightVisitor(NodeVisitor):
    """ Vist and Highlight MathJax grammar elements. """
    grammar = Grammar(mathjax_grammar_def)


    def __init__(self, highlighter):
        super().__init__()
        self.highlighter = highlighter
        self._revision = 0

    def set_revision(self, rev:int):
        self._revision = rev

    def revision(self):
        return self._revision

    def setCurrentBlock(self, block:QTextBlock):
        self.block = block
        self.position = block.position()
        self.length = block.length()


    def get_formats(self, start, length, offset=0):
        """returns a list of tuples that specify the format type of contiguous blocks in the form
        (start, length, format)."""

        block_formats = []
        last_format = None

        if length > 0 and self.format_map:
            block_start = start - offset
            formats = self.format_map[start:length + start]

            for format in formats:
                if format is not None:
                    if last_format == format:
                        block_formats[-1] = (block_formats[-1][0], block_formats[-1][1] + 1, format)
                    else:
                        block_formats.append((block_start, 1, format))
                block_start += 1
                last_format = format

        return block_formats

    def get_formats_for_block(self, block:QTextBlock):
        """returns a list of tuples that specify the format type of contiguous blocks in the form
        (start, length, format)."""

        start = block.position()
        return self.get_formats(start, len(block.text()), offset=start)

    def parse(self, text: str, pos: int = 0) -> Node:
        self.format_map = [None] * len(text)
        return super().parse(text)


    def visit_expr(self, node, visited_children):
        """ Returns the overall output. """
        # print('X:', node.txt)
        print('visit_expr: called:')
        return node.text
        # return visited_children or node
        # output = {}
        # for child in visited_children:
        #     output.update(child[0])
        #     dict.update
        # return output

    def visit_token(self, node, visited_children):

        print("visit_token: called")
        return node

    def visit_superscript(self, node, visited_children):

        # self.highlighter.setFormat(node.start, node.end - node.start, STYLES['superscript'])
        for i in range(node.start, node.end):
            self.format_map[i] = 'superscript'
        return node

    def visit_subscript(self, node, visited_children):

        #self.highlighter.setFormat(node.start, node.end - node.start, STYLES['subscript'])
        for i in range(node.start, node.end):
            self.format_map[i] = 'subscript'
        return node

    def visit_variable(self, node, visited_children):

        # self.highlighter.setFormat(node.start, node.end - node.start,
        #                            STYLES['variable'])
        for i in range(node.start, node.end):
            self.format_map[i] = 'variable'
        return node

    def visit_digit(self, node, visited_children):

        #self.highlighter.setFormat(node.start, node.end - node.start, STYLES['digit'])
        for i in range(node.start, node.end):
            self.format_map[i] = 'digit'
        return node

    def visit_comment(self, node, visited_children):

        #self.highlighter.setFormat(node.start, node.end - node.start, STYLES['digit'])
        for i in range(node.start, node.end):
            self.format_map[i] = 'comment'
        return node

    def visit_command(self, node, visited_children):

        backslash, command, *_ = node.children
        #self.highlighter.setFormat(command.start, command.end - command.start, STYLES['command'])
        # What should we be returning, really?
        for i in range(command.start, command.end):
            self.format_map[i] = 'command'
        return ('[***NODE***]', command, '[***NODE***]')

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



    def generic_visit(self, node, visited_children):
        """ The generic visit method. """
        return visited_children or node


