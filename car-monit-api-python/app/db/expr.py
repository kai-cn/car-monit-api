# -*- coding: utf-8 -*-
"""OGNL subset used by MyBatis ``<if test="...">``.

Migrated from: org.apache.ibatis.scripting.xmltags.IfSqlNode
                (expressions are evaluated by OGNL at run time)

The 23 mapper XMLs only use a small, well-defined subset:

    id != null  and  id != ''
    type != null
    flag == 'jiandong'
    carNoList != null and carNoList.size() > 0

Instead of ``eval()`` -- which would execute arbitrary Python embedded in an
XML file -- this module implements a small recursive-descent evaluator with
exactly OGNL's semantics for those constructs:

* ``null`` -> ``None``, ``==`` on strings compares values (OGNL uses
  ``equals`` for non-numeric operands);
* a missing property yields ``null`` (OGNL returns null for a missing map key
  and MyBatis swallows the reflection error for beans);
* ``.size()`` / ``.length()`` / ``.isEmpty()`` / ``.contains()`` /
  ``.equals()`` / ``.toString()`` are supported on any value.
"""
from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any, Callable, Mapping, Optional

log = logging.getLogger(__name__)

__all__ = ["evaluate", "ExprError"]

_TOKEN_RE = re.compile(
    r"""
      (?P<space>\s+)
    | (?P<number>\d+\.\d+|\d+)
    | (?P<string>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
    | (?P<op><=|>=|==|!=|&&|\|\||[<>!()+\-.,\[\]])
    | (?P<ident>[A-Za-z_$][\w$]*)
    """,
    re.VERBOSE,
)


class ExprError(ValueError):
    """Raised when the XML contains an expression this evaluator cannot parse."""


def _tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        match = _TOKEN_RE.match(text, index)
        if not match:
            raise ExprError(f"unexpected character {text[index]!r} in {text!r}")
        index = match.end()
        kind = match.lastgroup or ""
        if kind == "space":
            continue
        tokens.append((kind, match.group()))
    tokens.append(("eof", ""))
    return tokens


class _Parser:
    def __init__(self, text: str, resolver: Callable[[str], Any]) -> None:
        self._tokens = _tokenize(text)
        self._position = 0
        self._resolver = resolver

    # ------------------------------------------------------------------ cursor
    def _peek(self) -> tuple[str, str]:
        return self._tokens[self._position]

    def _advance(self) -> tuple[str, str]:
        token = self._tokens[self._position]
        self._position += 1
        return token

    def _accept(self, value: str) -> bool:
        if self._peek()[1] == value and self._peek()[0] in ("op", "ident"):
            self._advance()
            return True
        return False

    def _expect(self, value: str) -> None:
        token = self._advance()
        if token[1] != value:
            raise ExprError(f"expected {value!r} but found {token[1]!r}")

    # ------------------------------------------------------------------ grammar
    def parse(self) -> Any:
        value = self._parse_or(True)
        if self._peek()[0] != "eof":
            raise ExprError(f"unexpected token {self._peek()[1]!r}")
        return value

    def _parse_or(self, flag: bool) -> Any:
        value = self._parse_and(flag)
        while self._accept("or") or self._accept("||"):
            right = self._parse_and(flag and not _truthy(value))
            if flag:
                value = _truthy(value) or _truthy(right)
        return value

    def _parse_and(self, flag: bool) -> Any:
        value = self._parse_not(flag)
        while self._accept("and") or self._accept("&&"):
            right = self._parse_not(flag and _truthy(value))
            if flag:
                value = _truthy(value) and _truthy(right)
        return value

    def _parse_not(self, flag: bool) -> Any:
        if self._accept("not") or self._accept("!"):
            value = self._parse_not(flag)
            return (not _truthy(value)) if flag else None
        return self._parse_comparison(flag)

    def _parse_comparison(self, flag: bool) -> Any:
        left = self._parse_additive(flag)
        for operator in ("==", "!=", "<=", ">=", "<", ">"):
            if self._peek() == ("op", operator):
                self._advance()
                right = self._parse_additive(flag)
                if flag:
                    return _compare(operator, left, right)
                return None
        return left

    def _parse_additive(self, flag: bool) -> Any:
        value = self._parse_postfix(flag)
        while self._peek() in (("op", "+"), ("op", "-")):
            operator = self._advance()[1]
            right = self._parse_postfix(flag)
            if flag:
                try:
                    value = value + right if operator == "+" else value - right
                except TypeError:
                    value = None
        return value

    def _parse_postfix(self, flag: bool) -> Any:
        value = self._parse_primary(flag)
        while True:
            if self._peek() == ("op", "."):
                self._advance()
                name = self._advance()[1]
                if self._peek() == ("op", "("):
                    arguments = self._parse_arguments(flag)
                    if flag:
                        value = _call_method(value, name, arguments)
                elif flag:
                    value = _get_property(value, name)
            elif self._peek() == ("op", "["):
                self._advance()
                index = self._parse_or(flag)
                self._expect("]")
                if flag:
                    try:
                        value = value[index]
                    except (TypeError, KeyError, IndexError):
                        value = None
            else:
                return value

    def _parse_arguments(self, flag: bool) -> list[Any]:
        self._expect("(")
        arguments: list[Any] = []
        if self._peek() != ("op", ")"):
            while True:
                arguments.append(self._parse_or(flag))
                if not self._accept(","):
                    break
        self._expect(")")
        return arguments

    def _parse_primary(self, flag: bool) -> Any:
        kind, value = self._advance()
        if kind == "number":
            return float(value) if "." in value else int(value)
        if kind == "string":
            return _unquote(value)
        if kind == "ident":
            if value == "null":
                return None
            if value == "true":
                return True
            if value == "false":
                return False
            if value == "empty":
                return None
            return self._resolver(value) if flag else None
        if (kind, value) == ("op", "("):
            result = self._parse_or(flag)
            self._expect(")")
            return result
        raise ExprError(f"unexpected token {value!r}")


def _unquote(text: str) -> str:
    quote_char = text[0]
    body = text[1:-1]
    return body.replace("\\" + quote_char, quote_char).replace("\\\\", "\\")


def _truthy(value: Any) -> bool:
    """OGNL boolean coercion: null is false, empty string/collection is false."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, (str, list, tuple, dict, set)):
        return len(value) > 0
    return True


def _compare(operator: str, left: Any, right: Any) -> bool:
    if operator == "==":
        return _equals(left, right)
    if operator == "!=":
        return not _equals(left, right)
    if left is None or right is None:
        return False
    try:
        if operator == "<":
            return left < right
        if operator == "<=":
            return left <= right
        if operator == ">":
            return left > right
        return left >= right
    except TypeError:
        # Java would throw; returning false keeps a single bad XML row from
        # breaking the whole statement. No XML in this project hits this path.
        log.debug("incomparable operands %r %s %r", left, operator, right)
        return False


def _equals(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


def _get_property(target: Any, name: str) -> Any:
    if target is None:
        return None
    if isinstance(target, Mapping):
        if name in target:
            return target[name]
        lowered = {str(key).lower(): value for key, value in target.items()}
        return lowered.get(name.lower())
    if dataclasses.is_dataclass(target) and not isinstance(target, type):
        from com.ruoyi.common.core.domain.JavaBean import _resolve_field

        field = _resolve_field(type(target), name)
        return getattr(target, field) if field else None
    try:
        value = getattr(target, name)
    except AttributeError:
        pass
    else:
        # ``JavaBean`` hands out ``getXxx``/``isXxx`` as methods (Java semantics);
        # OGNL evaluates the property, it never tests the method object itself.
        return value() if callable(value) else value
    getter = f"get{name[:1].upper()}{name[1:]}"
    accessor = getattr(target, getter, None)
    if callable(accessor):
        try:
            return accessor()
        except Exception:  # noqa: BLE001 - a broken getter behaves like null
            return None
    return None


def _call_method(target: Any, name: str, arguments: list[Any]) -> Any:
    if name in ("size", "length"):
        return 0 if target is None else len(target)
    if name == "isEmpty":
        return target is None or len(target) == 0
    if name == "contains":
        try:
            return arguments[0] in target
        except TypeError:
            return False
    if name == "equals":
        return _equals(target, arguments[0] if arguments else None)
    if name == "toString":
        return "" if target is None else str(target)
    if name == "indexOf":
        try:
            return target.index(arguments[0])
        except (ValueError, TypeError):
            return -1
    if name in ("intValue", "longValue"):
        try:
            return int(target)
        except (TypeError, ValueError):
            return 0
    if name in ("doubleValue", "floatValue"):
        try:
            return float(target)
        except (TypeError, ValueError):
            return 0.0
    if name == "get":
        try:
            return target.get(arguments[0])
        except (AttributeError, TypeError, IndexError):
            return None
    if name == "startsWith":
        return str(target).startswith(str(arguments[0]))
    if name == "endsWith":
        return str(target).endswith(str(arguments[0]))
    if name == "toUpperCase":
        return str(target).upper()
    if name == "toLowerCase":
        return str(target).lower()
    if name == "trim":
        return str(target).strip()
    if name == "matches":
        return bool(re.fullmatch(str(arguments[0]), str(target)))
    log.debug("unsupported OGNL method .%s() on %r", name, type(target).__name__)
    return None


def evaluate(expression: Optional[str], resolver: Callable[[str], Any]) -> bool:
    """Evaluate a MyBatis ``test`` expression.

    ``resolver(name)`` resolves a property of the current parameter object.
    """
    text = (expression or "").strip()
    if not text:
        # MyBatis treats an empty test as "always true"
        return True
    try:
        return _truthy(_Parser(text, resolver).parse())
    except ExprError:
        log.error("cannot evaluate MyBatis test expression: %s", expression)
        raise
