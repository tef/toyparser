from __future__ import print_function, unicode_literals
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


from collections import namedtuple, OrderedDict, defaultdict
from functools import partial
import re

class SyntaxErr(Exception):
    pass

# Table driven parser/lexer cursors.
# These cursors are (mostly) immutable, and functions like next() return new cursors.

Token = namedtuple('token','name text position')
Token.__str__ = lambda self:"{}_{}".format(self.text, self.name[0])

class Position(namedtuple('Position','off line_off line col')):
    newlines = re.compile(r'\r|\n|\r\n') # Todo: unicode
    def count_lines(self, source, offset):
        line = self.line
        line_off = self.line_off
        #print('source', [source[self.off:offset+1]], self.off, offset, self.newlines.pattern)
        for match in self.newlines.finditer(source, self.off, offset):
            line += 1;
            line_off = match.end()

        col = (offset-line_off)+1
        return Position(offset, line_off, line, col)
    
class RegexLexer(object):
    def __init__(self, rx, source, position):
        self.source = source
        self.position = position
        self._current = None
        self._next = None
        self.rx = rx

    def pos(self):
        return self.position
    
    def current(self):
        if self._current is None:
            self._current, pos = self.rx(self.source, self.position)
            if self._current and pos.off < len(self.source):
                self._next = self.__class__(
                    self.rx, self.source, pos
                )
            else:
                self._next = ()
        return self._current



    def next(self):
        if self._next is None:
            self.current()
        return self._next


def token_filter(*types):
    class TokenFilter(object):
        def __init__(self, lexer):
            self.lexer = lexer
        
        def current(self):
            while self.lexer: 
                current = self.lexer.current()
                if current.name in types:
                    self.lexer = self.lexer.next()
                else:
                    return current

        def next(self):
            lexer = self.lexer.next()
            if lexer:
                lexer.current()
                return self.__class__(lexer)

        def pos(self):
            return self.lexer.pos()

    return TokenFilter

class ParserCursor(object):
    def __init__(self, language, lexer):
        self.lexer = lexer
        self.lang = language

    def current_token(self):
        return self.lexer.current()

    def pos(self):
        if self.lexer:
            return self.lexer.pos()
        
    def next(self):
        lexer = self.lexer.next()
        return ParserCursor(self.lang, lexer)

    def pop(self):
        return self.current_token(), self.next()

    def accept(self, e):
        if e == self.current_token().text:
            return self.next()
        else:
            raise SyntaxErr("expecting: {}, got {}".format(e, self.current_token()))

    def __nonzero__(self):
        return bool(self.lexer)

    def __eq__(self, o):
        return self.lexer == o.lexer

    def parse_stmts(self):
        exprs =[]
        parser = self
        pos = -1
        while parser:
            expr, parser = parser.parse_expr(outer=Everything)
            #print([expr])
            pos = parser.pos()
            if expr:
                exprs.append(expr)
                #print('expr',[expr])
            if parser and parser.current_token().name == 'terminator':
                while parser and parser.current_token().name =='terminator':
                    #print('next', [parser.current_token()])
                    parser = parser.next()
            else:
                break

        return exprs, parser

    def parse_expr(self, outer):
        item = self.current_token()
        pos = self.pos()
        rule = self.lang.get_prefix_rule(item, outer)

        if rule and rule.captured_by(outer): # beginning of a rule
            item, parser = rule.parse_prefix(self, outer)
            #print(rule,item, parser)
        else:
            return None, self

        # This is where the magic happens
        while parser and parser.pos() != pos:
            first = parser.current_token()
            pos = parser.pos()
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
        #print "parse_block: item: %s pos:%d" %(item, parser.pos())
        parser = parser.accept(self.end_char)
        return Block(self.op, item, self.end_char), parser
    
class Prefix(namedtuple('prefix', 'op right')):
    def __str__(self):
        return "<%s %s>"%(self.op, self.right) 

class PrefixRule(namedtuple('rule', 'precedence op')):
    def captured_by(self, rule):
        return True

    def parse_prefix(self, parser, outer):
        parser = parser.accept(self.op)
        new_item, parser = parser.parse_expr(outer=self)
        #print "PrefixRule: item: %s pos:%d" %(new_item, parser.pos())
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
        #print "infix: item: %s pos:%d" %(item, parser.pos())
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
        #print(parser.pos(), parser.current_token())
        parser = parser.accept(self.op)
        #print "infix: %s" % op
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

class TokenRule(namedtuple('expr', 'op precedence')):
    def captured_by(self, rule):
        return True

    def parse_prefix(self, parser, outer):
        return parser.pop()

class TerminatorRule(namedtuple('expr','op precedence')):
    def captured_by(self, outer):
        #print(outer, self.precedence)
        return outer.precedence < self.precedence #(the precedence is higher, the scope is more narrow!)

class Language(object):
    """ One big lookup table to save us from things """
    def __init__(self):
        self.literal_rule = TokenRule('literal', 0)
        self.suffix = OrderedDict()
        self.prefix = OrderedDict()
        self.literals = OrderedDict()
        self.operators = set()
        self.ignored = set()
        self.whitespace = OrderedDict()
        self.terminators = set()
        self.comments = set()
        self._rx = None
        self._names = None

    def rx(self):
        ops = sorted(self.operators, key=len, reverse=True)
        ops =[ re.escape(o).replace(' ','\s+') for o in ops]


        rx = [
            ('terminator', "|".join(self.terminators)),
            ('whitespace', "|".join(self.whitespace.values())),
            ('operator', "|".join(ops)),
        ]
        for key, value in self.literals.items():
            rx.append((key, value))
        
        rx= "|".join("(?P<{}>{})".format(*a) for a in rx)
        
        ignored = "|".join(self.ignored)

        rx = r'(?:{})* ({}) (?:{})*'.format(ignored, rx, ignored)

        rx = re.compile(rx, re.U + re.X)
        #print(rx.pattern)
        self._rx = rx
        self._names = dict(((v, k) for k,v in rx.groupindex.items()))


    def match(self, source, position):
        if not self._rx:
            self.rx()

        match = self._rx.match(source, position.off)

        if not match:
            return Token('error', 'unknown', position), position

        for num, result in enumerate(match.groups()[1:],2):
            if result:
                name = self._names[num] 
                #print(position.off, match.start(num), match.end(0))
                pos =  position.count_lines(source, match.start(num))
                next_pos = pos.count_lines(source, match.end(0))
                token = Token(name, result, pos)
                #print("pos",pos, next_pos)
                return token, next_pos

    def get_suffix_rule(self, token, outer):
        return self.suffix.get(token.text)

    def get_prefix_rule(self, token, outer):
        if token.name in ("operator","terminator"):
            return self.prefix[token.text]
        else:
            return self.literal_rule

    def parse(self, source):
        if source:
            pos = Position(off=0, line_off=0, line=1,col=1)
            lexer = RegexLexer(self.match, source, pos)
            filter = token_filter("whitespace")
            parser = ParserCursor(self, filter(lexer))

            items, parser = parser.parse_stmts()

            if parser:
                raise SyntaxErr("item {}, left over {} at {}".format(items,source[parser.pos().off:], parser.pos()))

            return items


    def def_whitespace(self, name, rx):
        rx = re.compile(rx, re.U).pattern
        self.whitespace[name] = rx


    def def_literal(self, name, rx):
        rx = re.compile(rx, re.U).pattern
        self.literals[name] = rx

    def def_ignored(self, name, rx):
        rx = re.compile(rx, re.U).pattern
        self.ignored[name] = rx

    def def_comment(self, name, rx):
        rx = re.compile(rx, re.U).pattern
        self.comment[name] = rx

    def def_keyword(self, name):
        self.operators.add(name)

    def def_terminator(self, name, rx):
        self.terminators.add(rx)
        self.prefix[name] = TerminatorRule(name, -1)

    def def_block(self, p, start, end):
        rule = BlockRule(p, start, end)
        self.prefix[rule.op] = rule
        self.operators.add(start)
        self.operators.add(end)

    def def_postfix_block(self, p, start, end):
        rule = PostfixBlockRule(p, start, end)
        self.suffix[rule.op] = rule
        self.operators.add(start)
        self.operators.add(end)

    def def_postfix(self, p, op):
        rule = PostfixRule(p, op)
        self.suffix[rule.op] = rule
        self.operators.add(rule.op)

    def def_prefix(self, p, op):
        rule = PrefixRule(p, op)
        self.prefix[rule.op] = rule
        self.operators.add(rule.op)

    def def_infix(self,p,op):
        rule = InfixRule(p, op)
        self.suffix[rule.op] = rule
        self.operators.add(rule.op)
    
    def def_rinfix(self,p,op):
        rule = RInfixRule(p, op)
        self.suffix[rule.op] = rule
        self.operators.add(rule.op)

    def bootstrap(self):
        self.def_terminator("\n",r"\n") 
        self.def_terminator(";", r";") 
        self.def_whitespace("space", r"\s+") 
        self.def_literal("number",r"\d[\d_]*")
        self.def_literal("identifier",r"\w+")
        self.def_literal("true", r"true\b")
        self.def_literal("false", r"false\b")
        self.def_literal("null", r"null\b")
        self.def_block(900,'(',')')
        self.def_block(900,'{','}')
        self.def_block(900,'[',']')
        
        self.def_postfix_block(800,'(',')')
        self.def_postfix_block(800,'{','}')
        self.def_postfix_block(800,'[',']')
        
        self.def_rinfix(700, '**')
        
        self.def_prefix(600, '+')
        self.def_prefix(600, '-')
        self.def_prefix(600, '~')
        self.def_prefix(600, '!')
        
        self.def_infix(500, '*')
        self.def_infix(500, '/')
        self.def_infix(500, '//')
        self.def_infix(500, '%')
        
        self.def_infix(400, '-')
        self.def_infix(400, '+')
        
        self.def_infix(300, '<<')
        self.def_infix(300, '>>')
        
        self.def_infix(220, '&')
        self.def_infix(210, '^')
        self.def_infix(200, '|')
        
        for c in "in,not in,is,is,<,<=,>,>=,<>,!=,==".split(','):
            self.def_infix(130, c)
        
        self.def_infix(120, 'not')
        self.def_infix(110, 'and')
        self.def_infix(100, 'or')
        
        self.def_rinfix(0, '=')



test = """
1 + 2
1 + 2 + 3 + 4 + 5
1 + 2 * 3 + 4
2 ** 3 ** 4
- 2 ** 3 ** 4 * 8
x [ 0 ] * 9
( 1 + 2 ) * 3
1*2+3+x[0][1]{2}
"""

language = Language()
language.bootstrap()


#for t in test.split("\n"):
#    print(t)
#    print(language.parse(t))
#    print()

print(test)
[print(line) for line in language.parse(test)]
print()
