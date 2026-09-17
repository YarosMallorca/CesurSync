"""Reglas de formato para los títulos que se envían a Google (ver format_rules.example.toml)."""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

TARGETS = {"tasks", "events"}


@dataclass(frozen=True)
class Rule:
    pattern: re.Pattern
    replace: str
    applies_to: frozenset[str]

    def apply(self, text: str) -> str:
        return self.pattern.sub(self.replace, text)


class Formatter:
    def __init__(self, rules: list[Rule]):
        self.rules = rules

    @classmethod
    def from_file(cls, path: str) -> "Formatter":
        """Carga las reglas; si el archivo no existe no se aplica ningún formato."""
        file = Path(path)
        if not file.exists():
            return cls([])

        with file.open("rb") as f:
            data = tomllib.load(f)

        return cls(
            [
                _parse_rule(raw, f"{path}: regla #{i}")
                for i, raw in enumerate(data.get("rules", []), start=1)
            ]
        )

    def apply(self, text: str, target: str) -> str:
        for rule in self.rules:
            if target in rule.applies_to:
                text = rule.apply(text)
        return text


def _parse_rule(raw: dict, where: str) -> Rule:
    if ("find" in raw) == ("pattern" in raw):
        raise ValueError(f"{where}: debe tener 'find' o 'pattern' (solo uno)")
    if "replace" not in raw:
        raise ValueError(f"{where}: falta 'replace'")

    unknown = raw.keys() - {"find", "pattern", "replace", "applies_to", "ignore_case"}
    if unknown:
        raise ValueError(f"{where}: claves desconocidas {sorted(unknown)}")

    applies_to = raw.get("applies_to", TARGETS)
    if isinstance(applies_to, str):
        applies_to = [applies_to]
    applies_to = frozenset(applies_to)
    if not applies_to <= TARGETS:
        raise ValueError(
            f"{where}: 'applies_to' solo admite {sorted(TARGETS)}, "
            f"recibido {sorted(applies_to)}"
        )

    flags = re.IGNORECASE if raw.get("ignore_case") else 0
    replace = raw["replace"]

    if "find" in raw:
        pattern = re.compile(re.escape(raw["find"]), flags)
        # En reemplazos literales las barras invertidas no son especiales
        return Rule(pattern, replace.replace("\\", "\\\\"), applies_to)

    try:
        pattern = re.compile(raw["pattern"], flags)
        _check_replacement(pattern, replace)
    except re.error as e:
        raise ValueError(f"{where}: regex no válida: {e}") from e

    return Rule(pattern, replace, applies_to)


def _check_replacement(pattern: re.Pattern, replace: str):
    """Detecta al cargar referencias a grupos inexistentes (\\3, \\g<nombre>) en 'replace'."""
    names = {index: name for name, index in pattern.groupindex.items()}
    dummy = "".join(
        f"(?P<{names[i]}>)" if i in names else "()"
        for i in range(1, pattern.groups + 1)
    )
    re.match(dummy, "").expand(replace)
