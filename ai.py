"""
AI components
"""
from math import sqrt
from random import randint

from bear_hug.ecs import Component, EntityTracker
from bear_hug.event import BearEvent


class AIComponent(Component):
    """
    A component responsible for wrapping the AI finite state machine.

    It is merely a wrapper without internal logics; its actions each tick are
    as follows:

    1. If the NPC is on the delay, do nothing. Else, proceed.

    2. Call ``switch_state`` method of its current state. If it returns None,
    proceed. Else, switch current state to whatever it returned, then proceed.

    3. Call ``take_action`` method of its current state. That method should
    return a number; set that number as the delay and do not take any actions or
    switch states until that many seconds have passed.

    """

    def __init__(self, *args, states={}, current_state='inactive', **kwargs):
        super().__init__(*args, name='controller', **kwargs)
        self.states = {}
        for state in states:
            self._add_state(state, states[state])
        self.current_state = current_state
        self.delay = 0
        self.have_waited = 0
        self.dispatcher.register_listener(self, 'tick')

    def _add_state(self, state_name, state):
        if not isinstance(state, AIState):
            raise TypeError(
                f'{type(state)} used instead of AIState for AIComponent')
        if state_name in self.states:
            raise ValueError(
                f'Duplicate state name {state_name} in AIComponent')
        state.owner = self.owner
        self.states[state_name] = state

    def on_event(self, event):
        if event.event_type == 'tick':
            self.have_waited += event.event_value
            if self.have_waited < self.delay:
                return
            # First check whether one should switch state
            next_state = self.states[self.current_state].switch_state()
            if next_state:
                if next_state not in self.states:
                    raise ValueError(f'AIComponent attempted to switch to unknown state {next_state}')
                self.current_state = next_state
            # Then take actions
            self.delay = self.states[self.current_state].take_action()
            self.have_waited = 0
    # TODO: __repr__ AIComponent and AIState


class AIState:
    """
    A single state of the AI finite state machine.

    It can address the entity it controls as self.owner, similar to the
    components. Unlike the components, though, it does not add itself to the
    owner's __dict__
    """
    def __init__(self, dispatcher, owner=None):
        self.dispatcher = dispatcher
        self.owner = owner

    def take_action(self):
        """
        Take the appropriate action and return the delay (in seconds) until the
        next action.
        :return:
        """
        raise NotImplementedError('AIState.take_action should be overridden')

    def switch_state(self):
        """
        Check whether the state needs to switch right now.

        Returns None (if it shouldn't) or str (state name)
        :return:
        """
        raise NotImplementedError('AIState.switch_state should be overridden')


################################################################################
# Agressor types: attack everyone with a different faction
################################################################################

def find_closest_enemy(entity, perception_distance):
    enemies = list(EntityTracker().filter_entities(
        lambda x: hasattr(x,'faction') and x.faction.faction != entity.faction.faction))
    current_closest = None
    min_dist = None
    for enemy in enemies:
        dx = entity.position.x - enemy.position.x
        dy = entity.position.y - enemy.position.y
        dist = sqrt(dx ** 2 + dy ** 2)
        if (not min_dist or min_dist > dist) \
                and dist < perception_distance:
            current_closest = enemy
        return current_closest


class AgressorPeacefulState(AIState):
    """
    Switches to AgressorCombatState if there is somebody to attack within
    perception distance.

    Takes no actions
    """
    def __init__(self, *args, perception_distance=150, check_delay=0.1,
                 combat_state = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perception_distance = perception_distance
        self.check_delay = check_delay
        self.combat_state = combat_state

    def switch_state(self):
        current_closest = find_closest_enemy(self.owner,
                                             self.perception_distance)
        if current_closest:
            # Set combat music
            # TODO: some fadeout between this and previous bg
            # Maybe a general thing with bg sound switches?
            self.dispatcher.add_event(BearEvent('set_bg_sound', 'punk_bg'))
            return self.combat_state

    def take_action(self):
        return self.check_delay


class AgressorCombatState(AIState):
    """
    A base class for agressor combat states.

    Switches to a peaceful state when there is nobody to fight, but expects
    child classes to define ``take_action``
    """
    def __init__(self, *args, peaceful_state=None,
                 perception_distance=150, **kwargs):
        super().__init__(*args, **kwargs)
        self.peaceful_state = peaceful_state
        self.perception_distance = perception_distance
        self.current_closest = None

    def switch_state(self):
        """
        Similar to AgressorPeacefulState, except the other way around

        :return:
        """
        current_closest = find_closest_enemy(self.owner,
                                             self.perception_distance)
        if not current_closest:
            return self.peaceful_state
        else:
            # Store enemy entity for future reference
            self.current_closest = current_closest


class NunchakuAgressorCombatState(AgressorCombatState):
    """
    When there is an enemy in nunchaku range, tries to whack them with right
    item
    """
    def take_action(self):
        # On every tick except the first after it got switched in,
        # self.current_closest is freshly populated by switch.state.
        # This check makes sure it's not trying to attack None on the 1st tick
        if not self.current_closest:
            return 0
        dx = self.owner.position.x - self.current_closest.position.x
        dy = self.owner.position.y - self.current_closest.position.y
        self.owner.position.turn(dx < 0 and 'r' or 'l')
        if abs(dx) <= 15 and abs(dy) <= 10:
            # If in melee range, attack with right hand
            self.owner.hands.use_hand('right')
            # TODO: let items define their use delays
            return 1.5
        else:
            i = randint(0, abs(dx) + abs(dy))
            if i <= abs(dx):
                self.owner.position.walk((dx < 0 and 1 or -1, 0))
            else:
                self.owner.position.walk((0, dy < 0 and 1 or -1))
            return 0.2


class BottleAgressorCombatState(AgressorCombatState):
    """
    Switches to a peaceful state when there is nobody to fight

    When there is, it tries to either throw bottle from the right hand or
    """
    def take_action(self):
        # On every tick except the first after it got switched in,
        # self.current_closest is freshly populated by switch.state.
        # This check makes sure it's not trying to attack None on the 1st tick
        if not self.current_closest:
            return 0
        dx = self.owner.position.x - self.current_closest.position.x
        dy = self.owner.position.y - self.current_closest.position.y
        self.owner.position.turn(dx < 0 and 'r' or 'l')
        if 35 <= abs(dx) <= 40 and abs(dy) <= 5:
            self.owner.hands.use_hand('right')
            return 1
        elif abs(dx) < 10 and abs(dy) < 5:
            # Try melee if caught in close quarters
            self.owner.hands.use_hand('left')
            return 0.5
        elif abs(dx) < 35:
            # Run away if 5 < dx < 30, whatever dy
            self.owner.position.walk((dx < 0 and -1 or 1, 0))
            return 0.2
        else:
            i = randint(0, abs(dx) + abs(dy))
            if i <= abs(dx):
                self.owner.position.walk((dx < 0 and 1 or -1, 0))
            else:
                self.owner.position.walk((0, dy < 0 and 1 or -1))
            return 0.2