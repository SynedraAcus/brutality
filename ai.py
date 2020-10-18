"""
AI components
"""
import inspect
from json import dumps, loads
from math import sqrt
from random import choice, randint, random

from bear_hug.bear_utilities import BearJSONException
from bear_hug.ecs import Component, EntityTracker
from bear_hug.event import BearEvent

from plot import PlotManager


def find_closest_enemy(entity, perception_distance, enemy_factions=None):
    """
    Finds closest enemy for leaving peaceful states or attack targeting.
    :param entity: Entity. who is looking

    :param perception_distance: Int. how far do they see

    :param enemy_factions: None or an iterable of str. If not None, taken as a
    list of enemy factions. If None, any different faction is treated as an enemy

    :return:
    """
    if enemy_factions:
        enemies = EntityTracker().filter_entities(
            lambda x: hasattr(x, 'faction')
                      and x.faction.faction in enemy_factions)
    else:
        enemies = EntityTracker().filter_entities(
            lambda x: hasattr(x, 'faction')
                      and x.faction.faction != entity.faction.faction)
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


def choose_direction(dx, dy, dy_preference):
    dx_prob = abs(dx) / (abs(dx) + abs(dy)) - dy_preference
    dy_prob = abs(dy) / (abs(dx) + abs(dy)) - dy_preference
    return (-dx // abs(dx) if random() < dx_prob and dx_prob > 0 else 0,
            -dy // abs(dy) if 0 < dy_prob < 1 - random() else 0)


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

    def __init__(self, *args, states={}, state_dump=None,
                 current_state='inactive', **kwargs):
        self._owner = None
        self.states = {}
        super().__init__(*args, name='controller', **kwargs)
        if state_dump:
            for state in state_dump:
                self._add_state(state,
                        deserialize_state(state_dump[state], self.dispatcher))
        for state in states:
            self._add_state(state, states[state])
        self.current_state = current_state
        self.delay = 0
        self.have_waited = 0
        self.dispatcher.register_listener(self, 'tick')

    # Wrapping owner so that it gets correctly set for states if they were
    # added to owner-less component (eg during loading from JSON dump)
    @property
    def owner(self):
        return self._owner

    @owner.setter
    def owner(self, value):
        self._owner = value
        for state in self.states:
            self.states[state].owner = self._owner

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

    def __repr__(self):
        d = loads(super().__repr__())
        d['current_state'] = self.current_state
        d['state_dump'] = {}
        for state in self.states:
            d['state_dump'][state] = repr(self.states[state])
        return dumps(d)


class AIState:
    """
    A single state of the AI finite state machine.

    It can address the entity it controls as self.owner, similar to the
    components. Unlike the components, though, it does not add itself to the
    owner's __dict__

    :param owner: Entity this state belongs to. Defaults to None

    :param enemy_factions: factions this state treats like enemies. Setting this
    to None makes it treat **ALL** factions except their own as such; to create
    a state without any enemies, set this to nonexistent faction ID.
    Defaults to None.

    :param enemy_perception_distance: distance, in chars, at which enemies are
    detected. Defaults to 50.

    :param player_id: Entity ID for player character, used in things like talks.
    Defaults to 'cop_1'

    :param player_perception_distance: distance, in chars, at which player
    character is detected. Defaults to 50.
    """
    def __init__(self, dispatcher, owner=None,
                 enemy_factions=None,
                 enemy_perception_distance=50,
                 player_id='cop_1',
                 player_perception_distance=50,
                 current_closest=None):
        self.dispatcher = dispatcher
        self.owner = owner
        self.enemy_factions = enemy_factions
        self.enemy_perception_distance = enemy_perception_distance
        self.player_id = player_id
        self.player_perception_distance = player_perception_distance
        self.current_closest = current_closest

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

    def __repr__(self):
        d = {'class': self.__class__.__name__,
             'enemy_factions': self.enemy_factions,
             'enemy_perception_distance': self.enemy_perception_distance,
             'player_id': self.player_id,
             'player_perception_distance': self.player_perception_distance}
        return dumps(d)


class WaitAIState(AIState):
    """
    A state that does nothing and waits for either player or enemies to arrive.

    Upon that happening, it switches to the corresponding state (if set). If the
    state is not set (default), the check doesn't happen. If both states are
    set, enemy presence is checked first; if an enemy is detected, enemy_arrival
    state is activated immediately without any attempts to check whether the
    player is around.

    :param player_arrival_state: str or None. If not None, `switch_state`
    returns this when player character is within `player_perception_distance`
    chars.

    :param enemy_arrival_state: str or None. If not None, `switch_state` returns
    this when at least one enemy is within `enemy_perception_distance` chars.

    :param check_delay: float. Time, in seconds, between two checks for enemy or
    player presence.
    """
    def __init__(self, *args,
                 player_arrival_state=None,
                 enemy_arrival_state=None,
                 check_delay=0.1,
                 **kwargs):
        super().__init__(*args, **kwargs)
        if player_arrival_state and not isinstance(player_arrival_state, str):
            raise TypeError(f'{type(player_arrival_state)} used instead of str for WaitAIState')
        if enemy_arrival_state and not isinstance(enemy_arrival_state, str):
            raise TypeError(f'{type(enemy_arrival_state)} used instead of str for WaitAIState')
        self.player_arrival_state = player_arrival_state
        self.enemy_arrival_state = enemy_arrival_state
        self.check_delay = check_delay

    def take_action(self):
        return self.check_delay

    def switch_state(self):
        if self.enemy_arrival_state:
            self.current_closest = find_closest_enemy(self.owner,
                                                      self.enemy_perception_distance,
                                                      self.enemy_factions)
            if self.current_closest:
                return self.enemy_arrival_state
        if self.player_arrival_state:
            try:
                player = EntityTracker().entities[self.player_id]
            except KeyError:
                # If the player is not available, he's likely dead
                return None
            dx = player.position.x - self.owner.position.x
            dy = player.position.y - self.owner.position.y
            dist = sqrt(dx ** 2 + dy ** 2)
            if dist <= self.player_perception_distance:
                return self.player_arrival_state
        return None

    def __repr__(self):
        d = loads(super().__repr__())
        d['player_arrival_state'] = self.player_arrival_state
        d['enemy_arrival_state'] = self.enemy_arrival_state
        d['check_delay'] = self.check_delay
        return dumps(d)


class RunawayAIState(AIState):
    """
    A state for running away from enemies.

    :param wait_state: str. A wait state to which this switches when no enemies
    are nearby. Cannot be set to None because otherwise this state can never be
    left.

    :param step_delay: float. A time it takes to make one step.
    """
    def __init__(self, *args, wait_state=None, step_delay=0.2, **kwargs):
        super().__init__(*args, **kwargs)
        if not isinstance(wait_state, str):
            raise TypeError(f'{type(wait_state)} used instead of str for RunawayAIState')
        self.wait_state = wait_state
        self.step_delay = step_delay

    def switch_state(self):
        self.current_closest = find_closest_enemy(self.owner,
                                                  self.enemy_perception_distance,
                                                  self.enemy_factions)
        if self.current_closest:
            return None
        else:
            return self.wait_state

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
        return self.step_delay

    def __repr__(self):
        d = loads(super().__repr__())
        d['wait_state'] = self.wait_state
        d['step_delay'] = self.step_delay
        return dumps(d)


class TalkAIState(AIState):
    """
    A state for characters delivering a monologue to the player. Switches to
    a runaway state when an enemy is around, and to the wait state if the player
    is nowhere near, or when monologue is exhausted.

    :param wait_state: str or None. Non-active state to switch to.

    :param enemy_arrival_state: str or None. State to switch to when enemies
    arrive.

    :param monologue: an iterable of str. A series of phrases to be delivered.
    If a single-phrase monologue is required, it should still be wrapped within
    a tuple because otherwise it iterates over string and spits out a series of
    single-letter phrases.

    :param phrase_delay: float. Delay, in seconds, between phrases.

    :param phrase_sounds: an iterable of str or None. If not None, one of these
    lines, chosen randomly at equal probabilities, is played via `play_sound`
    event. Sound validity is not checked and could create crashes if
    SoundListener doesn't know these sound IDs.
    """
    def __init__(self, *args,
                 wait_state=None,
                 enemy_arrival_state=None,
                 monologue=('Line one', 'Line two'),
                 phrase_delay=1.2,
                 phrase_sounds=None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.wait_state = wait_state
        self.enemy_arrival_state = enemy_arrival_state
        for line in monologue:
            if not isinstance(line, str):
                raise ValueError(f'monologue for a CivilianTalkState should be an iterable of strs')
        self.monologue = monologue
        self.phrase_sounds = phrase_sounds
        # Index of the next phrase to be said
        self.next_phrase = 0
        self.phrase_delay = phrase_delay
        self.last_used_sound = None

    def switch_state(self):
        # See if there is someone to run away from
        current_closest = find_closest_enemy(self.owner,
                                             self.enemy_perception_distance,
                                             self.enemy_factions)
        if current_closest:
            return self.enemy_arrival_state
        if self.next_phrase >= len(self.monologue):
            return self.wait_state
        # If not, look if player is within radius
        try:
            player = EntityTracker().entities[self.player_id]
        except KeyError:
            # If the player is not available, he's likely dead
            return None
        dist = sqrt((self.owner.position.x - player.position.x) ** 2 +
                    (self.owner.position.y - player.position.y) ** 2)
        # Wait if he is not
        if dist > self.player_perception_distance:
            return self.wait_state

    def take_action(self):
        # Could've switched into talk state after exhausting the monologue
        if self.next_phrase >= len(self.monologue):
            return 0
        try:
            pc = EntityTracker().entities[self.player_id]
        except KeyError:
            return 0
        if self.owner.position.x >= pc.position.x:
            self.owner.position.turn('l')
        else:
            self.owner.position.turn('r')
        # Center on the first line
        x_offset = round((len(self.monologue[self.next_phrase].split('\n')[0])
                          - self.owner.widget.width) / 2)
        if self.phrase_sounds and (self.next_phrase % 2 == 0):
            if len(self.phrase_sounds) > 1:
                sound = choice(self.phrase_sounds)
                while sound == self.last_used_sound:
                    sound = choice(self.phrase_sounds)
                self.last_used_sound = sound
            else:
                sound = self.phrase_sounds[0]
            self.dispatcher.add_event(BearEvent('play_sound',
                                                sound))
        self.owner.spawner.spawn('message', (-x_offset, 0),
                                 text=self.monologue[self.next_phrase],
                                 vy=-2,
                                 vx=0,
                                 color=self.owner.faction.phrase_color,
                                 destroy_condition='timeout',
                                 lifetime=5.0)
        # Could have waited a lot during combat or waiting, but it still
        # should not spawn all phrases at once
        self.next_phrase += 1
        return self.phrase_delay

    def __repr__(self):
        d = loads(super().__repr__())
        d['wait_state'] = self.wait_state
        d['enemy_arrival_state'] = self.enemy_arrival_state
        d['monologue'] = self.monologue
        d['phrase_delay'] = self.phrase_delay
        d['phrase_sounds'] = self.phrase_sounds
        return dumps(d)


class CombatAIState(AIState):
    """
    A combatant state.

    Looks for enemies and switches to wait state when it doesn't find them. If
    there are enemies and dy <=2, checks whether dx is valid for either hand.
    If dx falls within at least one of the ranges, valid hand is used. If both
    hands are useful at current dx, one is chosen at random. To permanently
    disable a hand, set its range to (0, 0).

    If no attack is possible, tries to walk towards enemy.

    :param right_range: 2-tuple of ints. min and max distance at which right
    hand is used.

    :param left_range: 2-tuple of ints. min and max distance at which left hand
    is used.

    :param wait_state: str. a state to which it switches when there is no enemy in
    range.
    """
    def __init__(self, *args,
                 right_range=(4, 8),
                 left_range=(4, 8),
                 wait_state=None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.right_range = right_range
        self.left_range = left_range
        self.wait_state = wait_state
        self.dy_preference = 0
        self.walk_direction = None
        self.steps_left = 0
        self.dispatcher.register_listener(self, 'ecs_collision')

    def switch_state(self):
        self.current_closest = find_closest_enemy(self.owner,
                                                  self.enemy_perception_distance,
                                                  self.enemy_factions)
        if not self.current_closest:
            return self.wait_state

    def take_action(self):
        if not self.current_closest:
            return 0
        dx = self.owner.position.x - self.current_closest.position.x
        dy = self.owner.position.y - self.current_closest.position.y
        self.owner.position.turn(dx < 0 and 'r' or 'l')
        valid_hands = []
        if -1 <= dy <= 2:
            # If within dy range, check whether dx is valid for either hand
            if self.left_range[0] <= abs(dx) <= self.left_range[1]:
                valid_hands.append('left')
            if self.right_range[0] <= abs(dx) <= self.right_range[1]:
                valid_hands.append('right')
        # Phrases emitted randomly when attacking
        if len(valid_hands) == 2:
            if random() < 0.3:
                phrase = choice(PlotManager().attack_phrases
                                [self.owner.faction.faction])
                self.owner.spawner.spawn('message', (0, -2), text=phrase,
                                         vy=-4,
                                         destroy_condition='timeout',
                                         lifetime=0.5)
            return self.owner.hands.use_hand(choice(valid_hands))
        elif len(valid_hands) == 1:
            if random() < 0.3:
                phrase = choice(PlotManager().attack_phrases
                                [self.owner.faction.faction])
                self.owner.spawner.spawn('message', (0, -2),
                                         text=phrase, vy=-4,
                                         destroy_condition='timeout',
                                         lifetime=0.5)
            return self.owner.hands.use_hand(valid_hands[0])
        else:
            # walk toward the enemy
            if self.walk_direction != (0, 0) and self.steps_left > 0:
                self.owner.position.walk(self.walk_direction)
                self.steps_left -= 1
                return 0.15
            else:
                if (not self.right_range[0] or abs(dx) < self.right_range[0]) and \
                        (not self.left_range[0] or abs(dx) < self.left_range[0]):
                    # If too close to use any available weapon, tweak dx for
                    # walk direction calculations
                    ranges = (self.left_range[0] if self.left_range[0] else 1000,
                              self.right_range[0] if self.right_range[0] else 1000)
                    r = min(ranges)
                    dx += r * 1 if dx > 0 else -1
                # Reconsidering direction
                self.steps_left = min(abs(dx) + 1, abs(dy) + 1,
                                      randint(4, 7))
                self.walk_direction = choose_direction(dx, dy,
                                                       self.dy_preference)
                return 0

    def on_event(self, event):
        # This part is for switching direction upon collision. It prevents
        # enemies from stupidly banging into the first wall they encounter
        if event.event_type == 'ecs_collision' and \
                event.event_value[0] == self.owner.id:
            try:
                if EntityTracker().entities[event.event_value[1]].collision.passable:
                    # Ignore collisions into passable objects
                    return
            except KeyError:
                # Another appearance of collision into just-destroyed entity
                return
            self.walk_direction = (randint(-1, 1), randint(-1, 1))
            self.steps_left = randint(4, 7)
# TODO: prevent nunchaku punks from getting lost after close contact with PC

    def __repr__(self):
        d = loads(super().__repr__())
        d['right_range'] = self.right_range
        d['left_range'] = self.left_range
        d['wait_state'] = self.wait_state
        return dumps(d)


def deserialize_state(serial, dispatcher):
    """
    Load the AIState from a JSON string or dict.

    This is a stripped-down version of `bear_hug.ecs.deserialize_component`
    without support for converters.

    Expects the dict or string to contain ``class`` key with the class name.
    This class will be used for an AIState instance; it should be imported by
    the code that calls this function, or somewhere within its call stack. This
    class should be a subclass of AIState.

    All other keys are used as kwargs for a newly created object. Keys ``owner``
    and ``dispatcher`` are forbidden and cause an exception to be raised.

    :param serial: A valid JSON string or a dict produced by deserializing such a string.

    :param dispatcher: A queue passed to the ``AIState.__init__``

    :returns: an AIState instance.
    """
    if isinstance(serial, str):
        d = loads(serial)
    elif isinstance(serial, dict):
        d = serial
    else:
        raise BearJSONException(f'Attempting to deserialize {type(serial)} to AIState')
    for forbidden_key in ('owner', 'dispatcher'):
        if forbidden_key in d.keys():
            raise BearJSONException(f'Forbidden key {forbidden_key} in AIState JSON')
    if 'class' not in d:
        raise BearJSONException('No class provided in component JSON')
    types = [x for x in d if '_type' in x]
    for t in types:
        del(d[t])
    # Try to get the Component class from where the function was imported, or
    # the importers of *that* frame. Without this, the function would only see
    # classes from this very file, or ones imported into it, and that would
    # break the deserialization of custom components.
    class_var = None
    for frame in inspect.getouterframes(inspect.currentframe()):
        if d['class'] in frame.frame.f_globals:
            class_var = frame.frame.f_globals[d['class']]
            break
    del frame
    if not class_var:
        raise BearJSONException(f"Class name {class_var} not imported anywhere in the frame stack")
    if not issubclass(class_var, AIState):
        raise BearJSONException(f"Class name {class_var}mapped to something other than a AIState subclass")
    kwargs = {}
    for key in d:
        if key == 'class':
            continue
        else:
            kwargs[key] = d[key]
    return class_var(dispatcher, **kwargs)