"""Bounded early equipment tour, with the parent strategy as its fallback.

Experimental strategy by daglar-dragomirov on the complete v10c lineage.
This prepares resources through the existing Mines/Minetown/Sokoban tour;
it does not assert quest eligibility or change the specialist router.
"""
from .glyph import Hunger

NURSERY_XL = 5
NURSERY_BUDGET = 8000
TOUR_BUDGET = 12000


class PreparationTour:
    def __init__(self, global_logic):
        self.gl = global_logic
        self.phase = 'nursery'
        self.nursery_started = None
        self.tour_started = None

    @property
    def active(self):
        return self.phase == 'tour'

    def _finish(self, reason, *, reset_milestone):
        if self.phase == 'done':
            return
        self.phase = 'done'
        if reset_milestone:
            self.gl.milestone = type(self.gl.milestone).BE_ON_FIRST_LEVEL
        self.gl.agent.log('PREPARATION tour finished: ' + reason)

    def hold_dive(self):
        """Hold ordinary dive triggers, without calling their state-mutating implementation."""
        if self.phase == 'done':
            return False
        agent = self.gl.agent
        bl = agent.blstats
        milestone = type(self.gl.milestone)
        # Hand the original rescue/late-rescue code its original milestone.
        # Do not turn a side-branch emergency into a new preparation attempt.
        if agent.prayer_failed and (
                self.gl.milestone == milestone.BE_ON_FIRST_LEVEL or
                (bl.hunger_state >= Hunger.WEAK and not agent.edible_carried_food())):
            self._finish('parent rescue', reset_milestone=False)
            return False
        if self.phase == 'nursery':
            if self.nursery_started is None:
                self.nursery_started = bl.time
            if bl.time - self.nursery_started >= NURSERY_BUDGET:
                self._finish('nursery budget', reset_milestone=False)
                return False
            return True
        if self.gl.milestone >= milestone.FIND_MINES_END:
            # Sokoban has completed or its existing stall handling skipped it.
            # The parent's food/HP/prayer and XP/tool checks choose what follows.
            self._finish('equipment tour complete', reset_milestone=True)
            return False
        if bl.time - self.tour_started >= TOUR_BUDGET:
            self._finish('equipment tour budget', reset_milestone=True)
            return False
        return True

    def nursery_done(self):
        """None delegates to the parent's original nursery condition after fallback."""
        if self.phase == 'done':
            return None
        if self.phase == 'tour':
            return True
        agent = self.gl.agent
        dive = self.gl.dive
        if agent.blstats.experience_level < NURSERY_XL:
            return False
        # Keep the parent's feeding, emergency-prayer and health gates.
        if not (dive.fed_for_dive() and dive.prayer_ready_for_dive() and dive.hp_ready_for_dive()):
            return False
        self.phase = 'tour'
        self.tour_started = agent.blstats.time
        agent.log('PREPARATION early equipment tour starts')
        return True
