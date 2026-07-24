from yolo_uno import *
from pins import *
import asyncio

# =========================================================
# HARDWARE & CONFIGURATION (Cooler Scope)
# =========================================================
rgb_cooler = RGBLed(D5_PIN, 4)   # Cooler -> D5 Port

TEMP_COOLER_ON = 30.0            # Cooler ON if temp > 30.0 °C

COLOR_OFF   = '#000000'
COLOR_GREEN = '#00ff00'

# Cooler States
COOLER_IDLE    = 0
COOLER_COOLING = 1

# =========================================================
# TASK IMPLEMENTATION
# =========================================================
async def task_Cooler(cooler_sem, data_mutex, temp_val):
    """
    Cooler Task (State Machine: IDLE / COOLING)
    Priority: Normal | Triggered by: cooler_sem
    """
    state = COOLER_IDLE

    while True:
        # Wait for signal from task_Read_Temperature
        await cooler_sem.acquire()

        # Read shared data under mutex protection
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