class FakeGraphics:
    GLYPH_ADVANCE = 4

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.pixels_drawn = 0
        self.texts = []

    def create_pen(self, r, g, b):
        for channel in (r, g, b):
            if not (isinstance(channel, int) and 0 <= channel <= 255):
                raise AssertionError(f"invalid pen {(r, g, b)}")
        return (r, g, b)

    def set_pen(self, pen):
        pass

    def set_font(self, font):
        pass

    def clear(self):
        pass

    def pixel(self, x, y):
        self._check_on_screen(x, y, 1, 1)
        self.pixels_drawn += 1

    def rectangle(self, x, y, w, h):
        self._check_on_screen(x, y, w, h)
        self.pixels_drawn += w * h

    def text(self, text, x, y, wordwrap, scale):
        self.texts.append(text)

    def measure_text(self, text, scale):
        return len(text) * self.GLYPH_ADVANCE * scale

    def _check_on_screen(self, x, y, w, h):
        if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
            raise AssertionError(f"draw {(x, y, w, h)} outside display")
