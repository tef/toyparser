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

class Block(namedtuple('infix', 'op item close')):
    def __str__(self):
        return "<%s%s%s>"%(self.op, self.item, self.close) 

class Infix(namedtuple('infix', 'op left right')):
    def __str__(self):
        return "<%s %s %s>"%(self.left, self.op, self.right) 

class InfixBlock(namedtuple('infix', 'op left right close')):
    def __str__(self):
        return "<%s%s%s%s>"%(self.left, self.op, self.right, self.close) 

class Prefix(namedtuple('prefix', 'op right')):
    def __str__(self):
        return "<%s %s>"%(self.op, self.right) 

class Postfix(namedtuple('postfix', 'op left')):
    def __str__(self):
        return "<%s %s>"%(self.left, self.op) 

# hooray it's the parser.

# We have two types of rules

# Prefix Operators: Parenthesis, Expressions that don't recurse on the left hand.
# Suffix Operators: Infix, Postfix, and things that recurse on the left.

PrefixRule = namedtuple('PrefixRule', 'parse_item')
SuffixRule = namedtuple('SuffixRule', 'parse_item_suffix precedence left_associative')

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

class Cursor(object):
    def __init__(self, source, pos=0):
        self.source = source
        self.pos = pos

    def peek(self):
        return self.source[self.pos]

    def next(self):
        return Cursor(self.source,self.pos+1)

    def pop(self):
        return self.peek(), self.next()

    def accept(self, e):
        if e == self.source[self.pos]:
            return self.next()
        else:
            raise SyntaxErr("expecting: %s, got %s"%(e, self.peek))


    def __nonzero__(self):
        return self.pos < len(self.source)

    def __eq__(self, o):
        return self.pos == o.pos and self.source == o.source

    def parse_item(self, precedence):

        # this is the normal recursive descent bit

        lookahead = self.peek()

        print "parse_item: lookahead:%s pos:%d" %(lookahead, self.pos)
        if lookahead in prefix: # beginning of a rule
            item, cursor = prefix[lookahead].parse_item(self, precedence)
        else:
            item, cursor = self.pop()
        
        # This is where the magic happens
        while cursor:
            lookahead = cursor.peek()
            rule = suffix.get(lookahead)
            print "parse_item: suffix lookahead:%s pos:%d" %(lookahead, cursor.pos)

            if rule and captures(precedence, rule.precedence, left_associative=rule.left_associative):
                item, cursor = rule.parse_item_suffix(item, cursor, precedence)
            else:
                break

        return item, cursor

def parse(source):
    cursor = Cursor(source)
    item, cursor = cursor.parse_item(precedence=everything)

    if cursor:
        raise SyntaxErr("left over tokens: %s"%cursor.source)

    return item

# Parse one item with the current precidence, returning it
# And the remaining tokens



# rule builders

class BlockRule(namedtuple('rule', 'precedence start_char end_char')):
    def captured_by(self, rule):
        return true

    def parse_item(self, cursor, precedence):
        cursor = cursor.accept(self.start_char)
        item, cursor = cursor.parse_item(precedence=everything)
        print "parse_block: item: %s pos:%d" %(item, cursor.pos)
        cursor = cursor.accept(self.end_char)
        return Block(self.start_char, item, self.end_char), cursor
    

def parse_prefix(p):
    def parser(cursor, precedence):
        op, cursor = cursor.pop()
        new_item, cursor = cursor.parse_item(precedence=p)
        print "parse_prefix: item: %s pos:%d" %(new_item, cursor.pos)
        return Prefix(op, new_item), cursor
    return PrefixRule(parser)

def parse_infix(p, left_associative=True):
    def parser(item, cursor, precedence):
        left = item
        op, cursor = cursor.pop()
        print "infix: item: %s pos:%d" %(item, cursor.pos)
        right, cursor = cursor.parse_item(p)
        return Infix(op, left, right), cursor
    return SuffixRule(parser, p, left_associative)


def parse_infix_block(p, end_char):
    def parser(item, cursor, precedence):
        left = item
        op, cursor = cursor.pop()
        # print "infix: %s" % op
        right, cursor = cursor.parse_item(precedence=everything)
        cursor = cursor.accept(end_char)
        return InfixBlock(op, left, right, end_char), cursor
    return SuffixRule(parser,p, left_associative=True)

def parse_postfix(p):
    def parser(item, cursor, precedence):
        left = item
        op, cursor = cursor.pop()
        return Postfix(op, left), cursor
    return SuffixRule(parser, p, left_associative=True)

# parser rules.

prefix['('] = BlockRule(900,'(',')')
prefix['{'] = BlockRule(900,'{','}')
prefix['['] = BlockRule(900,'[',']')

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
    "1 + 2 + 3 * 4 * 5 * 6".split(),
    ['+', '1','*',2],
    ['+', '(', '1','*','2',')'],
    ['x','[','1',']'],

]

for test in streams:
    print test
    print parse(test)
    print 

