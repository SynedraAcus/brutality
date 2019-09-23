import random

from bear_hug.bear_utilities import shapes_equal, copy_shape, BearException
from bear_hug.widgets import Widget, Label, Layout


class PatternGenerator:
    def __init__(self, atlas):
        self.atlas = atlas

    def generate_tiled(self, pattern, size):
        """
        Generate a chars/colors pair, tiled with a given pattern.
        The pattern is always aligned up and left.
        :param pattern: either str or a tuple. If a tuple, should be chars
        and colors; if str, should be a valid ID in self.atlas.
        :return:
        """
        if isinstance(pattern, str):
            tile_chars, tile_colors = self.atlas.get_element(pattern)
        elif isinstance(pattern, tuple):
            tile_chars, tile_colors = pattern
            if not shapes_equal(tile_colors, tile_chars):
                raise BearException('Incorrect pattern')
        else:
            raise BearException('A pattern for PatternGenerator should be either str or tuple')
        chars = [[' ' for x in range(size[0])] for y in range(size[1])]
        colors = copy_shape(chars, 'white')
        tile_height = len(tile_chars)
        tile_width = len(tile_chars[0])
        for y in range(len(chars)):
            for x in range(len(chars[0])):
                chars[y][x] = tile_chars[y % tile_height][x % tile_width]
                colors[y][x] = tile_colors[y % tile_height][x % tile_width]
        return chars, colors
    
    def tile_randomly(self, *patterns, size):
        """
        Tile with patterns in random order
        :param patterns:
        :param size:
        :return:
        """""
        tile_chars = []
        tile_colors = []
        for pattern in patterns:
            if isinstance(pattern, str):
                tc, tcol = self.atlas.get_element(pattern)
                tile_chars.append(tc)
                tile_colors.append(tcol)
            elif isinstance(pattern, tuple):
                if not shapes_equal(pattern[0], pattern[1]):
                    raise BearException('Incorrect pattern')
                tile_chars.append(pattern[0])
                tile_colors.append(pattern[1])
            else:
                raise BearException(
                    'A pattern for PatternGenerator should be either str or tuple')
        chars = [[' ' for x in range(size[0])] for y in range(size[1])]
        colors = copy_shape(chars, 'white')
        tile_height = len(tile_chars[0])
        tile_width = len(tile_chars[0][0])
        r = False
        for tile_y in range(size[1] // tile_height + 1):
            for tile_x in range(size[0] // tile_width + 1):
                running_pattern = random.randint(0, len(tile_chars) - 1)
                for y in range(tile_height):
                    for x in range(tile_width):
                        try:
                            chars[tile_y * tile_height + y] \
                                 [tile_x * tile_width + x] = tile_chars \
                                    [running_pattern][y][x]
                            colors[tile_y * tile_height + y] \
                                [tile_x * tile_width + x] = tile_colors \
                                    [running_pattern]\
                                    [y][x]
                        except IndexError:
                            r = True
                            break
        return chars, colors
        
    @staticmethod
    def stack_boxes(*boxes, order='vertical'):
        """
        Stack several rectangular elements into a single (chars, colors) item.
        Expects all of them to be the same size along the direction orthogonal
        to that of stacking, ie vertically stacked elements should be equal in
        width and horizontally stacked ones should be equal in height.
        :param boxes: iterable, a collection of elements to stack
        :param order: str. Either 'vertical' or 'horizontal'
        :return:
        """
        for item in boxes[1:]:
            if not shapes_equal(item, boxes[0]):
                raise BearException('Incorrectly shaped item in stack_boxes')
        if order == 'vertical':
            chars = []
            colors = []
            for item in boxes:
                chars.extend(item[0])
                colors.extend(item[1])
        elif order == 'horizontal':
            chars = []
            colors = []
            for y in range(len(boxes[0][0])):
                chars.append([])
                colors.append([])
                for item in boxes:
                    chars[y] += item[0][y]
                    colors[y] += item[1][y]
        else:
            raise BearException('Stacking order should be either vertical or horizontal')
        return chars, colors


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