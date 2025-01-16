from bfbbfb.dsl import ADD, COPY, IN, LOOP, MOV, OUT_S, SHF, ZERO, off, OUT_N, OUT
DP = {
    "x86": "r12",
    "arm": "X19",
}

# !! STACK STRUCTURE !!
#
# We use a stack in the compiler to keep track of labels so we can compile
# nested loops. The stack stores values from 1 to 255 (the maximum cell value).
# The stack has the following structure:
# [z y x 0 1 1 1 1 ... 1 <temp>]
# 1s represent spots on the stack. The 0 marks the cell directly before the
# first stack value. x is on the top of the stack, z is on the bottom.

# !! REGISTER STRUCTURE !!
# +-------+------------+--------------+-----+-------+----+----+----+--------+
# | stack | stack temp | paren number | <0> | input | t1 | t2 | t3 | mem... |
# +-------+------------+--------------+-----+-------+----+----+----+--------+
# <0> should always be set to 0 (or at least very transiently not)

ST=-2
GPI=-1
G0=0
PI=1
TMP1=2
TMP2=3
TMP3=4

def add_to_stack():
    """
    STARTS AT  stack temp
    USES       stack temp
    """
    return [
        MOV(0, -1),  # move value on to end of stack
        SHF(-1),  # move onto end of stack
        ADD(-1),  # since stack is initially 1, get value to stack temp value
        SHF(-1),  # set up execution
        # loop does the following:
        # 4>1 1 0 5 becomes 1 4>1 0 5
        # 1 4>1 0 5 becomes 1 1 4>0 5
        LOOP(
            ADD(-1),  # decrement empty stack (1 -> 0)
            MOV(1, 0),  # curry value from last cell to this cell
            SHF(1),  # go back to old cell
            ADD(1),  # restore stack state (0 -> 1)
            SHF(-2),  # go to cell after curried value
        ),  # we see a zero
        MOV(1, 0),  # move curried value into this cell
        SHF(2),  # go back onto a 1
        # then we go back until we see a 0, which should be stack temp
        LOOP(SHF(1)),
    ]


def pop_from_stack():
    """
    STARTS AT  stack temp
    USES       stack temp
    """
    return [
        SHF(-1),  # move onto stack
        LOOP(SHF(-1)),  # go until stack head
        MOV(-1, 0),  # move top of stack into previous cell
        SHF(1),  # set up for loop
        # loop does the following:
        # 0 1>1 4 0 5 becomes  0>1 4 1 0 5
        # 0>1 4 1 0 5 becomes >0 4 1 1 0 5
        LOOP(
            ADD(-1),  # decrement empty stack (1 -> 0)
            MOV(-1, 0),  # curry value from last cell to this cell
            SHF(-1),  # go back to old cell
            ADD(1),  # restore stack state (0 -> 1)
            SHF(2),  # go to cell before curried value
        ),
        MOV(-1, 0),  # move value into stack temp
        SHF(-1),  # move into top of stack
        ADD(1),  # reset to empty stack state (0 -> 1)
        SHF(1),  # move bcak into stack temp
    ]


def if_eq_then(comp, *instr):
    """
    STARTS AT  program input
    USES       tmp1 (2), tmp2 (3)
    *instr must start at <0> and end at <0>
    """
    return [
        ADD(-ord(comp)),  # subtract to maybe zero
        # if it's not zero, subtract 1 from tmp1 (tmp2 is zero)
        COPY(*off(PI, PI, TMP1, TMP2)),  # save value in temp2
        LOOP(SHF(1), ADD(-1), SHF(-1), ZERO()),
        MOV(*off(PI, TMP2, PI)),
        # add 1 to tmp1, it will now be 1 if eq, 0 if not
        SHF(*off(PI, TMP1)),
        ADD(1),
        MOV(*off(TMP1, TMP1, G0)),  # move into 0
        SHF(*off(TMP1, G0)),  # go to 0
        LOOP(
            ZERO(),
            *instr,  # instruction must start and end at 0
        ),
        SHF(*off(G0, PI)),  # go back to program input
        ADD(ord(comp)),  # restore original program input
    ]


def begin_loop(arch, cell_bytes):
    """
    STARTS AT <0>
    USES      tmp1, tmp2, tmp3
    ENDS AT   <0>
    """
    if arch == "bf":
        return "["

    dp = DP[arch]
    body = {
        "x86": f"    cmp {addrmode(cell_bytes)} [{dp}], 0\n    je e",
        "arm": "unimplemented",
    }
    return [
        SHF(*off(G0, GPI)),  # go to global parenthesis index
        # bump it (this allows it to start at 0, since 0 isn't allowed on the stack)
        ADD(1),  
        COPY(*off(GPI, GPI, TMP1, ST)),
        SHF(*off(GPI, ST)),  # move to stack temp, as per add_to_stack calling convention
        *add_to_stack(),  # add it to the stack
        SHF(*off(ST, TMP1)), # move into TMP1
        OUT_S("s"),
        OUT_N("a", *off(TMP1, GPI, TMP1, TMP2, TMP3)),
        OUT_S(":\n" + body[arch]),  # emit end of label
        OUT_N("a", *off(TMP1, GPI, TMP1, TMP2, TMP3)),
        OUT_S("\n"),  # move to next line
        SHF(*off(TMP1, G0)),  # end back at index 0
    ]


def end_loop(arch, cell_bytes):
    """
    STARTS AT <0>
    USES      tmp1, tmp2
    ENDS AT   <0>
    """
    if arch == "bf":
        return "]"

    dp = DP[arch]
    body = {
        "x86": f"    cmp {addrmode(cell_bytes)} [{dp}], 0\n    jne s",
        "arm": "unimplemented",
    }
    return [
        SHF(*off(G0, ST)),  # go to stack temp
        *pop_from_stack(),  # pop from the stack
        SHF(*off(ST, TMP1)),
        OUT_S("e"),
        OUT_N("a", *off(TMP1, ST, TMP1, TMP2, TMP3)),
        OUT_S(":\n" + body[arch]),  # emit end of label
        OUT_N("a", *off(TMP1, ST, TMP1, TMP2, TMP3)),
        OUT_S("\n"),  # move to next line
        SHF(*off(TMP1, ST)),
        ZERO(),
        SHF(*off(ST, G0))
    ]


def EMIT_INCREMENT_DP(arch, cell_bytes):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": f"    add {dp}, {cell_bytes}\n",
            "arm": f"    addi {dp}, {dp}, #{cell_bytes}\n",
            "bf": ">",
        }[arch]
    )


def EMIT_DECREMENT_DP(arch, cell_bytes):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": f"    sub {dp}, {cell_bytes}\n",
            "arm": f"    subi {dp}, {dp}, #{cell_bytes}\n",
            "bf": "<",
        }[arch]
    )


def addrmode(cell_bytes):
    match cell_bytes:
        case 1:
            return "byte"
        case 2:
            return "word"
        case 4:
            return "dword"
        case 8:
            return "qword"


def EMIT_INCREMENT_TAPE(arch, cell_bytes):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": f"    add {addrmode(cell_bytes)} [{dp}], 1\n",
            "arm": "unimplemented",
            "bf": "+",
        }[arch]
    )


def EMIT_DECREMENT_TAPE(arch, cell_bytes):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": f"    sub {addrmode(cell_bytes)} [{dp}], 1\n",
            "arm": "unimplemented",
            "bf": "+",
        }[arch]
    )


def EMIT_OUTPUT(arch):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": f"""\
    mov rdi, 1      ; fd    = stdout
    lea rsi, [{dp}] ; buf   = tape[dp]
    mov rdx, 1      ; count = 1
    mov rax, 1      ; call  = sys_write
    syscall
""",
            "arm": "unimplemented",
            "bf": ".",
        }[arch]
    )


def EMIT_INPUT(arch):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": f"""\
    mov rdi, 0      ; fd    = stdin
    lea rsi, [{dp}] ; buf   = tape[dp]
    mov rdx, 1      ; count = 1
    mov rax, 0      ; call  = sys_read
    syscall
""",
            "arm": "unimplemented",
            "bf": ",",
        }[arch]
    )


def EMIT_HEADER(arch, tape_bytes):
    dp = DP[arch]
    return OUT_S(
        {
            "x86": textwrap.dedent(f"""\
                global _start
                section .text
                _start:
                    mov {dp}, rsp
                    mov rcx, {tape_bytes // 8 + 1}
                .zeroize_stack:
                    mov qword [rsp], 0
                    sub rsp, 8
                    dec rcx
                    jnz .zeroize_stack
                .done:
                    mov rsp, {dp}
                """)
        }[arch]
    )


def init_stack(stack_size):
    """
    STARTS AT: stack end
    ENDS AT: <0>
    """
    return [
        SHF(1),
        *[
            ADD(1),
            SHF(1),
        ]
        * stack_size,
        SHF(2)
    ]


def EMIT_FOOTER(arch):
    return OUT_S(
        {
            "x86": """\
    mov rax, 60
    mov rdi, 0
    syscall"""
        }[arch]
    )


def compile(arch="x86", tape_size="30000", cell_bytes="1", stack_size="255"):
    tape_size = int(tape_size)
    cell_bytes = int(cell_bytes)
    stack_size = int(stack_size)
    return [
        EMIT_HEADER(arch, tape_size * cell_bytes),
        *init_stack(stack_size),
        SHF(1),  # move to program_in
        IN(),  # get in
        LOOP(  # main loop, switch on all possible inputs
            *if_eq_then(">", EMIT_INCREMENT_DP(arch, cell_bytes)),
            *if_eq_then("<", EMIT_DECREMENT_DP(arch, cell_bytes)),
            *if_eq_then("+", EMIT_INCREMENT_TAPE(arch, cell_bytes)),
            *if_eq_then("-", EMIT_DECREMENT_TAPE(arch, cell_bytes)),
            *if_eq_then(".", EMIT_OUTPUT(arch)),
            *if_eq_then(",", EMIT_INPUT(arch)),
            *if_eq_then("[", *begin_loop(arch, cell_bytes)),
            *if_eq_then("]", *end_loop(arch, cell_bytes)),
            IN(),
        ),
        EMIT_FOOTER(arch),
    ]