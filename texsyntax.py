# syntax.py

import sys

# from PySide2 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import (QSyntaxHighlighter, QTextBlock, QTextDocument, QTextCharFormat, QColor,
                         QFont)
from PyQt5.QtCore import QRegExp
from mjparse import mathjax_grammar_def

from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor, Node
from parsimonious.exceptions import (ParseError, IncompleteParseError, VisitationError, UndefinedLabel, BadGrammar)




def format(color, style='', background='', underline_style=QTextCharFormat.NoUnderline,
           underline_color=''):
    """Return a QTextCharFormat with the given attributes."""

    _color = QColor()
    _color.setNamedColor(color)

    _format = QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

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


class LatexHighlighter (QSyntaxHighlighter):
    """Syntax highlighter for the Python language.
    """
    # Python keywords
    keywords = [
        'and', 'assert', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'exec', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in',
        'is', 'lambda', 'not', 'or', 'pass', 'print',
        'raise', 'return', 'try', 'while', 'yield',
        'None', 'True', 'False',
    ]

    # Python operators
    oldoperators = [
        '=',
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Arithmetic
        '\+', '-', '\*', '/', '//', '\%', '\*\*',
        # In-place
        '\+=', '-=', '\*=', '/=', '\%=',
        # Bitwise
        '\^', '\|', '\&', '\~', '>>', '<<',
    ]


    operators = [
        #r'\\[A-Za-z]+',
        #r'\\ZZZZZZZZ[A-Za-z]+',
    ]

    variables = [
        #r'[^\\0-9A-Za-z]([A-Za-z]+)',
        #r'^([A-Za-z]+)',
        #r'\\ZZZZZZZZ[A-Za-z]+',
        #r'[A-Za-z]+',
    ]

    comment = [
       r'%.*$'
    ]

    braces = [
        r'\\{', r'\\}', r'\(', r'\)', r'\[', r'\]',
    ]

    group= [
        # groups in TeX are denoted by unescaped curly braces {}
        r'(?<!\\)\{', r'(?<!\\)\}',
    ]

    supersub= [
        r'_', r'\^',
    ]

    def __init__(self, parent: QTextDocument) -> None:
        super().__init__(parent)
        self.visitor = MathJaxHightlightVisitor(self)

        # Multi-line strings (expression, flag, style)
        self.tri_single = (QRegExp("'''"), 1, STYLES['string2'])
        self.tri_double = (QRegExp('"""'), 2, STYLES['string2'])

        rules = []

        # Keyword, operator, and brace rules
        # rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
        #     for w in LatexHighlighter.keywords]
        rules += [(r'%s' % o, 0, STYLES['operator'])
            for o in LatexHighlighter.operators]
        rules += [(r'%s' % b, 0, STYLES['brace'])
            for b in LatexHighlighter.braces]
        rules += [(r'%s' % s, 0, STYLES['supersub'])
                  for s in LatexHighlighter.supersub]
        rules += [(r'%s' % v, 1, STYLES['variable'])
                  for v in LatexHighlighter.variables]

        # All other rules
        rules += [
            # Numeric literals
            # (r'[0-9]*\.[0-9]+', 0, STYLES['numbers']),
            # (r'[0-9]+', 0, STYLES['numbers']),
            #(r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            #(r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            #(r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),
        ]
        """
        rules += [
            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['defclass']),

            # Numeric literals
            (r'\[0-9]+', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),


            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),

            # From '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),
        ]

        """

        # Build a QRegExp for each pattern
        self.rules = [(QRegExp(pat), index, fmt)
            for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
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


