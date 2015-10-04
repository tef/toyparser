"""
An operator precedence parser that handles expressions.

The trick here is what's known as precedence climbing, or left corner
transform, or pratt parsing, and a litany of other names. The trick
is frequenly re-invented.

It's basically recursive descent + a while loop to handle left recursion.
It's very similar to doing shunting yard but with the call stack.

The trick is to split your rules into prefixes, and suffixes. You run any prefix
rules (recursive decent bit), and then repeatedly apply suffix rules (precedence
climbing).

For ex: infix operators are defined as suffix rules, we only look for a + 
after we've parsed an item
"""


from collections import namedtuple, OrderedDict

class SyntaxErr(Exception):
    pass

# Table driven parser/lexer cursors.
# These cursors are immutable, and functions like next() return new cursors.

class LexerCursor(object):
    def __init__(self, lang, source, pos=0):
        self.lang = lang
        self.source = source
        self.pos = pos 
    
    def current(self):
        return self.source[self.pos]

    def next(self):
        pos = self.pos + 1
        if pos < len(self.source):
            return LexerCursor(self.lang, self.source, pos)

    def __nonzero__(self):
        return self.pos < len(self.source)

    def __eq__(self, o):
        return self.pos == o.pos and self.source == o.source



class ParserCursor(object):
    def __init__(self, language, lexer, pos=0):
        self.lexer = lexer
        self.lang = language

    def current_token(self):
        return self.lexer.current()

    def pos(self):
        if self.lexer:
            return self.lexer.pos
        else:
            return -1
        
    def next(self):
        lexer = self.lexer.next()
        return ParserCursor(self.lang, lexer)

    def pop(self):
        return self.current_token(), self.next()

    def accept(self, e):
        if e == self.current_token():
            return self.next()
        else:
            raise SyntaxErr("expecting: %s, got %s"%(e, self.current_token()))

    def __nonzero__(self):
        return bool(self.lexer)

    def __eq__(self, o):
        return self.lexer == o.lexer

    def parse_expr(self, outer):

        # this is the normal recursive descent bit

        first = self.current_token()
        pos = self.pos()

        rule = self.lang.get_prefix_rule(first, outer)
        print "parse: first:%s pos:%d" %(first, self.pos())
        if rule: # beginning of a rule
            item, parser = rule.parse_prefix(self, outer)
        else:
            item, parser = self.pop()
        
        # This is where the magic happens
        while parser and parser.pos() != pos:
            first = parser.current_token()
            pos = parser.pos()

            print "parse: suffix first:%s pos:%d" %(first, parser.pos())
            rule = self.lang.get_suffix_rule(first, outer)
            if rule and rule.captured_by(outer):
                item, parser = rule.parse_suffix(item, parser, outer)


        return item, parser


# Parse Rules 
Everything = namedtuple('Everything','precedence captured_by')(0, (lambda r: False))

class Block(namedtuple('block', 'op item close')):
    def __str__(self):
        return "<%s%s%s>"%(self.op, self.item, self.close) 

class BlockRule(namedtuple('rule', 'precedence op end_char')):
    def captured_by(self, outer):
        return outer

    def parse_prefix(self, parser, outer):
        parser = parser.accept(self.op)
        item, parser = parser.parse_expr(outer=Everything)
        print "parse_block: item: %s pos:%d" %(item, parser.pos())
        parser = parser.accept(self.end_char)
        return Block(self.op, item, self.end_char), parser
    
class Prefix(namedtuple('prefix', 'op right')):
    def __str__(self):
        return "<%s %s>"%(self.op, self.right) 

class PrefixRule(namedtuple('rule', 'precedence op')):
    def captured_by(self, rule):
        return true

    def parse_prefix(self, parser, outer):
        parser = parser.accept(self.op)
        new_item, parser = parser.parse_expr(outer=self)
        print "PrefixRule: item: %s pos:%d" %(new_item, parser.pos())
        return Prefix(self.op, new_item), parser


class Infix(namedtuple('infix', 'op left right')):
    def __str__(self):
        return "<%s %s %s>"%(self.left, self.op, self.right) 

class InfixRule(namedtuple('rule','precedence op')):
    def captured_by(self, rule):
        return rule.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

    def parse_suffix(self, item, parser, outer):
        left = item
        parser = parser.accept(self.op)
        print "infix: item: %s pos:%d" %(item, parser.pos())
        right, parser = parser.parse_expr(outer=self)
        return Infix(self.op, left, right), parser

class RInfixRule(InfixRule):
    def captured_by(self, rule):
        return rule.precedence <= self.precedence

class PostfixBlock(namedtuple('infix', 'op left right close')):
    def __str__(self):
        return "<%s%s%s%s>"%(self.left, self.op, self.right, self.close) 

class PostfixBlockRule(namedtuple('rule','precedence op end_char')):
    def captured_by(self, rule):
        return rule.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

    def parse_suffix(self, item, parser, outer):
        left = item
        parser = parser.accept(self.op)
        # print "infix: %s" % op
        right, parser = parser.parse_expr(outer=Everything)
        parser = parser.accept(self.end_char)
        return PostfixBlock(self.op, left, right, self.end_char), parser

class PostfixRule(namedtuple('rule','precedence op')):
    def captured_by(self, outer):
        return outer.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

    def parse_suffix(self, item, parser, outer):
        left = item
        parser = parser.accept(self.op)
        return Postfix(self.op, left), parser

class Postfix(namedtuple('postfix', 'op left')):
    def __str__(self):
        return "<%s %s>"%(self.left, self.op) 

class DefaultRule(namedtuple('expr', 'op precedence')):
    def captured_by(self, rule):
        true

    def parse_prefix(self, parser, outer):
        return parser.pop()

    def parse_suffix(self, item, parser, outer):
        return item, parser



class Language(object):
    """ One big lookup table to save us from things """
    def __init__(self):
        self.suffix = OrderedDict()
        self.prefix = OrderedDict()
        self.keywords = OrderedDict()
        self.literals = OrderedDict()
        self.operators = OrderedDict()
        self.ignored = OrderedDict()
        self.whitespace = OrderedDict()

    def parse(self, source):
        lexer = LexerCursor(self, source)
        parser = ParserCursor(self, lexer)
        item, parser = parser.parse_expr(outer=Everything)

        if parser:
            raise SyntaxErr("left over lexer: %s"%parser.source)

        return item
    def add_prefix(self, rule):
        self.prefix[rule.op] = rule

    def add_suffix(self, rule):
        self.suffix[rule.op] = rule

    def get_suffix_rule(self, key, outer):
        return self.suffix.get(key)

    def get_prefix_rule(self, key, outer):
        return self.prefix.get(key)

    def def_block_rule(self, p, start, end):
        self.add_prefix(BlockRule(p, start, end))

    def def_postfix_block_rule(self, p, start, end):
        self.add_suffix(PostfixBlockRule(p, start, end))

    def def_postfix_rule(self, p, op):
        self.add_suffix(PostfixRule(p, op))

    def def_prefix_rule(self, p, op):
        self.add_prefix(PrefixRule(p, op))

    def def_infix_rule(self,p,op):
        self.add_suffix(InfixRule(p, op))
    
    def def_rinfix_rule(self,p,op):
        self.add_suffix(RInfixRule(p, op))

    def def_whitespace(self, name, rx):
        pass

    def def_keyword(self, name, rx):
        pass

    def def_literal(self, name, rx):
        pass
    
    def def_operator(self, name, rx):
        pass

    def def_control(self, name, rx): 
        pass

    def def_ignored(self, name, rx):
        pass

    def def_error(self, name,rx):
        pass

    def bootstrap(self):
        self.def_block_rule(900,'(',')')
        self.def_block_rule(900,'{','}')
        self.def_block_rule(900,'[',']')
        
        self.def_postfix_block_rule(800,'(',')')
        self.def_postfix_block_rule(800,'(','}')
        self.def_postfix_block_rule(800,'[',']')
        
        self.def_rinfix_rule(700, '**')
        
        self.def_prefix_rule(600, '+')
        self.def_prefix_rule(600, '-')
        self.def_prefix_rule(600, '~')
        self.def_prefix_rule(600, '!')
        
        self.def_infix_rule(500, '*')
        self.def_infix_rule(500, '/')
        self.def_infix_rule(500, '//')
        self.def_infix_rule(500, '%')
        
        self.def_infix_rule(400, '-')
        self.def_infix_rule(400, '+')
        
        self.def_infix_rule(300, '<<')
        self.def_infix_rule(300, '>>')
        
        self.def_infix_rule(220, '&')
        self.def_infix_rule(210, '^')
        self.def_infix_rule(200, '|')
        
        for c in "in,not in,is,is,<,<=,>,>=,<>,!=,==".split(','):
            self.def_infix_rule(130, c)
        
        self.def_infix_rule(120, 'not')
        self.def_infix_rule(110, 'and')
        self.def_infix_rule(100, 'or')
        
        self.def_rinfix_rule(0, '=')



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

language = Language()
language.bootstrap()

for test in streams:
    print test
    print language.parse(test)
    print 

