from bfbbfb.dsl import ADD, IN, LOOP, MOV, OUT_S, SHF, ZERO, COPY

# !! Stack Structure !!
#
# We use a stack in the compiler to keep track of labels so we can compile
# nested loops. The stack stores values from 1 to 255 (the maximum cell value).
# The stack has the following structure:
# [<temp> 1 1 1 1 1 ... 1 0 x y z]
# 1s represent spots on the stack. The 0 marks the cell directly before the
# first stack value. x is on the top of the stack, z is on the bottom.
#
# !! Calling Convention !!
# add_to_stack: expects to the value to be pushed to be in <temp>
# pop_from_stack: expects <temp> to be 0

# !! REGISTER STRUCTURE !!
# 0:     global 0
# 1:     program input
# 2-4:   temp registers 1-3
# 5:     global parenthesis index
# 6:     stack temp
# 7-261: stack memory
# 262:   stack head


def add_to_stack():
    """
    STARTS AT  stack temp (6)
    USES       stack temp (6)
    """
    return [
        MOV(0, 1), # move value on to end of stack
        SHF(1),    # move onto end of stack
        ADD(-1),   # since stack is initially 1, get value to stack temp value
        SHF(1),    # set up execution
        # loop does the following:
        # 4>1 1 0 5 becomes 1 4>1 0 5
        # 1 4>1 0 5 becomes 1 1 4>0 5
        LOOP(      
            ADD(-1),    # decrement empty stack (1 -> 0)
            MOV(-1, 0), # curry value from last cell to this cell
            SHF(-1),    # go back to old cell
            ADD(1),     # restore stack state (0 -> 1)
            SHF(2),     # go to cell after curried value
        ),          # we see a zero
        MOV(-1, 0), # move curried value into this cell
        SHF(-2),    # go back onto a 1
        # then we go back until we see a 0, which should be stack temp
        LOOP(SHF(-1)), 
    ]


def pop_from_stack():
    """
    STARTS AT  stack temp (6)
    USES       stack temp (6)
    """
    return [
        SHF(1),       # move onto stack
        LOOP(SHF(1)), # go until stack head
        MOV(1, 0),    # move top of stack into previous cell
        SHF(-1),      # set up for loop
        # loop does the following:
        # 0 1>1 4 0 5 becomes  0>1 4 1 0 5
        # 0>1 4 1 0 5 becomes >0 4 1 1 0 5
        LOOP(
            ADD(-1),   # decrement empty stack (1 -> 0)
            MOV(1, 0), # curry value from last cell to this cell
            SHF(1),    # go back to old cell
            ADD(1),    # restore stack state (0 -> 1)
            SHF(-2),   # go to cell before curried value
        ),
        MOV(1, 0), # move value into stack temp
        SHF(1),    # move into top of stack
        ADD(1),    # reset to empty stack state (0 -> 1)
        SHF(-1),   # move bcak into stack temp
    ]

def if_eq_then(comp, *instr):
    """
    STARTS AT  program input (1)
    USES       tmp1 (2), tmp2 (3)
    *instr must start at 0 and end at 0
    """
    return [
        ADD(-ord(comp)), # subtract to maybe zero
        # if it's not zero, subtract 1 from tmp1 (tmp2 is zero)
        COPY(0, 1, 2), # save value in temp2
        LOOP(
            SHF(1),
            ADD(-1),
            SHF(-1),
            ZERO()
        ),
        MOV(2, 0),
        # add 1 to tmp1, it will now be 1 if eq, 0 if not
        SHF(1),
        ADD(1),
        MOV(0, -2), # move into 0
        SHF(-2),        # go to 0
        LOOP(
            ZERO(),
            *instr   # instruction must start and end at 0
        ),
        SHF(1), # go back to program input
        ADD(ord(comp)) # restore original program input
    ]


REGS = {
    "x86": {"dp": "r12", "ip": "r13"},
    "arm": {"dp": "X19", "ip": "X20 CHECK THAT YOU CAN ACTUALLY USE THIS REGISTER"},
}


def EMIT_INCREMENT_DP(arch):
    dp = REGS[arch]["dp"]
    return OUT_S(
        {
            "x86": f"ADD {dp}, 1\n",
            "arm": f"ADDI {dp}, {dp}, #1\n",
            "bf": ">",
        }[arch]
    )


def EMIT_DECREMENT_DP(arch):
    dp = REGS[arch]["dp"]
    return OUT_S(
        {
            "x86": f"SUB {dp}, 1\n",
            "arm": f"SUBI {dp}, {dp}, #1\n",
            "bf": "<",
        }[arch]
    )


def EMIT_INCREMENT_TAPE(arch):
    ip = REGS[arch]["ip"]
    return OUT_S(
        {
            "x86": f"ADD {ip}, 1\n",
            "arm": f"ADDI {ip}, {ip}, #1\n",
            "bf": "+",
        }[arch]
    )


def EMIT_DECREMENT_TAPE(arch):
    ip = REGS[arch]["ip"]
    return OUT_S(
        {
            "x86": f"SUB {ip}, 1\n",
            "arm": f"SUBI {ip}, {ip}, #1\n",
            "bf": "+",
        }[arch]
    )


out = {}
def EMIT_OUTPUT(arch):
    return []

inp = {}
def EMIT_INPUT(arch):
    return []

bloop = {}
def BEGIN_LOOP(arch):
    return []

eloop = {}
def END_LOOP(arch):
    return []

header = {}
def EMIT_HEADER(arch):
    return []

def compile(arch):
    return [
        *EMIT_HEADER(arch),
        SHF(1), # move to program_in
        IN(),   # get in
        LOOP(   # main loop, switch on all possible inputs
            if_eq_then(">", EMIT_INCREMENT_DP(arch)),
            if_eq_then("<", EMIT_DECREMENT_DP(arch)),
            if_eq_then("+", EMIT_INCREMENT_TAPE(arch)),
            if_eq_then("-", EMIT_DECREMENT_TAPE(arch)),
            if_eq_then(".", EMIT_OUTPUT(arch)),
            if_eq_then(",", EMIT_INPUT(arch)),
            if_eq_then("[", *BEGIN_LOOP(arch)),
            if_eq_then("]", *END_LOOP(arch)),
        ),
    ]
