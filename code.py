import asyncio

import board

from adafruit_ht16k33.segments import BigSeg7x4, Seg14x4
from digitalio import DigitalInOut, Direction, Pull
import neopixel

import keypad
import time

PLAYER_COLORS = ( (255,0,0), (0,255,0), (0,0,255), (255,0,255), (255,255,0), (0,255,255), (255,255,255) )

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

pixels = neopixel.NeoPixel(board.D5, 8, brightness=0.1, auto_write=False, pixel_order=(1,0,2,3))
pixels.fill(0x000000)
pixels.show()


def show_player(player, marquee):
    pixels.fill(player.color)
    pixels.show()
    marquee.message("{} PLAYER ".format(player.number), 0.3, True)

class TimerTracker:
    def __init__(self):
        self.time = 0.0
        self.paused = True
        self.start_time = 0.0
        self.pre_pause_time = 0.0

    def pause(self):
        self.pre_pause_time = self.time
        self.paused = True

    def resume(self):
        self.start_time = time.monotonic()
        self.paused = False

    def update(self):
        if self.paused is True:
            return
        self.time = time.monotonic() - self.start_time + self.pre_pause_time

class Player:
    def __init__(self, number=1, color=(0,0,0)):
        self.number = number
        self.color = color
        self.timer = TimerTracker()

class Game:
    def __init__(self):
        self.players = []
        self._current_player = 0
        self.paused = True

    @property
    def current_player(self):
        return self.players[self._current_player]

    def next_player(self):
        self._current_player = (self._current_player + 1) % len(self.players)

    def pause(self):
        self.current_player.timer.pause()
        self.paused = True

    def resume(self):
        self.current_player.timer.resume()
        self.paused = False

class MarqueeMessage:
    def __init__(self, text, speed):
        self.text = text
        self.speed = speed
        self.scroll = True

    def message(self, text = None, speed = 0.3, scroll = True):
        self.text = text
        self.speed = speed
        self.scroll = scroll

async def marquee_routine(message):
    position = 0
    current_text = ""
    while True:
        if message.text is not None:
            if message.text is not current_text:
                current_text = message.text
                if message.scroll is True:
                    position = 0
                    small_segment.print("    ")
                else: # scroll is False
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

async def setup_phase(game, marquee, small_button_pin, large_button_pin):
    setup_phase = "PLAYERS"
    color_phase_player = 1
    current_color = 0

    large_button_light.value = False
    large_segment.print("   1")
    large_segment.colon = False
    marquee.message("HOW MANY PLAYERS   ", 0.3, True)

    number_players = 1
    with keypad.Keys((small_button_pin, large_button_pin), value_when_pressed=False, pull=True) as keys:
        while setup_phase is not "DONE":
            key_event = keys.events.get()
            if key_event and key_event.pressed:
                key_number = key_event.key_number
                if key_number == 0:
                    small_button_light.value = False
                    if setup_phase is "PLAYERS":
                        print("Done players")
                        setup_phase = "COLORS"
                        #game = Game()
                        pixels.fill(PLAYER_COLORS[current_color])
                        pixels.show()
                        marquee.message("PLAYER {} COLOR   ".format(color_phase_player), 0.3, True)
                    elif setup_phase is "COLORS":
                        print("Color chosen")
                        player = Player(color_phase_player, PLAYER_COLORS[current_color])
                        game.players.append(player)
                        color_phase_player += 1
                        if color_phase_player > number_players:
                            setup_phase = "DONE"
                            marquee.message(None)
                        else:
                            current_color = 0
                            pixels.fill(PLAYER_COLORS[current_color])
                            pixels.show()
                            marquee.message("PLAYER {} COLOR   ".format(color_phase_player), 0.3, True)

                if key_number == 1:
                    large_button_light.value = True
                    if setup_phase is "PLAYERS":
                        print("More players")
                        number_players += 1
                        if number_players == 10:
                            number_players = 1
                        large_segment.print("   {}".format(number_players))
                    elif setup_phase is "COLORS":
                        print("Change color")
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

async def monitor_buttons(marquee, small_button_pin, large_button_pin):
    large_button_light.value = False
    with keypad.Keys((small_button_pin, large_button_pin), value_when_pressed=False, pull=True) as keys:
        while True:
            key_event = keys.events.get()
            if key_event and key_event.pressed:
                key_number = key_event.key_number
                if key_number == 0:
                    small_button_light.value = False
                    if game.paused is True:
                        game.resume()
                        show_player(game.current_player, marquee)
                    else:
                        game.pause()
                        marquee.message("PAUSED   ", 0.3, True)
                if key_number == 1:
                    if game.paused is False:
                        large_button_light.value = True
                        game.current_player.timer.pause()
                        game.next_player()
                        show_player(game.current_player, marquee)
                        game.current_player.timer.resume()
            if key_event and key_event.released:
                key_number = key_event.key_number
                if key_number == 0:
                    small_button_light.value = True
                if key_number == 1:
                    large_button_light.value = False

            await asyncio.sleep(0)

async def update_timer():
    while True:
        game.current_player.timer.update()
        await asyncio.sleep(0)

async def show_timer():
    large_segment.colon = True
    while True:
        current_time = game.current_player.timer.time
        minutes = int(current_time / 60)
        seconds = int(current_time % 60)

        time_string = "{:02d}".format(minutes) + "{:02d}".format(seconds)
        large_segment.print(time_string)

        await asyncio.sleep(0.05)

async def main():
    marquee = MarqueeMessage(None, 1.0)
    marquee_task = asyncio.create_task(marquee_routine(marquee))

    setup_task = asyncio.create_task(setup_phase(game, marquee, small_button_pin, large_button_pin))
    await asyncio.gather(setup_task)

    print("Starting game", game)
    marquee.message("RDY ", 0, False)

    time.sleep(0.5)

    buttons_task = asyncio.create_task(monitor_buttons(marquee, small_button_pin, large_button_pin))
    timer_task = asyncio.create_task(update_timer())
    show_timer_task = asyncio.create_task(show_timer())

    await asyncio.gather(buttons_task, timer_task, show_timer_task)

    print("End of program, this should never be reached")

game = Game()
asyncio.run(main())