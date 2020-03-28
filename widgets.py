"""
Various game-specific widgets
"""

from math import sqrt
from random import choice, uniform

from bear_hug.bear_utilities import shapes_equal, copy_shape, BearException, \
    generate_box, BearLayoutException
from bear_hug.event import BearEvent
from bear_hug.widgets import Animation, Widget, Label, Layout,\
    SimpleAnimationWidget
from bear_hug.bear_hug import BearTerminal


class HitpointBar(Layout):
    """
    A hitpoint bar for HUD.

    Subscribes to brut_damage and brut_heal and tracks all events involving the
    health of a target entity
    """
    def __init__(self, target_entity=None, max_hp=10,
                 width=43, height=3):
        chars = [['\u2591' for x in range(width)] for y in range(height)]
        colors = [['green' for x in range(width)] for y in range(height)]
        super().__init__(chars, colors)
        self.target_entity = target_entity
        self.max_hp = max_hp
        self.current_hp = self.max_hp
        self.need_update = False
        label = Label(f'{self.current_hp}/{self.max_hp}',
                      width=self.width, height=1, just='center')
        self.add_child(label, (0, 1))
        self._rebuild_self()

    def on_event(self, event):
        if event.event_type == 'brut_damage' and event.event_value[0] == self.target_entity:
            self.current_hp -= event.event_value[1]
            self.need_update = True
        elif event.event_type == 'brut_heal' and event.event_value[0] == self.target_entity:
            self.current_hp += event.event_value[1]
            #TODO: HitpointBar should track changes in max hp
            # Currently it stores maximum HP independently of HealthComponent,
            # which it should not. I need to either create a hitpoint change
            # event or request current and max HP via EntityTracker during every
            # HitpointBar update
            if self.current_hp > self.max_hp:
                self.current_hp = self.max_hp
            self.need_update = True
        if self.need_update:
            green_x = round(len(self.colors[0]) * self.current_hp / self.max_hp)
            self.children[0].colors =\
                [['green' for _ in range(green_x+1)] + ['red' for _ in range(green_x+1, self.width)]
                 for y in range(self.height)]
            self.children[1].text = f'{self.current_hp}/{self.max_hp}'
            self._rebuild_self()
            self.terminal.update_widget(self)


class ItemWindow(Widget):
    """
    A window that displays an item icon within HUD
    """
    def __init__(self, target_entity, target_hand,
                 atlas):
        chars = [[' ' for x in range(14)] for y in range(9)]
        colors = copy_shape(chars, '000')
        super().__init__(chars, colors)
        self.target_entity = target_entity
        self.target_hand = target_hand
        self.atlas = atlas

    def on_event(self, event):
        if event.event_type == 'brut_pick_up':
            if event.event_value[0] == self.target_entity and event.event_value[1] == self.target_hand:
                icon_id = f"{event.event_value[2].split('_')[0]}_icon"
                self.chars, self.colors = self.atlas.get_element(icon_id)
                self.terminal.update_widget(self)


class TypingLabelWidget(Layout):
    """
    Looks like a Label, but prints its content with little animation. It is
    actually a Layout containing a Label. Accepts chars and colors (first two
    unnamed arguments) for the Layout background; ``*args`` and ``**kwargs``
    are passed to the Label to allow text justification, color, etc.
    """
    def __init__(self, chars, colors, *args, text='SAMPLE TEXT\nMORE OF SAMPLE TEXT\nLOTS OF IT',
                 chars_per_second=10, **kwargs):
        super().__init__(chars, colors)
        self.label = Label(text, *args, **kwargs)
        vis_chars = copy_shape(chars, ' ')
        vis_colors = copy_shape(colors, '000')
        self.visible_label = Widget(vis_chars, vis_colors)
        self.add_child(self.visible_label, (0, 0))
        self.is_drawing = True
        self.current_draw_x = 0
        self.current_draw_y = 0
        self.char_delay = 1/chars_per_second
        self.have_waited = 0

    def on_event(self, event):
        if event.event_type == 'tick':
            if not self.is_drawing:
                return
            self.have_waited += event.event_value
            while self.have_waited > self.char_delay:
                # With small char_delay it's possible that a single tick will
                # permit drawing multiple characters
                drawn = False
                while not drawn:
                    c = self.label.chars[self.current_draw_y][self.current_draw_x]
                    if c and c != ' ':
                        # Draw a single char from a label, if there is one
                        self.visible_label.chars[self.current_draw_y][self.current_draw_x] = c
                        self.visible_label.colors[self.current_draw_y][self.current_draw_x] = self.label.colors[self.current_draw_y][self.current_draw_x]
                        drawn = True
                    self.current_draw_x += 1
                    if self.current_draw_x >= self.label.width:
                        self.current_draw_x = 0
                        self.current_draw_y += 1
                    if self.current_draw_y >= self.label.height:
                        self.is_drawing = False
                        drawn = True
                self.have_waited -= self.char_delay
            self._rebuild_self()
            self.terminal.update_widget(self)


class ParticleWidget(Widget):
    """
    Displays the explosion of particles from midpoint towards edges

    :param size: A tuple of ints, widget size.

    :param character: A character used for a particle

    :param color: Particle color

    :param char_speed: A speed for particles, in chars per second
    """
    def __init__(self, size=(5, 5), character='*', color='red',
                 char_count=5, char_speed=2, **kwargs):
        chars = [[' ' for _ in range(size[0])] for _ in range(size[1])]
        colors = copy_shape(chars, color)
        super().__init__(chars, colors, **kwargs)
        self.character = character
        # self.move_delay = 1 / char_speed
        self.have_waited = 0
        self.char_count = char_count
        self.x_list = [round(size[0]/2) for _ in range(char_count)]
        self.y_list = [round(size[1]/2) for _ in range(char_count)]
        speed = abs(char_speed)
        x_speeds = [uniform(-speed, speed) for _ in range(char_count)]
        y_speeds = [sqrt(char_speed**2 - x_speeds[j]**2) for j in range(char_count)]
        self.x_signs = [1 if x > 0 else -1 for x in x_speeds]
        self.y_signs = [choice((-1, 1)) for _ in range(char_count)]
        self.x_delays = [abs(1/x) for x in x_speeds]
        self.y_delays = [1/y for y in y_speeds]
        self.x_waited = [0 for _ in range(char_count)]
        self.y_waited = [0 for _ in range(char_count)]
        self.chars[self.y_list[0]][self.x_list[0]] = self.character

    def on_event(self, event):
        if event.event_type == 'tick':
            # with high speeds, multiple steps per tick are possible
            for i in range(self.char_count):
                if not self.x_list[i]:
                    continue
                self.x_waited[i] += event.event_value
                while self.x_waited[i] > self.x_delays[i]:
                    self.x_waited[i] -= event.event_value
                    self.x_list[i] += self.x_signs[i]
                self.y_waited[i] += event.event_value
                while self.y_waited[i] > self.y_delays[i]:
                    self.y_waited[i] -= event.event_value
                    self.y_list[i] += self.y_signs[i]
                if self.x_list[i] < 0 or self.x_list[i] >= self.width - 0.5 or \
                        self.y_list[i] < 0 or self.y_list[i] >= self.height - 0.5:
                    # If char flies outside the widget, it's ignored
                    # Replacing with None to avoid rebuilding list for each
                    # such character
                    self.x_list[i] = None
                    self.y_list[i] = None
            # Draw only after movement has finished
            chars = copy_shape(self.colors, ' ')
            for index, x in enumerate(self.x_list):
                if x:
                    chars[round(self.y_list[index])][round(x)] = self.character
            self.chars = chars
        # Just in case nothing else was visible on this tick
        return BearEvent('ecs_update')

# TODO: Better customization for ParticleWidget
# Multiple characters, multiple colors, movement other than explosion from the
# center, etc


class LevelSwitchWidget(SimpleAnimationWidget):
    """
    A blinking level switch of required size

    Note: size is actually the rectangle around the switch, not only its visible
    part. For example, this (with invisible part represented by dots) has the
    size of (7, 4)

    ...////
    ..////.
    .////..
    ////...

    Although the actual blinking parallelogram is 4 x 4.

    Width should always be no less than height, otherwise no parallelogram could
    possibly fit inside. If they are equal, resulting parallelogram will have
    width of exactly 1 char.
    """
    def __init__(self, size=(10, 5)):
        # pregenerate chars
        if size[1] > size[0]:
            raise ValueError('Width of LevelSwitchWidget should be at least as high as its height.')
        chars = []
        offset = size[1] - 1
        running_offset = offset
        for _ in range(size[1]):
            chars.append([' '] * running_offset
                         + ['>'] * (size[0] - offset)
                         + [' '] * (offset - running_offset))
            running_offset -= 1
        colors = copy_shape(chars, 'white')
        colors2 = copy_shape(chars, '#D900D9')
        colors3 = copy_shape(chars, '#D900D9')
        color_list = ('#400040', '#8C008C', '#D900D9')
        offset = 0
        for y in range(len(colors)):
            for x in range(len(colors[0])):
                # print((x + offset) % 3, end=',')
                colors[y][x] = color_list[(x + offset) % 3]
                colors2[y][x] = color_list[(x + 1 + offset) % 3]
                colors3[y][x] = color_list[(x + 2 + offset) % 3]
            # print('\n')
            offset += 1
            if offset == 3:
                offset = 0
        super().__init__(Animation([(chars, colors3),
                                    (chars, colors2),
                                    (chars, colors)],
                                   2))

