import random

from bear_hug.bear_utilities import shapes_equal, copy_shape, BearException, \
    generate_box, BearLayoutException
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


# TODO: backport Menu system
class MenuWidget(Layout):
    """
    A menu widget that includes multiple buttons.

    :param dispatcher: BearEventDispatcher instance to which the menu will subscribe

    :param items: an iterable of MenuItems

    :param background: A background widget for the menu. If not supplied, a default double-thickness box is used. If background widget needs to get events (ie for animation), it should be subscribed by the time it's passed here.

    :param color: A bearlibterminal-compatible color. Used for a menu frame and header text

    :param header: str or None. A menu header. This should not be longer than menu width, otherwise an exception is thrown.
    """
    # TODO: modality: pause everything when shown
    def __init__(self, dispatcher, terminal=None, items=[], header=None,
                 color='white',
                 background=None, **kwargs):
        self.items = []
        # Separate from self.heigh and self.width to avoid overwriting attrs
        self.h = 3
        self.w = 4
        self.color = color
        for item in items:
            self._add_item(item)
        if terminal and not isinstance(terminal, BearTerminal):
            raise TypeError(f'{type(terminal)} used as a terminal for MenuWidget instead of BearTerminal')
        # Set background, if supplied
        if not background:
            bg_chars = generate_box((self.w, self.h), 'double')
            bg_colors = copy_shape(bg_chars, self.color)
            for y in range(len(bg_chars) - 2):
                for x in range(len(bg_chars[0]) - 2):
                    bg_chars[y + 1][x + 1] = '\u2588'
                    bg_colors[y + 1][x + 1] = 'black'
            super().__init__(bg_chars, bg_colors)
        else:
            if background.width < self.w or background.height < self.h:
                raise BearLayoutException('Background for MenuWidget is too small')
            # Creating tmp BG widget instead of just taking BG chars and colors
            # because the background could be some complex widget, eg animation
            bg_chars = [[' ' for x in range(background.width)]
                        for y in range(background.height)]
            bg_colors = copy_shape(bg_chars, 'black')
            super().__init__(bg_chars, bg_colors)
            self.background = background
        # Adding header, if any
        if header:
            if not isinstance(header, str):
                raise TypeError(f'{type(header)} used instead of string for MenuWidget header')
            if len(header) > self.width - 2:
                raise BearLayoutException(f'MenuWidget header is too long')
            header_label = Label(header, color=self.color)
            x = round((self.width - header_label.width) / 2)
            self.add_child(header_label, (x, 0))
        # Adding buttons
        current_height = 2
        for item in self.items:
            self.add_child(item, (2, current_height))
            current_height += item.height + 1
        dispatcher.register_listener(self, ['tick', 'service', 'misc_input', 'key_down'])
        # Prevent scrolling multiple times when key is pressed
        self.input_delay = 0.2
        self.current_delay = self.input_delay
        self._current_highlight = 0
        self.items[self.current_highlight].highlight()
        # TODO: do something about menu transparency
        # Some background chars are visible because they overlap menu item chars
        # I should either add a screening widget at lower bearlibterminal layer,
        # or find some way to disable char overlap in the necessary range

    def _add_item(self, item):
        """
        Add an item to the menu.

        This method may only be called from ``__init__``; there is no support
        for changing menu contents on the fly

        :param item: MenuItem instance
        """
        if not isinstance(item, MenuItem):
            raise TypeError(f'{type(item)} used instead of MenuItem for MenuWidget')
        self.items.append(item)
        self.h += item.height + 1
        if item.width > self.w - 4:
            self.w = item.width + 4

    @property
    def current_highlight(self):
        return self._current_highlight

    @current_highlight.setter
    def current_highlight(self, value):
        if not 0 <= value <= len(self.items) - 1:
            raise ValueError('current_highlight can only be set to a valid item index')
        self.items[self._current_highlight].unhighlight()
        self._current_highlight = value
        self.items[self._current_highlight].highlight()

    def on_event(self, event):
        if event.event_type == 'tick' and self.current_delay <= self.input_delay:
            self.current_delay += event.event_value
        elif event.event_type == 'key_down' and self.current_delay >= self.input_delay:
            self.current_delay = 0
            if event.event_value in ('TK_SPACE', 'TK_ENTER'):
                self.items[self.current_highlight].activate()
            elif event.event_value in ('TK_UP', 'TK_W') \
                    and self.current_highlight > 0:
                self.current_highlight -= 1
            elif event.event_value in ('TK_DOWN', 'TK_S') \
                    and self.current_highlight < len(self.items) - 1:
                self.current_highlight += 1
            elif event.event_value == 'TK_MOUSE_LEFT':
                if self.terminal:
                    # Silently ignore mouse input if terminal is not set
                    mouse_x = self.terminal.check_state('TK_MOUSE_X')
                    mouse_y = self.terminal.check_state('TK_MOUSE_Y')
                    x, y = self.terminal.widget_locations[self].pos
                    if x <= mouse_x <= x + self.width and y <= mouse_y <= y + self.height:
                        b = self.get_child_on_pos((mouse_x - x, mouse_y -y))
                        # self.current_highlight = self.items.index(b)
                        if isinstance(b, MenuItem):
                            self.items[self.current_highlight].activate()
        elif event.event_type == 'misc_input' and event.event_value == 'TK_MOUSE_MOVE':
            if self.terminal:
                # Silently ignore mouse input if terminal is not set
                mouse_x = self.terminal.check_state('TK_MOUSE_X')
                mouse_y = self.terminal.check_state('TK_MOUSE_Y')
                x, y = self.terminal.widget_locations[self].pos
                if x <= mouse_x < x + self.width and y <= mouse_y < y + self.height:
                    b = self.get_child_on_pos((mouse_x - x, mouse_y - y))
                    # Could be the menu header
                    if isinstance(b, MenuItem):
                        self.current_highlight = self.items.index(b)
        return super().on_event(event)


class MenuItem(Layout):
    """
    A button for use inside menus. Includes a label surrounded by a single-width
    box. Contains a single callable, ``self.action``, which will be called when
    this button is activated.

    MenuItem by itself does not handle any input. It provides ``self.activate``
    method which should be called by something (presumably a menu containing
    this button).

    :param text: str. A button label

    :param action: callable. An action that this MenuItem performs

    :param color: a bearlibterminal-compatible color that this button has by
    default

    :param highlight_color: a bearlibterminal-compatible color that this button
    has when highlighted via keyboard menu choice or mouse hover.
    """
    def __init__(self, text='Test', action=lambda: print('Button pressed'),
                 color='white', highlight_color='green',
                 **kwargs):
        self.color = color
        self.highlight_color = highlight_color
        # Widget generation
        label = Label(text, color=self.color)
        bg_chars = generate_box((label.width+2, label.height+2),
                                'single')
        bg_colors = copy_shape(bg_chars, self.color)
        super().__init__(bg_chars, bg_colors)
        self.add_child(label, (1, 1))
        self._rebuild_self()
        if not hasattr(action, '__call__'):
            raise BearException('Action for a button should be callable')
        self.action = action

    def highlight(self):
        """
        Change button colors to show that it's highlighted
        """
        self.background.colors = copy_shape(self.background.colors,
                                            self.highlight_color)
        self._rebuild_self()

    def unhighlight(self):
        """
        Change button colors to show that it's no longer highlighted
        :return:
        """
        self.background.colors = copy_shape(self.background.colors,
                                            self.color)
        self._rebuild_self()

    def activate(self):
        """
        Perform the button's action
        """
        self.action()