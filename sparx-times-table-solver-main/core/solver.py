"""Math solver with improved text normalisation.

Improvements over the original:
- Richer OCR-correction table covering common misreads (O→0, I→1, l→1)
- Cleaner regex pipeline that avoids over-stripping valid characters
- Returns equation type metadata so callers can log what kind of problem was solved
- Handles implicit multiplication (3x4) without mangling standalone 'x' variables
"""
import logging
import re
from typing import Optional, Tuple

import sympy

logger = logging.getLogger(__name__)

# Characters that EasyOCR commonly misreads in a maths context
_OCR_MAP = {
    "×": "*",
    "÷": "/",
    ":": "/",
    "?": "x",
    "X": "x",
    "O": "0",
    "I": "1",
    "l": "1",
}

# digit-x-digit (e.g. "3x4" → "3*4") — must run before coefficient-x
_IMPLICIT_MUL_DIGIT = re.compile(r"(\d+)\s*x\s*(\d+)")
# coefficient-x-variable (e.g. "2x+3=7" → "2*x+3=7")
_IMPLICIT_MUL_COEF = re.compile(r"(\d+)\s*x(?!\d)")
# Strips anything that isn't a recognised maths character
_ALLOWED = re.compile(r"[^0-9+\-*/().=x]")
# Collapses spaces around operators
_OP_SPACES = re.compile(r"\s*([+\-*/=()])\s*")


class MathSolver:

    def normalize(self, text: str) -> str:
        text = text.strip()

        # Apply OCR corrections character-by-character first
        for bad, good in _OCR_MAP.items():
            text = text.replace(bad, good)

        # Implicit multiplication before stripping 'x'
        text = _IMPLICIT_MUL_DIGIT.sub(r"\1*\2", text)
        text = _IMPLICIT_MUL_COEF.sub(r"\1*x", text)

        # Remove disallowed characters
        text = _ALLOWED.sub("", text)

        # Tighten spacing around operators
        text = _OP_SPACES.sub(r"\1", text)

        # Balance parentheses
        opens = text.count("(")
        closes = text.count(")")
        if opens > closes:
            text += ")" * (opens - closes)

        return text.strip()

    def solve(self, raw: str) -> Tuple[Optional[str], str]:
        """Return (answer_string, equation_type).

        equation_type is one of: 'expression', 'equation', 'empty', 'unsolvable', 'error'.
        """
        normalized = self.normalize(raw)
        if not normalized:
            return None, "empty"

        try:
            if "=" in normalized:
                lhs_str, rhs_str = normalized.split("=", 1)
                x = sympy.Symbol("x")
                lhs = sympy.sympify(lhs_str)
                rhs = sympy.sympify(rhs_str)
                solutions = sympy.solve(sympy.Eq(lhs, rhs), x)
                if not solutions:
                    return None, "unsolvable"
                result = solutions[0]
                eq_type = "equation"
            else:
                result = sympy.sympify(normalized)
                eq_type = "expression"

            # Format as integer when possible, otherwise 6 d.p.
            if result == int(result):
                return str(int(result)), eq_type
            return f"{float(result):.6f}".rstrip("0").rstrip("."), eq_type

        except Exception as exc:
            logger.warning("Solver failed for %r: %s", normalized, exc)
            return None, "error"
