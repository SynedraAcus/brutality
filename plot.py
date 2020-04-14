"""
Plot generation system
"""

import random

from bear_hug.ecs import Singleton


class PlotManager(metaclass=Singleton):
    """
    A master class in control of the plot
    """
    def __init__(self):
        # TODO: more general phrases
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
                                               ('Careful around the emitter',
                                                'Wouldn\'t want you fried'),
                                               ('Hey, what\'s it \nwith the alpha spark\nand sodium lamps?',
                                                'Why are they even...',
                                                'Oh, nevermind,',
                                                'Just thinking aloud'))}
        pass

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
