import re

openers = ['{', r'\left(', r'\left[', r'\left\{', r'\left.']
closers = ['}', r'\right(', r'\right[', r'\right\{', r'\right.']

open_environtments = [r'\begin{}']
close_environments = [r'\end{}']
# begin, end

re.split

# for each opener, do we see a mirrored closer?  where should we see it?  after all closers in front of us.
# if we see the our closer before  one ahead of us is supposed to have one, that is an error.  that block/node will
# be marked as in error
# so should we not let them close an expression in error?
# maybe have a dict keyed by the openers with the count thus far in the string.  

