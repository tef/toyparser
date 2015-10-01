from collections import namedtuple

class SyntaxErr(Exception):
    pass

# data structures we use 
class Infix(namedtuple('infix', 'op left right')):
    def __str__(self):
        return "(%s %s %s)"%(self.left, self.op, self.right) 

class Prefix(namedtuple('prefix', 'op right')):
    def __str__(self):
        return "(%s %s)"%(self.op, self.right) 

class Postfix(namedtuple('postfix', 'op left')):
    def __str__(self):
        return "(%s %s)"%(self.left, self.op) 

# hooray it's the parser.

# parse *one* complete item 

def parse_head(tokens, precedence):
    head, tail = tokens[0], tokens[1:]

    # print "parse_head, head=%s, tail=%s"%(head, tail)
    if head in prefix:
        # beginning of a rule
        head, tail = prefix[head].parser(head, tail, precedence)

    else:
        # just an item
        head, tail = head, tail
        
    while tail:
        old_head, old_tail = head, tail
        head, tail = parse_tail(head, tail, precedence)
        if old_head == head and old_tail == tail:
            break
    return head, tail
    
def parse_tail(head, tail, precedence):
    # print "parse_tail, head=%s, tail=%s"%(head, tail)
    if not tail:
        return head, tail

    follow = tail[0]

    if follow in suffix:
        rule = suffix[follow]
        if captures(precedence, rule.precedence, left_associative=rule.left_associative):
            return rule.parser(head, tail, precedence)


    return head, tail

# rule builders
PrefixRule = namedtuple('PrefixRule', 'parser')
SuffixRule = namedtuple('SuffixRule', 'parser precedence left_associative')


def parse_block(end_char):
    def parser(head, tail, precedence):
        head, tail = parse_head(tail, precedence=everything)
        if tail[0] == end_char:
            return head, tail[1:]
        else:
            raise SyntaxErr("syntax error, expecting %s"%end_char)
    return PrefixRule(parser)
    

def parse_prefix(p):
    def parser(op, tail, precedence):
        new_head, tail = parse_head(tail, precedence=p)
        return Prefix(op, new_head), tail
    return PrefixRule(parser)

def parse_infix(p, left_associative=True):
    def parser(head, tail, precedence):
        left, op, right, tail = head, tail[0], tail[1], tail[2:]
        # print "infix: %s" % op
        
        right, tail = parse_tail(right, tail, p)
        return Infix(op, left, right), tail
    return SuffixRule(parser, p, left_associative)

def parse_postfix(p):
    def parser(head, tail, precedence):
        left, op, tail = head, tail[0], tail[1:]
        return Postfix(op, left, right), tail
    return SuffixRule(parser, p, left_associative=True)

def captures(outer, other, left_associative=True):
    if left_associative: # left associative, i.e (a op b) op c
        return outer < other
    else: # right associative, i.e a op (b op c)
        return outer <= other


everything = 0

prefix = { } # defined later

prefix['('] = parse_block(')')
prefix['+'] = parse_prefix(1000)
prefix['-'] = parse_prefix(1000)

suffix = {}
suffix['*'] = parse_infix(500)
suffix['+'] = parse_infix(100)
suffix['**'] = parse_infix(50, left_associative=False)



def parse(source):
    head, tail = parse_head(source, precedence=everything)

    if tail:
        raise SyntaxErr("left over tokens: %s"%tail)

    return head

streams = [
    ['1', '*', '2', '+', '3', '*', '4'],
    ['(', '1', '+', '2', ')', '*', '3'],
    ['1', '**', '2', '**', 3],
    ['+', '1','*',2],
    ['+', '(', '1','*','2',')'],

]

for test in streams:
    print test
    print parse(test)
    print 

