import random

from bear_hug.bear_utilities import shapes_equal, copy_shape, BearException, \
    generate_box, BearLayoutException
from bear_hug.event import BearEvent
from bear_hug.widgets import Widget, Label, Layout
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
        elif event.event_type == 'brut_heal' and event.event_value[1] == self.target_entity:
            self.current_hp += event.event_value[1]
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