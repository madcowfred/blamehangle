"""
This thing terrifies me. Original URL:

http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/277940
"""

from types import ClassType, FunctionType
from opcode import opmap, HAVE_ARGUMENT, EXTENDED_ARG
LOAD_GLOBAL, LOAD_CONST = opmap['LOAD_GLOBAL'], opmap['LOAD_CONST']
ABORT_CODES = (EXTENDED_ARG, opmap['STORE_GLOBAL'])

def _make_constants(f, builtin_only=False, stoplist=[], verbose=False):
    try:
        co = f.func_code
    except AttributeError:
        return f        # Jython doesn't have a func_code attribute.
    newcode = map(ord, co.co_code)
    newconsts = list(co.co_consts)
    codelen = len(newcode)
    
    import __builtin__
    env = vars(__builtin__).copy()
    if builtin_only:
        stoplist = dict.fromkeys(stoplist)
        stoplist.update(f.func_globals)
    else:
        env.update(f.func_globals)

    i = 0
    while i < codelen:
        opcode = newcode[i]
        if opcode in ABORT_CODES:
            return f    # for simplicity, only optimize common cases
        if opcode == LOAD_GLOBAL:
            oparg = newcode[i+1] + (newcode[i+2] << 8)            
            name = co.co_names[oparg]
            if name in env and name not in stoplist:
                value = env[name]
                for pos, v in enumerate(newconsts):
                    if v is value:
                        break
                else:
                    pos = len(newconsts)
                    newconsts.append(value)
                newcode[i] = LOAD_CONST
                newcode[i+1] = pos & 0xFF
                newcode[i+2] = pos >> 8
                if verbose:
                    print name, '-->', value
        i += 1
        if opcode >= HAVE_ARGUMENT:
            i += 2

    codestr = ''.join(map(chr, newcode))
    codeobj = type(co)(co.co_argcount, co.co_nlocals, co.co_stacksize,
                    co.co_flags, codestr, tuple(newconsts), co.co_names,
                    co.co_varnames, co.co_filename, co.co_name,
                    co.co_firstlineno, co.co_lnotab, co.co_freevars,
                    co.co_cellvars)
    return type(f)(codeobj, f.func_globals, f.func_name, f.func_defaults,
                    f.func_closure)
