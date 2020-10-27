import re
from collections import namedtuple
def flatten(s):
    return re.sub('\n',' ', s)
def no_blanks(s):
    return re.sub(' ', '', s)
def inner(s, l='(', r=')'):
    if not l in s or not r in s:
        return s
    string_map = [(ind, t) for ind, t in enumerate(s)]
    left, right = False, False
    inside = {}
    for ind, t in string_map:
        if left == False:
            if t == l:
                left = True
                inside['left'] =  ind
            continue
        if right == False:
            if t == r:
                inside['right'] = ind
    return s[inside['left']+1:inside['right']]

#Used for grouping columns with database class
TableColumn = namedtuple('col', ['name', 'type', 'mods'])