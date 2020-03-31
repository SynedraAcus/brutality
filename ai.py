"""
AI components
"""
from math import sqrt
from random import choice, randint

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

def find_closest_enemy(entity, perception_distance, enemy_factions=None):
    """
    Finds closest enemy for leaving peaceful states or attack targeting.
    :param entity: Entity. who is looking

    :param perception_distance: Int. how far do they see

    :param enemy_factions: None or an iterable of str. If not None, taken as a list of enemy factions. If None, any different faction is treated as an enemy.
    :return:
    """
    if enemy_factions:
        enemies = list(EntityTracker().filter_entities(
            lambda x: hasattr(x,'faction') and x.faction.faction in enemy_factions))
    else:
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
            return self.owner.hands.use_hand('right')
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
    fight in melee with left hand (presumably a fist)
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
            return self.owner.hands.use_hand('right')
        elif abs(dx) < 10 and abs(dy) < 5:
            return self.owner.hands.use_hand('left')
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


################################################################################
# Civilian: a peaceful NPC who just stands there, maybe delivering some
# monologue
################################################################################


class CivilianAIState(AIState):
    """
    A base class for civilians: remembers who he should talk to and who he
    should run from.
    """
    def __init__(self, *args, pc_id, enemy_factions=None,
                 player_perception_distance=20,
                 enemy_perception_distance=50,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.pc_id = pc_id
        self.enemy_factions = enemy_factions
        self.player_perception_distance = player_perception_distance
        self.enemy_perception_distance = enemy_perception_distance


class CivilianWaitState(CivilianAIState):
    """
    Waits either for enemy to run from, or for the PC to talk to
    """
    def __init__(self, *args, runaway_state=None,
                 player_interaction_state=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.runaway_state = runaway_state
        self.player_interaction_state = player_interaction_state

    def switch_state(self):
        # See if there is someone to run away from
        current_closest = find_closest_enemy(self.owner,
                                             self.enemy_perception_distance,
                                             self.enemy_factions)
        if current_closest:
            return self.runaway_state
        # If not, look if pc_id is within radius
        pc = EntityTracker().entities[self.pc_id]
        dist = sqrt((self.owner.position.x - pc.position.x) ** 2 +
                    (self.owner.position.y - pc.position.y) ** 2)
        if dist <= self.player_perception_distance:
            return self.player_interaction_state

    def take_action(self):
        return 0.2


class CivilianRunawayState(CivilianAIState):
    """
    Runs away from the enemy.

    This state does not switch directly to player interaction. It can only be
    left if there are no enemies, switching to wait state. Otherwise, NPCs could
    randomly start talking in the middle of the battle.
    """
    def __init__(self, *args, peaceful_state=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.peaceful_state = peaceful_state
        self.current_closest = None

    def switch_state(self):
        current_closest = find_closest_enemy(self.owner,
                                             self.enemy_perception_distance,
                                             self.enemy_factions)
        if current_closest:
            self.current_closest = current_closest
        else:
            return self.peaceful_state

    def take_action(self):
        if not self.current_closest:
            return 0
        dx = self.owner.position.x - self.current_closest.position.x
        dy = self.owner.position.y - self.current_closest.position.y
        self.owner.position.turn(dx > 0 and 'r' or 'l')
        i = randint(0, abs(dx) + abs(dy))
        if i <= abs(dx):
            self.owner.position.walk((dx < 0 and -1 or 1, 0))
        else:
            self.owner.position.walk((0, dy < 0 and -1 or 1))
        return 0.2


class CivilianTalkState(CivilianAIState):
    """
    While the player is within range, delivers his monologue.

    Switches to runaway_state if enemy is near or to wait state if the player
    is too far (or upon exhausting the monologue)

    :param monologue: iterable of strs. A series of phrases that this char delivers

    :param phrase_pause: float. A delay between phrases, in seconds
    """
    def __init__(self, *args, monologue=('Line one', 'Line two'),
                 phrase_pause=1.2,
                 peaceful_state=None,
                 runaway_state=None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.peaceful_state = peaceful_state
        self.runaway_state = runaway_state
        for line in monologue:
            if not isinstance(line, str):
                raise ValueError(f'monologue for a CivilianTalkState should be an iterable of strs')
        self.monologue = monologue
        # Index of the next phrase to be said
        self.next_phrase = 0
        self.phrase_pause = phrase_pause

    def switch_state(self):

        # See if there is someone to run away from
        current_closest = find_closest_enemy(self.owner,
                                             self.enemy_perception_distance,
                                             self.enemy_factions)
        if current_closest:
            return self.runaway_state
        if self.next_phrase >= len(self.monologue):
            return self.peaceful_state
        # If not, look if pc_id is within radius
        pc = EntityTracker().entities[self.pc_id]
        dist = sqrt((self.owner.position.x - pc.position.x) ** 2 +
                    (self.owner.position.y - pc.position.y) ** 2)
        # Wait if he is not
        if dist > self.player_perception_distance:
            return self.peaceful_state

    def take_action(self):
        # Could've switched into talk state after already exhausting the monologue
        if self.next_phrase >= len(self.monologue):
            return 0
        # Center on the first line
        x_offset = round((len(self.monologue[self.next_phrase].split('\n')[0]) - self.owner.widget.width) / 2)
        self.owner.spawner.spawn('message', (-x_offset, 0),
                                 text=self.monologue[self.next_phrase],
                                 vy=-3,
                                 vx=randint(-1, 1),
                                 color='gray',
                                 destroy_condition='timeout',
                                 lifetime=5.0)
        # Could have waited a lot during combat or waiting, but it still
        # should not spawn all phrases at once
        self.next_phrase += 1
        return self.phrase_pause

# TODO: a more reasonable navigation logic for NPCs
# Currently they get stuck around the obstacles and tend to start turning around
# every few steps when on the edge of perception distance. It is probably gonna
# look much better if they pick a direction, walk it for a few tens of steps,
# then reconsider. Pretty trivial, but bound to look better
