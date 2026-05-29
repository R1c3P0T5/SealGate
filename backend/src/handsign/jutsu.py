"""JutsuFSM and SignFilter extracted from github.com/yuto0226/hand_sign/jutsu.py.

draw_jutsu() and all PIL/cv2/numpy rendering helpers are intentionally omitted
— the frontend handles overlay drawing.
"""

from __future__ import annotations

from collections.abc import Callable

SIGN_KANJI: dict[str, str] = {
    "ne": "子",
    "ushi": "丑",
    "tora": "寅",
    "u": "卯",
    "tatsu": "辰",
    "mi": "巳",
    "uma": "午",
    "hitsuji": "未",
    "saru": "申",
    "tori": "酉",
    "inu": "戌",
    "i": "亥",
}


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
            self._current = None  # reset so it must be re-held
            return sign
        return None

    def reset(self) -> None:
        self._current = None


class JutsuFSM:
    """Matches a stream of confirmed signs against jutsu sequences.

    Tracks per-jutsu progress. Resets a jutsu's progress on wrong sign
    or when gap_ms elapses since the last confirmed sign for that jutsu.

    jutsu dict values must be kanji sequences (e.g. ["亥", "寅"]).
    feed() accepts romaji signs and converts them via SIGN_KANJI.

    on_complete fires only when a full sequence is recognised AND the
    global cooldown has elapsed. It never fires on partial progress.
    """

    def __init__(
        self,
        on_complete: Callable[[str], None],
        jutsu: dict[str, list[str]],
        gap_ms: float = 3000,
        cooldown_ms: float = 5000,
    ) -> None:
        self.jutsu = jutsu
        self.gap_ms = gap_ms
        self.cooldown_ms = cooldown_ms
        self.on_complete = on_complete
        self._step: dict[str, int] = {name: 0 for name in jutsu}
        # Timestamp of the last sign that advanced each jutsu's step counter.
        # Used to expire stale progress after gap_ms of inactivity.
        self._last_step_at: dict[str, float] = {name: 0.0 for name in jutsu}
        self._fired_at: float = -cooldown_ms  # allow immediate first fire
        self._last_sign: str | None = None

    def feed(self, sign: str, now: float) -> None:
        if sign == self._last_sign:
            return
        self._last_sign = sign
        kanji = SIGN_KANJI.get(sign)
        if kanji is None:
            return
        newly_completed: list[str] = []
        for name, seq in self.jutsu.items():
            if (
                self._step[name] > 0
                and (now - self._last_step_at[name]) * 1000 > self.gap_ms
            ):
                self._step[name] = 0
            step = self._step[name]
            if kanji == seq[step]:
                self._step[name] += 1
                self._last_step_at[name] = now
                if self._step[name] == len(seq):
                    self._step[name] = 0
                    newly_completed.append(name)
            else:
                self._step[name] = 0
        if newly_completed and (now - self._fired_at) * 1000 >= self.cooldown_ms:
            winner = max(newly_completed, key=lambda n: len(self.jutsu[n]))
            self._fired_at = now
            self.reset()
            self.on_complete(winner)

    def reset(self) -> None:
        for name in self._step:
            self._step[name] = 0
        self._last_sign = None

    def leading_jutsu(self) -> tuple[str, int, int] | None:
        """Return (name, step, total) for the jutsu with the most progress."""
        if not self._step:
            return None
        best_name = max(self._step, key=self._step.__getitem__)
        if self._step[best_name] == 0:
            return None
        return (best_name, self._step[best_name], len(self.jutsu[best_name]))
