from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor

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

if __name__ == '__main__':
    grammar = Grammar(mathjax_grammar_def)
    tree = grammar.parse('''\displaystyle{ \n\n }  \Pr[A] \Sin''')
    mjv = MathJaxVisitorX()
    output = mjv.visit(tree)
    print("output =", output)
