from config import BOARD

__all__ = ["BUTTON_A_ZONE", "DISPLAY", "HEIGHT", "WIDTH", "Channel", "Unicorn"]

if BOARD == "stellar":
    from picographics import DISPLAY_STELLAR_UNICORN as DISPLAY
    from stellar import Channel
    from stellar import StellarUnicorn as Unicorn
elif BOARD == "galactic":
    from galactic import Channel
    from galactic import GalacticUnicorn as Unicorn
    from picographics import DISPLAY_GALACTIC_UNICORN as DISPLAY
elif BOARD == "cosmic":
    from cosmic import Channel
    from cosmic import CosmicUnicorn as Unicorn
    from picographics import DISPLAY_COSMIC_UNICORN as DISPLAY
else:
    raise ValueError("Unknown BOARD in config.py: " + str(BOARD))

WIDTH = Unicorn.WIDTH
HEIGHT = Unicorn.HEIGHT

BUTTON_A_ZONE = tuple((0, y) for y in range(2, 5))
