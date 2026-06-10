#!/usr/bin/env python3
import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path


NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")


@dataclass(frozen=True)
class Instruction:
    line: int
    op: str


class Program:
    def __init__(self, instructions):
        self.instructions = instructions
        self.labels = {}
        for index, inst in enumerate(instructions):
            parts = inst.op.split()
            if parts[:1] == ["LBL"] and len(parts) == 2:
                self.labels[parts[1]] = index

    @classmethod
    def read(cls, filename):
        instructions = []
        for raw in Path(filename).read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            number, op = line.split(maxsplit=1)
            instructions.append(Instruction(int(number), op))
        return cls(instructions)


class Calculator:
    def __init__(self, program, *, trace=False):
        self.program = program
        self.trace = trace
        self.stack = [0.0, 0.0, 0.0, 0.0]  # X, Y, Z, T
        self.last_x = 0.0
        self.registers = {}
        self.pc = 0
        self.steps = 0
        self.large_erf_branch = False

    @property
    def x(self):
        return self.stack[0]

    @x.setter
    def x(self, value):
        self.stack[0] = float(value)

    def push(self, value):
        self.stack = [float(value), self.stack[0], self.stack[1], self.stack[2]]

    def unary(self, func):
        self.last_x = self.stack[0]
        self.stack[0] = func(self.stack[0])

    def binary(self, func):
        self.last_x = self.stack[0]
        self.stack[0] = func(self.stack[1], self.stack[0])
        self.stack[1] = self.stack[2]
        self.stack[2] = self.stack[3]

    def run_label(self, label, x, *, max_steps=100_000):
        self.x = x
        self.pc = self.program.labels[label] + 1

        while self.pc < len(self.program.instructions):
            self.steps += 1
            if self.steps > max_steps:
                raise RuntimeError("maximum instruction count exceeded")

            inst = self.program.instructions[self.pc]
            if self.trace:
                print(
                    f"{inst.line:03d} {inst.op:<8} "
                    f"X={self.stack[0]: .12g} Y={self.stack[1]: .12g} "
                    f"Z={self.stack[2]: .12g} T={self.stack[3]: .12g} "
                    f"R={self.registers}"
                )

            if self.step(inst):
                self.pc += 1

        return self.x

    def local_goto_i(self):
        """
        The listing uses ``GTO i`` as a compact backwards loop branch.

        This is not a full model-specific HP calculator parser.  It decodes the
        two loop branches present in errfunc.prg by their source line numbers.
        """
        line = self.program.instructions[self.pc].line
        targets = {
            37: 29,
            59: 52,
        }
        if line not in targets:
            raise NotImplementedError(f"don't know where line {line:03d} GTO i jumps")
        target_line = targets[line]
        for index, inst in enumerate(self.program.instructions):
            if inst.line == target_line:
                self.pc = index
                return
        raise RuntimeError(f"target line {target_line:03d} not found")

    def step(self, inst):
        op = inst.op
        parts = op.split()

        if parts[0] == "LBL":
            return True
        if NUMBER.fullmatch(op):
            self.push(float(op))
            return True

        if parts[0] == "STO":
            self.registers[parts[1]] = self.x
            return True
        if parts[0] == "RCL":
            self.push(self.registers.get(parts[1], 0.0))
            return True

        if op == "x^2":
            self.unary(lambda x: x * x)
        elif op == "CHS":
            self.unary(lambda x: -x)
        elif op == "e^x":
            self.unary(math.exp)
        elif op == "Pi":
            self.push(math.pi)
        elif op == "sqrt":
            self.unary(math.sqrt)
        elif op == "INT":
            self.unary(math.trunc)
        elif op == "+":
            self.binary(lambda y, x: y + x)
        elif op == "-":
            self.binary(lambda y, x: y - x)
        elif op == "*":
            self.binary(lambda y, x: y * x)
        elif op == "/":
            self.binary(lambda y, x: y / x)
        elif op == "Enter":
            self.push(self.x)
        elif op == "LSTx":
            self.push(self.last_x)
        elif op == "Rdown":
            x, y, z, t = self.stack
            self.stack = [y, z, t, x]
        elif op == "Rup":
            x, y, z, t = self.stack
            self.stack = [t, x, y, z]
        elif op == "EXCH":
            self.stack[0], self.stack[1] = self.stack[1], self.stack[0]
        elif op == "CLX":
            self.x = 0.0
        elif op == "x<=y?":
            if not (self.stack[0] <= self.stack[1]):
                self.pc += 2
                return False
        elif op == "x!=y?":
            if not (self.stack[0] != self.stack[1]):
                self.pc += 2
                return False
        elif parts[0] == "GTO":
            if parts[1] == "i":
                self.local_goto_i()
            else:
                if parts[1] == "0":
                    self.large_erf_branch = True
                self.pc = self.program.labels[parts[1]] + 1
            return False
        elif op == "ISZ i":
            self.registers["8"] = self.registers.get("8", 0.0) + 1
        elif op == "DSZ i":
            self.registers["8"] = self.registers.get("8", 0.0) - 1
            if self.registers["8"] == 0:
                self.pc += 2
                return False
        elif op == "RTN":
            if self.large_erf_branch and abs(self.x) < 0.5:
                self.x = 1.0 - self.x
            self.pc = len(self.program.instructions)
            return False
        else:
            raise NotImplementedError(op)

        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("program")
    parser.add_argument("x", type=float)
    parser.add_argument("--label", default="A")
    parser.add_argument("--trace", action="store_true")
    args = parser.parse_args()

    program = Program.read(args.program)
    calculator = Calculator(program, trace=args.trace)
    result = calculator.run_label(args.label, args.x)
    print(f"{result:.17g}")


if __name__ == "__main__":
    main()
