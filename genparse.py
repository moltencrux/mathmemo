#!/usr/bin/env python3

import argparse
import sys
from parsimonious.grammar import Grammar
from parsimonious.exceptions import ParseError


def print_tree(node, depth=0):
    """Print a Parsimonious parse tree."""
    indent = "  " * depth
    text = repr(node.text)

    print(f"{indent}{node.expr_name}: {text}")

    for child in node.children:
        print_tree(child, depth + 1)


def main():
    parser = argparse.ArgumentParser(
        description="Parse an input file using a Parsimonious PEG grammar."
    )
    parser.add_argument("grammar_file", help="Path to the PEG grammar file")
    parser.add_argument("input_file", help="Path to the input file")
    args = parser.parse_args()

    try:
        with open(args.grammar_file, "r", encoding="utf-8") as f:
            grammar_source = f.read()

        with open(args.input_file, "r", encoding="utf-8") as f:
            input_text = f.read()

        grammar = Grammar(grammar_source)
        result = grammar.parse(input_text)

        print_tree(result)

    except ParseError as error:
        print(f"Parse error:\n{error}", file=sys.stderr)
        return 1

    except OSError as error:
        print(f"File error: {error}", file=sys.stderr)
        return 1

    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
