"""
An operator precedence parser that handles expressions.

It's basically recursive descent + a while loop to handle left recursion.

For ((1+2)+3)+4 we parse 1, and parse the suffix for 1, which is  + 2,
then we parse the suffix for (1+2) which is +3, and so on, until we have
((1+2)+3) and the suffix is 4.

There is only really precedece settings to enforce how operations
combine and when to switch from left to right associativity.

The trick here is what's known as precedence climbing, or left corner
transform, or pratt parsing, and a litany of other names. The trick
is frequenly re-invented.

It's very similar to doing shunting yard but with the call stack.
"""


from collections import namedtuple

class SyntaxErr(Exception):
    pass

# data structures we use 

class Infix(namedtuple('infix', 'op left right')):
    def __str__(self):
        return "(%s %s %s)"%(self.left, self.op, self.right) 

class InfixBlock(namedtuple('infix', 'op left right close')):
    def __str__(self):
        return "(%s%s%s%s)"%(self.left, self.op, self.right, self.close) 

class Prefix(namedtuple('prefix', 'op right')):
    def __str__(self):
        return "(%s %s)"%(self.op, self.right) 

class Postfix(namedtuple('postfix', 'op left')):
    def __str__(self):
        return "(%s %s)"%(self.left, self.op) 

# hooray it's the parser.

# We have two types of rules

# Prefix Operators: Parenthesis, Expressions that don't recurse on the left hand.
# Suffix Operators: Infix, Postfix, and things that recurse on the left.

PrefixRule = namedtuple('PrefixRule', 'parser')
SuffixRule = namedtuple('SuffixRule', 'parser precedence left_associative')

# The suffix rules expose a precidence, over how much they bind to the left
# hand argument in <head> <suffix> i.e 1 + 2 * 3 the binding on the left hand side of *

# When we run a prefix rule, it passes in the binding power it has over the right 
# hand side, i.e in +a, the binding over a

# Every rule has a precidence, but only those that bind to a left hand argument
# need to expose it. (We parse left to right)

everything = 0


prefix = {} 
suffix = {}

# Precidence
# This is called in parse_tail, to work out if 1+2 op 3 
# should parse 1+(2 op 3) or (1+2) op 3 

def captures(outer, other, left_associative=True):
    if left_associative: # left associative, i.e (a op b) op c
        return outer < other #(the precedence is higher, the scope is more narrow!)
    else: # right associative, i.e a op (b op c)
        return outer <= other

# parse *one* complete item 

def parse(source):
    head, tail = parse_item(source, precedence=everything)

    if tail:
        raise SyntaxErr("left over tokens: %s"%tail)

    return head

# Parse one item with the current precidence, returning it
# And the remaining tokens

def parse_item(tokens, precedence):
    head, tail = tokens[0], tokens[1:]
    # print "parse_item, head=%s, tail=%s"%(head, tail)

    # this is the normal recursive descent bit

    if head in prefix: # beginning of a rule
        head, tail = prefix[head].parser(head, tail, precedence)
    
    # This is where the magic happens
    while tail:
        old_head, old_tail = head, tail
        # Take the item and find any infix rules that bind to it and their right hand side
        head, tail = parse_tail(head, tail, precedence)
        # And then use that as the new item, and search again for infix rules 
        if old_head == head and old_tail == tail:
            break
    return head, tail
    
def parse_tail(head, tail, precedence):
    # print "parse_tail, head=%s, tail=%s"%(head, tail)

    if tail and tail[0] in suffix:
        rule = suffix[tail[0]]
        if captures(precedence, rule.precedence, left_associative=rule.left_associative):
            return rule.parser(head, tail, precedence)

    return head, tail

# rule builders

def parse_block(end_char):
    def parser(head, tail, precedence):
        head, tail = parse_item(tail, precedence=everything)
        if tail[0] == end_char:
            return head, tail[1:]
        else:
            raise SyntaxErr("syntax error, expecting %s"%end_char)
    return PrefixRule(parser)
    

def parse_prefix(p):
    def parser(op, tail, precedence):
        new_head, tail = parse_item(tail, precedence=p)
        return Prefix(op, new_head), tail
    return PrefixRule(parser)

def parse_infix(p, left_associative=True):
    def parser(head, tail, precedence):
        left, op, right, tail = head, tail[0], tail[1], tail[2:]
        # print "infix: %s" % op
        
        right, tail = parse_tail(right, tail, p)
        return Infix(op, left, right), tail
    return SuffixRule(parser, p, left_associative)

def parse_infix_block(p, end_char):
    def parser(head, tail, precedence):
        left, op, tail = head, tail[0], tail[1:]
        # print "infix: %s" % op
        right, tail = parse_item(tail, precedence=everything)
        if tail[0] == end_char:
            return InfixBlock(op, left, right, end_char), tail[1:]
        else:
            raise SyntaxErr("syntax error, expecting %s"%end_char)
    return SuffixRule(parser,p, left_associative=True)

def parse_postfix(p):
    def parser(head, tail, precedence):
        left, op, tail = head, tail[0], tail[1:]
        return Postfix(op, left, right), tail
    return SuffixRule(parser, p, left_associative=True)

# parser rules.

prefix['('] = parse_block(')')
prefix['{'] = parse_block('}')
prefix['['] = parse_block(']')

suffix['('] = parse_infix_block(800,')')
suffix['{'] = parse_infix_block(800,'}')
suffix['['] = parse_infix_block(800,']')

suffix['**'] = parse_infix(700, left_associative=False)

prefix['+'] = parse_prefix(600)
prefix['-'] = parse_prefix(600)
prefix['~'] = parse_prefix(600)
prefix['!'] = parse_prefix(600)

suffix['*'] = parse_infix(500)
suffix['/'] = parse_infix(500)
suffix['//'] = parse_infix(500)
suffix['%'] = parse_infix(500)

suffix['-'] = parse_infix(400)
suffix['+'] = parse_infix(400)

suffix['<<'] = parse_infix(300)
suffix['>>'] = parse_infix(300)

suffix['&'] = parse_infix(220)
suffix['^'] = parse_infix(210)
suffix['|'] = parse_infix(200)

for c in "in,not in,is,is,<,<=,>,>=,<>,!=,==".split(','):
    suffix[c] = parse_infix(130)

suffix['not'] = parse_infix(120)
suffix['and'] = parse_infix(110)
suffix['or'] = parse_infix(100)

suffix['='] = parse_infix(everything, left_associative=False)

streams = [
    ['1', '*', '2', '+', '3', '*', '4'],
    ['(', '1', '+', '2', ')', '*', '3'],
    ['1', '**', '2', '**', 3],
    ['3','+','1', '**', '2', '**', '3', '+', 4],
    ['+', '1','*',2],
    ['+', '(', '1','*','2',')'],
    ['x','[','1',']'],

]

for test in streams:
    print test
    print parse(test)
    print 

