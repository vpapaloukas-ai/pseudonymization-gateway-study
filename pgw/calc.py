"""Step 6 (spec §4): calculations happen locally. The model writes {SUM: [AMOUNT_1], [AMOUNT_2], ...} or
{DIFF: [AMOUNT_1], [AMOUNT_2]}; the gateway computes the figure from the vault, so the model never sees one
and the figure is exact."""
import re

from pgw.crm import money
from pgw.vault import Vault

BRACES = re.compile(r"\{[^{}]*\}")
SUM = re.compile(r"\{\s*SUM\s*:\s*\[AMOUNT_\d+\](?:\s*,\s*\[AMOUNT_\d+\])+\s*\}")
DIFF = re.compile(r"\{\s*DIFF\s*:\s*\[AMOUNT_\d+\]\s*,\s*\[AMOUNT_\d+\]\s*\}")
OPERAND = re.compile(r"\[AMOUNT_\d+\]")


def pence(figure: str) -> int:
    m = re.fullmatch(r"£\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?", figure.strip())
    if not m:
        raise ValueError(f"not a £ figure: {figure!r}")
    return int(m.group(1).replace(",", "")) * 100 + int(m.group(2) or 0)


def apply(text: str, vault: Vault) -> tuple[str, list[str], list[str]]:
    """Replace each valid expression with its figure. Returns (text, figures written, bad expressions)."""
    figures: list[str] = []
    bad: list[str] = []

    def one(m: re.Match) -> str:
        expr = m.group(0)
        is_sum, is_diff = bool(SUM.fullmatch(expr)), bool(DIFF.fullmatch(expr))
        values = [vault.value(t) for t in OPERAND.findall(expr)]
        try:
            nums = [pence(v) for v in values] if (is_sum or is_diff) and None not in values else None
        except ValueError:
            nums = None
        result = None if nums is None else (sum(nums) if is_sum else nums[0] - nums[1])
        if result is None or result < 0:
            bad.append(expr)
            return expr
        figures.append(money(result))
        return money(result)

    return BRACES.sub(one, text), figures, bad
