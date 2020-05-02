"""
Plot generation system
"""

import random

from bear_hug.ecs import Singleton


# TODO: Goal description in the main menu

# TODO: Get the goal-based levelgen to actually work
# For the demo, all levels are assembled manually. Although the code in this
# file and the next_goal_level method of LevelManager can serve as useful basis
# for future plot generation system, I just haven't figured out the correct
# abstract structure behind the whole system yet.

class Goal:
    """
    A description of the current player goal.

    Basically a quest plus some basic levelgen data and exposition text
    """
    def __init__(self,
                 name='Menu',
                 description = 'I\'m in a main menu',
                 enemy_factions=('punks', ),
                 ally_factions=('cops',),
                 location='ghetto',
                 level_types=('corridor', ),
                 exposition_monologues=(('This is a main menu',
                                         'Walk into one of the transporters\nto the right',
                                         'I recommend the NEW GAME')),
                 chatter={'cops': 'Cop chatter',
                          'scientists': 'Scientist chatter'},
                 next_on_win=('tutorial', ),
                 next_on_lose=None):
        self.name = name
        self.chatter = chatter
        self.exposition_monologues = exposition_monologues
        self.location = location
        self.description = description
        self.enemy_factions = enemy_factions
        self.ally_factions = ally_factions
        self.level_types = level_types
        self.next_on_win = next_on_win
        self.next_on_lose = next_on_lose
        self.current_stage = 0


class PlotManager(metaclass=Singleton):
    """
    A master class in control of the plot
    """
    def __init__(self, goals=(), initial_goal={}):
        # TODO: more phrases
        # Phrases useful in any kind of plot - random faction-specific chatter
        self.general_phrases = {'cops': (('Captain\'s an ass,\nif you ask me.', ),
                                         ('Hey there', 'How\'s it going?'),
                                         ('Anybody seen my badge?',),
                                         ('Hi', ),
                                         ('Howdy',),
                                         ('The whole damn city\nis going to hell',
                                          'We need to clean up\nthe streets')),
                                'scientists': (('Now back to the grants',),
                                               ('Where\'s the goddamn\nwelder?',
                                                'I have no time for\nplaying hide-n-seek',
                                                'Especially with my tools'),
                                               ('Calibrating...', ),
                                               ('Careful around the spikes',
                                                'Wouldn\'t want you fried'),
                                               ('Hey, what\'s it \nwith the alpha spark\nand sodium lamps?',
                                                'Why are they even...',
                                                'Oh, nevermind,',
                                                'Just thinking aloud'))}
        # TODO: connect attack phrases to plot state
        # Attack phrases - something for the enemies to shout when they beat you
        # Single-line, long monologue would seem stupid mid-battle
        self.attack_phrases = {'punks': ('Oink oink, motherfucker!',
                                         'Here, piggy, piggy...',
                                         'This is OUR turf!',
                                         'Down with you!',
                                         'Asshole',
                                         'You shoulda\nstayed out of here',
                                         'Go die already'),
                               'scientists': ('Stay out of my lab!',
                                              'Who has even\nlet you in?',
                                              'No way I let some asshole\nplay with my equipment',
                                              'Here\'s for you',
                                              'And stay down'),
                               'cops': ('One less asshole',
                                        'Feeling lucky?',
                                        'Here\'s for you',
                                        'You\'re SO fucked')}
        # for goal in goals:
        #     if not isinstance(goal, Goal):
        #         raise TypeError(f'{type(goal)} used instead of Goal in PlotManager')
        # self.goals = goals
        # self.current_goal = self.goals[initial_goal]

    def next_stage(self):
        """
        Advance a goal.

        If a current goal was completed, start the next one.
        :return:
        """
        self.current_goal.current_stage += 1
        if self.current_goal.current_stage >= len(self.current_goal.level_types):
            next_goal = random.choice(self.current_goal.next_on_win)
            self.current_goal = self.goals[next_goal]
            self.current_goal.current_stage = 0

    def get_peaceful_phrase(self, faction='cops'):
        """
        Return a plot-appropriate monologue for a peaceful NPC of a given
        faction.
        :return:
        """
        if faction not in self.general_phrases:
            raise ValueError(f'Requested a phrase for a nonexistent faction "{faction}"')
        return random.choice(self.general_phrases[faction])

    def get_next_level(self):
        """
        Return a handle for the next level
        :return:
        """
        return 'dept_corridor'
