from collections import namedtuple

# some basic defintions of operator precedence

everything = 0

prefix = {
    '+': 1000,
    '-': 1000,
}
postfix = {

}

left_infix = {
    '*': 500,
    '+': 100,
}

right_infix = { 
    '**': 50,
}

expressions = { } # defined later
suffixes = { } # defined later

def captures(outer, other, left=True):
    if left: # left associative, i.e (a op b) op c
        return outer < other
    else: # right associative, i.e a op (b op c)
        return outer <= other

# data structures we use 
class SyntaxErr(Exception):
    pass

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

    print "parse_head, head=%s, tail=%s"%(head, tail)
    if head in expressions:
        head, tail = expressions[head](head, tail, precedence)

    elif head in prefix:
        head, tail = parse_head(tail, precedence=prefix[head])
        head = Prefix(head, head)

    elif head.isdigit():
        head, tail = head, tail
        
    else:
        raise SyntaxErr("syntax error, expected number or prefix operator")
    
    while tail and (tail[0] in suffixes):
            head, tail = parse_tail(head, tail, precedence)
    return head, tail
    
def parse_tail(head, tail, precedence):
    print "parse_tail, head=%s, tail=%s"%(head, tail)
    if not tail:
        return head, tail

    follow = tail[0]
    if follow in left_infix and captures(precedence, left_infix[follow]):
        print "infix: %s" % follow
        left, op, right, tail = head, tail[0], tail[1], tail[2:]
        
        right, tail = parse_tail(right, tail, left_infix[follow])
        return Infix(op, left, right), tail

    if follow in right_infix and captures(precedence, right_infix[follow], left=False):
        print "infix: %s" % follow
        left, op, right, tail = head, tail[0], tail[1], tail[2:]
        
        right, tail = parse_tail(right, tail, right_infix[follow])
        return Infix(op, left, right), tail

    elif follow in postfix and captures(precedence, postfix[follow]):
        left, op, tail = head, tail[0], tail[1:]
        return Postfix(op, left, right), tail
    else:
        return head, tail

def parse_braces(head, tail, precedence):
    head, tail = parse_head(tail, precedence=everything)
    if tail[0] == ')':
        return head, tail[1:]
    else:
        raise SyntaxErr("syntax error, expecting )")
    

expressions['('] = parse_braces

suffixes.update(left_infix)
suffixes.update(right_infix)
suffixes.update(postfix)

def parse(source):
    head, tail = parse_head(source, precedence=everything)

    if tail:
        raise SyntaxErr("left over tokens: %s"%tail)

    return head

streams = [
    ['1', '*', '2', '+', '3', '*', '4'],
    ['(', '1', '+', '2', ')', '*', '3'],
    ['1', '**', '2', '**', 3],
]

for test in streams:
    print test
    print parse(test)
    print 

