"""The local token-to-value map. It never leaves the perimeter; it is the key that keeps the data personal."""
import re

TOKEN_RE = re.compile(r"\[([A-Z][A-Z_]*)_(\d+)\]")


class Vault:
    def __init__(self) -> None:
        self._by_value: dict[tuple[str, str], str] = {}
        self._by_token: dict[str, str] = {}
        self._counts: dict[str, int] = {}

    def token(self, entity_type: str, value: str) -> str:
        key = (entity_type, value)
        if key not in self._by_value:
            n = self._counts.get(entity_type, 0) + 1
            self._counts[entity_type] = n
            tok = f"[{entity_type}_{n}]"
            self._by_value[key] = tok
            self._by_token[tok] = value
        return self._by_value[key]

    def value(self, token: str) -> str | None:
        return self._by_token.get(token)

    def tokens(self) -> dict[str, str]:
        return dict(self._by_token)

    def to_json(self) -> dict:
        return {"keys": [[e, val, tok] for (e, val), tok in self._by_value.items()]}

    @classmethod
    def from_json(cls, data: dict) -> "Vault":
        v = cls()
        for e, val, tok in data["keys"]:
            v._by_value[(e, val)] = tok
            v._by_token[tok] = val
            v._counts[e] = max(v._counts.get(e, 0), int(TOKEN_RE.fullmatch(tok).group(2)))
        return v


def restore(text: str, vault: Vault) -> str:
    return TOKEN_RE.sub(lambda m: vault.value(m.group(0)) or m.group(0), text)
