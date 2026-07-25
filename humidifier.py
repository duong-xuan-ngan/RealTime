from yolo_uno import *
from pins import *
from lcd1602 import *
from dht20 import *

import asyncio

# ---------------------------------------------------------
# 6.5 Humidifier Task
# State machine: IDLE / GREEN(5s) / YELLOW(3s) / RED(2s)
# Priority: normal  |  Triggered by: humidifier_sem
# ---------------------------------------------------------
async def task_Humidifier():
    state = HUMI_IDLE
    while True:
        await humidifier_sem.acquire()

        # Read shared data under mutex
        await data_mutex.acquire()
        h = humi_val[0]
        data_mutex.release()

        # State transition: only leave IDLE if humidity is low
        if state == HUMI_IDLE and h < HUMI_LOW:
            state = HUMI_GREEN

        # State actions
        if state == HUMI_GREEN:
            print("[HUMIDIFIER] GREEN 5s")
            rgb_humidifier.show(0, hex_to_rgb(COLOR_GREEN))
            await asleep_ms(5000)
            state = HUMI_YELLOW

            print("[HUMIDIFIER] YELLOW 3s")
            rgb_humidifier.show(0, hex_to_rgb(COLOR_YELLOW))
            await asleep_ms(3000)
            state = HUMI_RED

            print("[HUMIDIFIER] RED 2s")
            rgb_humidifier.show(0, hex_to_rgb(COLOR_RED))
            await asleep_ms(2000)

            rgb_humidifier.show(0, hex_to_rgb(COLOR_OFF))
            state = HUMI_IDLE
            print("[HUMIDIFIER] sequence done -> IDLE")
        else:
            rgb_humidifier.show(0, hex_to_rgb(COLOR_OFF))
            print("[HUMIDIFIER] IDLE")