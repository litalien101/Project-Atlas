"""Small bounded history buffer for server-authoritative hitbox rewind."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, sin
from typing import Deque


@dataclass(frozen=True)
class HitboxSnapshot:
    time: float
    x: float
    y: float
    z: float
    radius: float
    height: float
    yaw: float = 0.0
    sequence: int | None = None


class EntityHistory:
    """Time-ordered hitbox samples, interpolated within a bounded rewind window."""

    def __init__(self, max_seconds: float = 2.0, max_samples: int = 120):
        if max_seconds <= 0 or max_samples < 2:
            raise ValueError("History limits must be positive and allow interpolation.")
        self.max_seconds = max_seconds
        self.samples: Deque[HitboxSnapshot] = deque(maxlen=max_samples)

    def record(self, sample: HitboxSnapshot) -> None:
        values = (sample.time, sample.x, sample.y, sample.z, sample.radius, sample.height, sample.yaw)
        if not all(isfinite(value) for value in values) or sample.radius <= 0 or sample.height <= 0:
            raise ValueError("Hitbox snapshot contains invalid values.")
        if self.samples and sample.time <= self.samples[-1].time:
            raise ValueError("Hitbox snapshots must have strictly increasing timestamps.")
        self.samples.append(sample)
        cutoff = sample.time - self.max_seconds
        while len(self.samples) > 1 and self.samples[1].time < cutoff:
            self.samples.popleft()

    def rewind(self, timestamp: float) -> HitboxSnapshot | None:
        if not isfinite(timestamp) or not self.samples:
            return None
        first, latest = self.samples[0], self.samples[-1]
        if timestamp < first.time or timestamp > latest.time or latest.time - timestamp > self.max_seconds:
            return None
        before = first
        for after in list(self.samples)[1:]:
            if timestamp <= after.time:
                span = after.time - before.time
                alpha = (timestamp - before.time) / span
                yaw_delta = atan2(sin(after.yaw - before.yaw), cos(after.yaw - before.yaw))
                return HitboxSnapshot(
                    timestamp,
                    before.x + (after.x - before.x) * alpha,
                    before.y + (after.y - before.y) * alpha,
                    before.z + (after.z - before.z) * alpha,
                    before.radius + (after.radius - before.radius) * alpha,
                    before.height + (after.height - before.height) * alpha,
                    before.yaw + yaw_delta * alpha,
                )
            before = after
        return latest if timestamp == latest.time else None

    def rewind_sequence(self, sequence: int, now: float, max_age: float = .5) -> HitboxSnapshot | None:
        """Resolve only a server-recorded input sequence within the allowed age."""
        if isinstance(sequence, bool) or not isinstance(sequence, int) or not isfinite(now) or max_age <= 0:
            return None
        for sample in reversed(self.samples):
            if sample.sequence == sequence:
                return sample if 0 <= now - sample.time <= max_age else None
        return None


def validate_melee_hit(origin: tuple[float, float, float], snapshot: HitboxSnapshot,
                       reach: float, attacker_radius: float = 0.0) -> bool:
    """Validate a simple horizontal melee reach and vertical capsule overlap."""
    ox, oy, oz = origin
    if not all(isfinite(value) for value in (*origin, reach, attacker_radius)) or reach < 0 or attacker_radius < 0:
        return False
    horizontal = hypot(ox - snapshot.x, oz - snapshot.z)
    vertical_overlap = oy <= snapshot.y + snapshot.height and oy >= snapshot.y - attacker_radius
    return horizontal <= reach + snapshot.radius + attacker_radius and vertical_overlap
