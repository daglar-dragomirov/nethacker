"""Observed hunger faint clock: eat.c duration and allmain.c immobilized game turns.

The estimate is a proxy, not hidden nutrition. No hero-speed multiplier applies
to negative multi. Unknown or interrupted endpoints do not become measurements.
"""

class FaintClock:
    START = 'You faint from lack of food'
    END = 'You regain consciousness'
    INTERRUPTS = ('You can move again', 'You revive.', 'You fall asleep',
                  'You are put to sleep', 'You are conscious again')

    def __init__(self):
        self.start = None
        self.pending = None

    def reset(self):
        self.start = None
        self.pending = None

    def note(self, message, turn):
        started, ended = self.START in message, self.END in message
        if any(s in message for s in self.INTERRUPTS):
            self.start = None
        if started and ended:
            # A combined screen supplies no separate start timestamp.
            self.start = None
            return
        if started:
            if self.start is None:
                self.start = turn
            elif turn != self.start:
                # A second distinct start without the matching end is ambiguous.
                self.start = None
        elif ended:
            if self.start is not None:
                elapsed = turn - self.start
                # minimum nomul duration is10; the start turn may already count.
                if elapsed >= 9:
                    self.pending = (turn, min(0, (10 - elapsed) * 10))
            self.start = None

    def consume(self, turn):
        if self.pending is None or self.pending[0] > turn:
            return None
        measured, self.pending = self.pending, None
        return measured
