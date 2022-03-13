# SPDX-FileCopyrightText: 2022 Mark Komus
# SPDX-License-Identifier: MIT

import asyncio
import time
import board
import neopixel
import keypad
import supervisor
from adafruit_ht16k33.segments import BigSeg7x4, Seg14x4
from digitalio import DigitalInOut, Direction

RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (255, 0, 255)
ORANGE = (255, 70, 0)
WHITE = (255, 255, 255)
PINK = (255, 90, 90)
CYAN = (0, 255, 255)
GREY = (50, 50, 50)
BLACK = (0, 0, 0)

PLAYER_COLORS = (
    RED,
    GREEN,
    BLUE,
    YELLOW,
    PURPLE,
    ORANGE,
    PINK,
    CYAN,
    GREY,
    WHITE,
    BLACK,
)

# Initialize components
i2c = board.I2C()

large_segment = BigSeg7x4(i2c)
large_segment.brightness = 0.1

small_segment = Seg14x4(i2c, address=0x71)
small_segment.brightness = 0.1

large_button_light = DigitalInOut(board.D25)
large_button_light.direction = Direction.OUTPUT
large_button_light.value = True
large_button_pin = board.D24

small_button_light = DigitalInOut(board.D12)
small_button_light.direction = Direction.OUTPUT
small_button_light.value = True
small_button_pin = board.D11

pixels = neopixel.NeoPixel(
    board.D5, 8, brightness=0.1, auto_write=False, pixel_order=(1, 0, 2, 3)
)
pixels.fill(0x000000)
pixels.show()


def show_player(player, marquee):
    """Helper module change all elements when the player changes"""
    pixels.fill(player.color)
    pixels.show()
    marquee.message("{} PLAYER ".format(player.number), 0.3, True)


class TimerTracker:
    """Timer that updates elapsed time passed"""
    def __init__(self):
        self.time = 0.0
        self.paused = True
        self.start_time = 0.0
        self.pre_pause_time = 0.0

    def pause(self):
        """Pause the timer"""
        self.pre_pause_time = self.time
        self.paused = True

    def resume(self):
        """Resume the timer"""
        self.start_time = time.monotonic()
        self.paused = False

    def update(self):
        """Update the timer. Must be called regularly."""
        if self.paused is True:
            return
        self.time = time.monotonic() - self.start_time + self.pre_pause_time


class Player:
    """Holds all information about a game player"""
    # pylint: disable=too-few-public-methods
    def __init__(self, number=1, color=(0, 0, 0)):
        self.number = number
        self.color = color
        self.timer = TimerTracker()


class Game:
    """Holds all information about a game"""
    def __init__(self):
        self.players = []
        self._current_player = 0
        self.paused = True
        self.game_over = False

    @property
    def current_player(self):
        """Return current player object"""
        return self.players[self._current_player]

    def next_player(self):
        """Advance to the next player"""
        self._current_player = (self._current_player + 1) % len(self.players)

    def pause(self):
        """Pause the game"""
        self.current_player.timer.pause()
        self.paused = True

    def resume(self):
        """Resume the game"""
        self.current_player.timer.resume()
        self.paused = False


class MarqueeMessage:
    """Message to be displayed on the marquee display"""
    # pylint: disable=too-few-public-methods
    def __init__(self, text, speed):
        self.text = text
        self.speed = speed
        self.scroll = True

    def message(self, text=None, speed=0.3, scroll=True):
        """Set the message to show, speed and if it scrolls."""
        self.text = text
        self.speed = speed
        self.scroll = scroll


async def marquee_routine(message):
    """Display the current message on the small segment display."""
    position = 0
    current_text = ""
    while True:
        if message.text is not None:
            if message.text is not current_text:
                current_text = message.text
                if message.scroll is True:
                    position = 0
                    small_segment.print("    ")
                else:  # scroll is False
                    small_segment.print(message.text)
            else:
                if message.scroll is True:
                    small_segment.scroll(1)
                    small_segment[3] = current_text[position]
                    position += 1
                    if position >= len(current_text):
                        position = 0
                    small_segment.show()

            await asyncio.sleep(message.speed)
        else:
            await asyncio.sleep(0)


async def setup_routine(game, marquee):
    """Setup a new game and players for the game."""
    # pylint: disable=too-many-branches,too-many-statements
    setup_phase = "PLAYERS"
    color_phase_player = 1
    current_color = 0

    large_button_light.value = False
    large_segment.print("   1")
    large_segment.colon = False
    marquee.message("HOW MANY PLAYERS   ", 0.3, True)

    number_players = 1
    with keypad.Keys(
        (small_button_pin, large_button_pin), value_when_pressed=False, pull=True
    ) as keys:
        while setup_phase != "DONE":
            key_event = keys.events.get()
            if key_event and key_event.pressed:
                key_number = key_event.key_number
                if key_number == 0:
                    small_button_light.value = False
                    if setup_phase == "PLAYERS":
                        setup_phase = "COLORS"
                        pixels.fill(PLAYER_COLORS[current_color])
                        pixels.show()
                        marquee.message(
                            "PLAYER {} COLOR   ".format(color_phase_player), 0.3, True
                        )
                        large_segment.print("   {}".format(color_phase_player))
                    elif setup_phase == "COLORS":
                        player = Player(
                            color_phase_player, PLAYER_COLORS[current_color]
                        )
                        game.players.append(player)
                        color_phase_player += 1
                        if color_phase_player > number_players:
                            setup_phase = "DONE"
                            marquee.message(None)
                        else:
                            current_color = 0
                            pixels.fill(PLAYER_COLORS[current_color])
                            pixels.show()
                            marquee.message(
                                "PLAYER {} COLOR   ".format(color_phase_player),
                                0.3,
                                True,
                            )
                            large_segment.print("   {}".format(color_phase_player))

                if key_number == 1:
                    large_button_light.value = True
                    if setup_phase == "PLAYERS":
                        number_players += 1
                        if number_players == 10:
                            number_players = 1
                        large_segment.print("   {}".format(number_players))
                    elif setup_phase == "COLORS":
                        current_color += 1
                        if current_color == len(PLAYER_COLORS):
                            current_color = 0
                        pixels.fill(PLAYER_COLORS[current_color])
                        pixels.show()

            if key_event and key_event.released:
                key_number = key_event.key_number
                if key_number == 0:
                    small_button_light.value = True
                if key_number == 1:
                    large_button_light.value = False

            await asyncio.sleep(0)


async def update_timer(game):
    """Regularlly update the game timer."""
    while True:
        game.current_player.timer.update()
        await asyncio.sleep(0)


async def show_timer(game):
    """Show the current player time on the large LED segment display."""
    large_segment.colon = True
    while True:
        current_time = game.current_player.timer.time
        minutes = int(current_time / 60)
        seconds = int(current_time % 60)

        time_string = "{:02d}".format(minutes) + "{:02d}".format(seconds)
        large_segment.print(time_string)

        await asyncio.sleep(0.05)


async def monitor_buttons(game, marquee):
    """Check if either button is pressed to run the timer project."""
    # pylint: disable=too-many-branches
    large_button_light.value = False
    small_button_press_time = 0
    with keypad.Keys(
        (small_button_pin, large_button_pin), value_when_pressed=False, pull=True
    ) as keys:
        while True:
            key_event = keys.events.get()
            if key_event and key_event.pressed:
                key_number = key_event.key_number
                if key_number == 0:  # small button
                    small_button_press_time = key_event.timestamp
                    small_button_light.value = False
                    if game.game_over is False:
                        if game.paused is True:
                            game.resume()
                            show_player(game.current_player, marquee)
                        else:
                            game.pause()
                            marquee.message("PAUSED   ", 0.3, True)
                if key_number == 1:
                    large_button_light.value = True
                    if game.game_over is True:
                        game.next_player()
                        show_player(game.current_player, marquee)
                    if game.paused is False:
                        game.current_player.timer.pause()
                        game.next_player()
                        show_player(game.current_player, marquee)
                        game.current_player.timer.resume()
            if key_event and key_event.released:
                key_number = key_event.key_number
                if key_number == 0:
                    small_button_light.value = True
                    if (
                        key_event.timestamp - small_button_press_time
                    ) > 4000:  # 4 seconds
                        if game.game_over is False:
                            game.game_over = True
                            game.pause()
                            marquee.message("GAME OVER   ", 0.3, True)
                        else:
                            supervisor.reload()
                if key_number == 1:
                    large_button_light.value = False

            await asyncio.sleep(0)


async def main():
    """Setup and control the overall project."""
    game = Game()

    marquee = MarqueeMessage(None, 1.0)
    asyncio.create_task(marquee_routine(marquee))

    setup_task = asyncio.create_task(setup_routine(game, marquee))
    await asyncio.gather(setup_task)

    pixels.fill(0)
    pixels.show()
    marquee.message("RDY ", 0, False)

    time.sleep(0.5)

    buttons_task = asyncio.create_task(monitor_buttons(game, marquee))
    timer_task = asyncio.create_task(update_timer(game))
    show_timer_task = asyncio.create_task(show_timer(game))

    await asyncio.gather(buttons_task, timer_task, show_timer_task)
    # We never get here


asyncio.run(main())