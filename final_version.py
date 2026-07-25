from yolo_uno import *
from pins import *
from lcd1602 import *
from dht20 import *

import asyncio

# =========================================================
# 1. CUSTOM SEMAPHORE
# Used for BOTH:
#   - Mutex (initial value = 1): protect shared sensor data
#   - Signaling (initial value = 0): notify actuator tasks
# =========================================================
class Semaphore:
    def __init__(self, value=1):
        if value < 0:
            raise ValueError("ValueError")
        self.value = value

    async def acquire(self):
        while self.value <= 0:
            await asleep_ms(10)
        self.value -= 1
        return True

    def release(self):
        self.value += 1

# =========================================================
# 2. SHARED STATE & SEMAPHORES  (Report section 3.1)
# =========================================================
# Shared sensor data (written by Read Temp task, read by 3 actuator tasks)
temp_val = [0.0]
humi_val = [0.0]

# Mutex protecting the shared data above
data_mutex = Semaphore(1)

# Signaling semaphores: Read Temp task releases these each cycle
# to notify each actuator task that a fresh reading is available.
heater_sem     = Semaphore(0)
cooler_sem     = Semaphore(0)
humidifier_sem = Semaphore(0)

# =========================================================
# 3. HARDWARE
# =========================================================
led_D13 = Pins(D13_PIN)

rgb_heater     = RGBLed(D3_PIN, 4)   # Heater     -> D3
rgb_cooler     = RGBLed(D5_PIN, 4)   # Cooler     -> D5
rgb_humidifier = RGBLed(D7_PIN, 4)   # Humidifier -> D7

lcd1602 = LCD1602()
dht20   = DHT20()

# =========================================================
# 4. THRESHOLDS & COLORS
# =========================================================
TEMP_SAFE_MAX    = 28.0   # Heater SAFE     if temp <= 28
TEMP_WARNING_MAX = 32.0   # Heater WARNING  if 28 < temp <= 32
                          # Heater CRITICAL if temp > 32
TEMP_COOLER_ON   = 30.0   # Cooler ON       if temp > 30
HUMI_LOW         = 50.0   # Humidifier ON   if humi < 50

COLOR_OFF    = '#000000'
COLOR_GREEN  = '#00ff00'
COLOR_ORANGE = '#ffa500'
COLOR_YELLOW = '#ffff00'
COLOR_RED    = '#ff0000'

# =========================================================
# 5. STATE CONSTANTS  (matches Part 2 state diagrams)
# =========================================================
# Heater states
HEATER_SAFE     = 0
HEATER_WARNING  = 1
HEATER_CRITICAL = 2

# Cooler states
COOLER_IDLE    = 0
COOLER_COOLING = 1

# Humidifier states
HUMI_IDLE   = 0
HUMI_GREEN  = 1
HUMI_YELLOW = 2
HUMI_RED    = 3

# =========================================================
# 6. TASKS
# =========================================================

# ---------------------------------------------------------
# 6.1 Blinky Task
# Priority: lowest  |  Period: 1000 ms
# ---------------------------------------------------------
async def task_LED_Blinky():
    while True:
        led_D13.toggle()
        await asleep_ms(1000)


# ---------------------------------------------------------
# 6.2 Read Temperature Task
# Priority: highest (producer)  |  Period: 5000 ms
# Shares data via `data_mutex`; signals actuator tasks via
# heater_sem / cooler_sem / humidifier_sem.
# ---------------------------------------------------------
async def task_Read_Temperature():
    while True:
        temp = await dht20.atemperature()
        humi = await dht20.ahumidity()

        # Protect shared data write
        await data_mutex.acquire()
        temp_val[0] = temp
        humi_val[0] = humi
        data_mutex.release()

        print("[SENSOR] Temp: {:.1f} C | Humi: {:.1f} %".format(temp, humi))

        lcd1602.clear()
        lcd1602.show("T:{:.1f}C".format(temp), 0, 0)
        lcd1602.show("H:{:.1f}%".format(humi), 1, 0)

        # Notify actuator tasks that new data is ready
        heater_sem.release()
        cooler_sem.release()
        humidifier_sem.release()

        await asleep_ms(5000)


# ---------------------------------------------------------
# 6.3 Heater Task  (State machine: SAFE / WARNING / CRITICAL)
# Priority: normal  |  Triggered by: heater_sem
# ---------------------------------------------------------
async def task_Heater():
    state = HEATER_SAFE
    while True:
        await heater_sem.acquire()

        # Read shared data under mutex
        await data_mutex.acquire()
        t = temp_val[0]
        data_mutex.release()

        # State transitions (based on current temperature)
        if t <= TEMP_SAFE_MAX:
            state = HEATER_SAFE
        elif t <= TEMP_WARNING_MAX:
            state = HEATER_WARNING
        else:
            state = HEATER_CRITICAL

        # State actions (switch-case style)
        if state == HEATER_SAFE:
            rgb_heater.show(0, hex_to_rgb(COLOR_GREEN))
            print("[HEATER] SAFE (GREEN)")
        elif state == HEATER_WARNING:
            rgb_heater.show(0, hex_to_rgb(COLOR_ORANGE))
            print("[HEATER] WARNING (ORANGE)")
        elif state == HEATER_CRITICAL:
            rgb_heater.show(0, hex_to_rgb(COLOR_RED))
            print("[HEATER] CRITICAL (RED)")


# ---------------------------------------------------------
# 6.4 Cooler Task  (State machine: IDLE / COOLING)
# Priority: normal  |  Triggered by: cooler_sem
# ---------------------------------------------------------
async def task_Cooler():
    state = COOLER_IDLE
    while True:
        await cooler_sem.acquire()

        # Read shared data under mutex
        await data_mutex.acquire()
        t = temp_val[0]
        data_mutex.release()

        # State transitions
        if state == COOLER_IDLE:
            if t > TEMP_COOLER_ON:
                state = COOLER_COOLING
        elif state == COOLER_COOLING:
            # After one fixed 5s cycle, return to IDLE for re-check
            state = COOLER_IDLE

        # State actions
        if state == COOLER_COOLING:
            print("[COOLER] COOLING (GREEN) for 5s")
            rgb_cooler.show(0, hex_to_rgb(COLOR_GREEN))
            await asleep_ms(5000)
            rgb_cooler.show(0, hex_to_rgb(COLOR_OFF))
            print("[COOLER] cycle done")
        else:
            rgb_cooler.show(0, hex_to_rgb(COLOR_OFF))
            print("[COOLER] IDLE")


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

# =========================================================
# 7. SETUP & MAIN
# =========================================================
async def setup():
    print("=== RTOS Smart Climate Control System Started ===")
    create_task(task_LED_Blinky())
    create_task(task_Read_Temperature())
    create_task(task_Heater())
    create_task(task_Cooler())
    create_task(task_Humidifier())

async def main():
    await setup()
    while True:
        await asleep_ms(100)

run_loop(main())# No code generated yet.
# Switch to Blocks mode and add some blocks.