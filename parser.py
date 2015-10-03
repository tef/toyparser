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


# The suffix rules expose a precidence, over how much they bind to the left
# hand argument in <head> <suffix> i.e 1 + 2 * 3 the binding on the left hand side of *

# When we run a prefix rule, it passes in the binding power it has over the right 
# hand side, i.e in +a, the binding over a

# Every rule has a precidence, but only those that bind to a left hand argument
# need to expose it. (We parse left to right)


# parse *one* complete item 
# rule builders

Everything = namedtuple('Everything','precedence captured_by')(0, (lambda r: False))

class BlockRule(namedtuple('rule', 'precedence op end_char')):
    def captured_by(self, outer):
        return outer

    def parse_prefix(self, parser, outer):
        parser = parser.accept(self.op)
        item, parser = parser.parse_expr(outer=Everything)
        print "parse_block: item: %s pos:%d" %(item, parser.pos)
        parser = parser.accept(self.end_char)
        return Block(self.op, item, self.end_char), parser
    
class PrefixRule(namedtuple('rule', 'precedence op')):
    def captured_by(self, rule):
        return true

    def parse_prefix(self, parser, outer):
        parser = parser.accept(self.op)
        new_item, parser = parser.parse_expr(outer=self)
        print "PrefixRule: item: %s pos:%d" %(new_item, parser.pos)
        return Prefix(self.op, new_item), parser

class InfixRule(namedtuple('rule','precedence op')):
    def captured_by(self, rule):
        return rule.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

    def parse_suffix(self, item, parser, outer):
        left = item
        parser = parser.accept(self.op)
        print "infix: item: %s pos:%d" %(item, parser.pos)
        right, parser = parser.parse_expr(outer=self)
        return Infix(self.op, left, right), parser

class RInfixRule(InfixRule):
    def captured_by(self, rule):
        return rule.precedence <= self.precedence

class PostfixBlockRule(namedtuple('rule','precedence op end_char')):
    def captured_by(self, rule):
        return rule.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

    def parse_suffix(self, item, parser, outer):
        left = item
        parser = parser.accept(self.op)
        # print "infix: %s" % op
        right, parser = parser.parse_expr(outer=Everything)
        parser = parser.accept(self.end_char)
        return InfixBlock(self.op, left, right, self.end_char), parser

class PostfixRule(namedtuple('rule','precedence op')):
    def captured_by(self, outer):
        return outer.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

    def parse_suffix(self, item, parser, outer):
        left = item
        parser = parser.accept(self.op)
        return Postfix(self.op, left), parser

class Parser(object):
    def __init__(self, source, pos=0):
        self.source = source
        self.pos = pos

    def peek(self):
        return self.source[self.pos]

    def next(self):
        return Parser(self.source,self.pos+1)

    def pop(self):
        return self.peek(), self.next()

    def accept(self, e):
        if e == self.peek():
            return self.next()
        else:
            raise SyntaxErr("expecting: %s, got %s"%(e, self.peek()))

    def __nonzero__(self):
        return self.pos < len(self.source)

    def __eq__(self, o):
        return self.pos == o.pos and self.source == o.source

    def parse_expr(self, outer):

        # this is the normal recursive descent bit

        lookahead = self.peek()

        print "parse: lookahead:%s pos:%d" %(lookahead, self.pos)
        if lookahead in prefix: # beginning of a rule
            item, parser = prefix[lookahead].parse_prefix(self, outer)
        else:
            item, parser = self.pop()
        
        # This is where the magic happens
        while parser:
            lookahead = parser.peek()
            rule = suffix.get(lookahead)
            print "parse: suffix lookahead:%s pos:%d" %(lookahead, parser.pos)

            if rule and rule.captured_by(outer):
                item, parser = rule.parse_suffix(item, parser, outer)
            else:
                break

        return item, parser

def parse(source):
    parser = Parser(source)
    item, parser = parser.parse_expr(outer=Everything)

    if parser:
        raise SyntaxErr("left over tokens: %s"%parser.source)

    return item

# Parse one item with the current precidence, returning it
# And the remaining tokens



prefix = {} 
suffix = {}


# parser rules.


prefix['('] = BlockRule(900,'(',')')
prefix['{'] = BlockRule(900,'{','}')
prefix['['] = BlockRule(900,'[',']')

suffix['('] = PostfixBlockRule(800,'(',')')
suffix['{'] = PostfixBlockRule(800,'(','}')
suffix['['] = PostfixBlockRule(800,'[',']')

suffix['**'] = RInfixRule(700, '**')

prefix['+'] = PrefixRule(600, '+')
prefix['-'] = PrefixRule(600, '-')
prefix['~'] = PrefixRule(600, '~')
prefix['!'] = PrefixRule(600, '!')

suffix['*'] = InfixRule(500, '*')
suffix['/'] = InfixRule(500, '/')
suffix['//'] = InfixRule(500, '//')
suffix['%'] = InfixRule(500, '%')

suffix['-'] = InfixRule(400, '-')
suffix['+'] = InfixRule(400, '+')

suffix['<<'] = InfixRule(300, '<<')
suffix['>>'] = InfixRule(300, '>>')

suffix['&'] = InfixRule(220, '&')
suffix['^'] = InfixRule(210, '^')
suffix['|'] = InfixRule(200, '|')

for c in "in,not in,is,is,<,<=,>,>=,<>,!=,==".split(','):
    suffix[c] = InfixRule(130, c)

suffix['not'] = InfixRule(120, 'not')
suffix['and'] = InfixRule(110, 'and')
suffix['or'] = InfixRule(100, 'or')

suffix['='] = RInfixRule(0, '=')

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

