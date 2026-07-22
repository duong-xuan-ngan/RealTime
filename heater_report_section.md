## 2.2 Heater Control State Machine

The heater LED (connected to D3) has three states, determined by the current
temperature reading. There is no timer involved in this task; the state is
recalculated every time a new sensor reading arrives, so the LED always
reflects the latest temperature.

**States:**

| State | Color | Condition |
|---|---|---|
| SAFE | GREEN | temperature <= 28.0 °C |
| WARNING | ORANGE | 28.0 °C < temperature <= 32.0 °C |
| CRITICAL | RED | temperature > 32.0 °C |

**Transitions:**

The task waits for a signal from the Read Temperature task (every 5 seconds).
On each signal, it reads the shared temperature value and re evaluates which
of the three ranges it falls into. Since every state is reachable directly
from every other state (the check is a plain range comparison, not a
sequence), the transition diagram is a simple triangle: SAFE, WARNING, and
CRITICAL each transition to whichever of the other two states matches the new
reading, or stay in place if the reading is still in the same range.

```
             temp <= 28
     (SAFE) <===========> (WARNING) <===========> (CRITICAL)
        28<temp<=32                     temp>32
```

*(Insert your own drawn version of this diagram, e.g. three circular states
with bidirectional arrows labeled with the threshold conditions, as the
figure for this section.)*

## 3.5 Heater Task

**Priority / period:** The heater task is not periodic itself; it blocks on
`heater_sem` and only runs when the Read Temperature task signals it, which
happens every 5 seconds. In this project's cooperative asyncio scheduler
there is no explicit numeric priority; all tasks run at the same priority and
yield control at each `await`.

**Synchronization:** Before reading the temperature, the task acquires
`data_mutex` to safely read the shared `temp_val` variable, since that
variable is also written by the Read Temperature task and read by the Cooler
and Humidifier tasks. It releases the mutex immediately after copying the
value, so it does not hold the lock while updating the LED.

**State variable:** The state is stored explicitly in a `state` variable
(`HEATER_SAFE`, `HEATER_WARNING`, `HEATER_CRITICAL`), and is recalculated from
the temperature before the corresponding LED color is set, matching the
state diagram in section 2.2 directly.

```python
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
```

## 4.2 Heater Behavior

*(Fill in after running on Wokwi or hardware. For each screenshot below,
capture the serial monitor output at the moment the LED changes color, so the
temperature value and the LED state are visible together.)*

**SAFE state (GREEN):**
[Insert screenshot here: serial output showing temperature <= 28.0 °C and
LED lit green.]

Comment: [Describe what the screenshot shows, for example the exact
temperature value logged and confirmation that the heater LED switched to
green at that reading.]

**WARNING state (ORANGE):**
[Insert screenshot here: serial output showing 28.0 °C < temperature <=
32.0 °C and LED lit orange.]

Comment: [Describe the transition you observed, for example temperature
crossing from the SAFE range into the WARNING range and the LED updating
within one sensor cycle of 5 seconds.]

**CRITICAL state (RED):**
[Insert screenshot here: serial output showing temperature > 32.0 °C and LED
lit red.]

Comment: [Describe the transition into CRITICAL and, if tested, the
transition back down to WARNING or SAFE once temperature dropped again.]
