from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
from typing import NamedTuple
from enum import StrEnum, auto
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
ws = ~"[\s\n\r]*"
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
        # print('X:', node.txt)
        print('visit_expr: called:')
        return ('##EXPR##', node.text, '##EXPR##',)
        # return visited_children or node
        # output = {}
        # for child in visited_children:
        #     output.update(child[0])
        #     dict.update
        # return output

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
    # def visit_entry(self, node, visited_children):
    #     """ Makes a dict of the section (as key) and the key/value pairs. """
    #     key, values = visited_children
    #     return {key: dict(values)}

    # def visit_token(self, node, visited_children):

    #     print("visit_token: called")
    #     pass
    #     variable, *_ = node.children
    #     return variable

    def visit_variable(self, node, visited_children):
        print("visit_variable: called")
        pass
        # variable, *_ = node.children
        return node.text

    def visit_letter(self, node, visited_children):

        print("visit_letter: called")
        pass
        # variable, *_ = node.children
        return node.text

    def generic_visit(self, node, visited_children):
        """ The generic visit method. """
        return visited_children or node

    def visit(self, node):
        pass
        return super().visit(node)


class MJTokenType(StrEnum):
    COMMENT = auto()
    COMMAND = auto()
    STARTGROUP = auto()
    ENDGROUP = auto()
    DIGIT = auto()
    SUPERSCRIPT = auto()
    SUBSCRIPT = auto()
    VARIABLE = auto()
    SYMBOLS = auto()
    NEWLINE = auto()
    SKIP = auto()
    MISMATCH = auto()


class Token(NamedTuple):
    type: MJTokenType
    value: str
    line: int
    pos: int

# This might not cover 2pt type parameters correctly. Do those need to be a single token?
def tokenize(code, ignore_mismatch=False):
    # keywords = {'IF', 'THEN', 'ENDIF', 'FOR', 'NEXT', 'GOSUB', 'RETURN'}
    token_spec = (
        (MJTokenType.COMMENT,      r'%[^\n]*\n?'),                    # Comment
        (MJTokenType.COMMAND,      r'\\(?:[A-Za-z]+|[ %#&_{}\\$])'),  # Command
        (MJTokenType.STARTGROUP,   r'\{'),                            # Group left delimiter
        (MJTokenType.ENDGROUP,     r'\}'),                            # Group right delimiter
        (MJTokenType.DIGIT,        r'\d'),                            # Decimal digit
        (MJTokenType.SUPERSCRIPT,  r'\^'),                            # Superscript/Power
        (MJTokenType.SUBSCRIPT,    r'_'),                             # Subscript
        (MJTokenType.VARIABLE,     r'[A-Za-z]'),                      # Identifiers
        (MJTokenType.SYMBOLS,      r'[+\-*\/=()\[\]|`\$\',.:;@?]'),   # Symbols (no escape required)
        (MJTokenType.NEWLINE,      r'\n'),                            # Line endings
        (MJTokenType.SKIP,         r'[ \t]+'),                        # Skip over spaces and tabs
        (MJTokenType.MISMATCH,     r'(?:\\.)|.'),                     # Any other character
    )
    tok_regex = '|'.join(f'(?P<{kind}>{regex})' for (kind, regex) in token_spec)
    line_num = 1
    line_start = 0
    for match in re.finditer(tok_regex, code):
        kind = MJTokenType(match.lastgroup)
        value = match.group()
        pos = match.start() - line_start
        if kind == MJTokenType.MISMATCH and not ignore_mismatch:
            raise RuntimeError(f'{value!r} unexpected on line {line_num}')
        yield Token(kind, value, line_num, pos)

if __name__ == '__main__':
    pcrule = r'''
    \displaystyle{
         \Pr(A_n \cap \cdots \cap A_1) = \prod_{k=1}^n P\left(
           A_k \middle| \bigcap_{j=1}^{k-1} A_j
         \right)
       }
    '''
    token_gen = tokenize(r'''\\xyz''', ignore_mismatch=True)
    for token in token_gen:
        print(token)

    # grammar = Grammar(mathjax_grammar_def)
    # tree = grammar.parse('''\displaystyle{ \n\n }  \Pr[A] \Sin''')
    # mjv = MathJaxVisitorTest()
    # output = mjv.visit(tree)
    # print("output =", output)
