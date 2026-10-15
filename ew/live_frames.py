"""Bounded samples of actual environment states for the public run viewer."""
import json
import time
from collections import deque

from .agent_sessions import _save


class FrameWriter:
    def __init__(self, path, interval=0.15, clock=time.monotonic):
        self.path, self.interval, self.clock = path, interval, clock
        self.frames = deque(maxlen=32)
        self.pending = None
        self.sequence, self.last, self.phase_key = 0, float('-inf'), None

    def observer(self, phase, suite=None):
        def emit(sample):
            self.pending = (phase, suite, sample)
            now = self.clock()
            key = (phase, suite)
            if key == self.phase_key and now - self.last < self.interval:
                return
            self.sequence += 1
            # Copy layout and state, because the simulator keeps advancing after this call.
            self.frames.append(json.loads(json.dumps({**sample, 'seq': self.sequence,
                'phase': phase, 'suite': suite, 'sampled_at': time.time()})))
            self.last, self.phase_key = now, key
            _save(self.path, {'latest': self.sequence, 'frames': list(self.frames)})
        return emit

    def flush(self):
        if self.pending:
            phase, suite, sample = self.pending
            self.last = float('-inf')
            self.observer(phase, suite)(sample)
