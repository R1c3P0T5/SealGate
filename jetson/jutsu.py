"""SignFilter extracted from github.com/yuto0226/hand_sign/jutsu.py.

Jetson only needs SignFilter for per-frame debounce; FSM judgment runs on the backend.
"""
from __future__ import annotations

SIGN_CLASSES = ["ne", "ushi", "tora", "u", "tatsu", "mi", "uma", "hitsuji", "saru", "tori", "inu", "i"]


class SignFilter:
    """Debounces per-frame classifier output into confirmed sign events.

    Emits a sign (romaji str) when the same sign is held for hold_ms.
    Resets immediately on sign change or unknown prediction.
    """

    def __init__(self, hold_ms: float = 500) -> None:
        self.hold_ms = hold_ms
        self._current: str | None = None
        self._since: float = 0.0

    def update(self, pred_idx: int, classes: list[str], now: float) -> str | None:
        if pred_idx == -1:
            self._current = None
            return None
        sign = classes[pred_idx]
        if sign != self._current:
            self._current = sign
            self._since = now
            return None
        if (now - self._since) * 1000 >= self.hold_ms:
            self._current = None
            return sign
        return None

    def reset(self) -> None:
        self._current = None
