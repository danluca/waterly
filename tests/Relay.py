# -*- coding: utf-8 -*-
from gpiozero import OutputDevice
import time

relays = [OutputDevice(5), OutputDevice(6), OutputDevice(13), OutputDevice(16), OutputDevice(19), OutputDevice(20)]

def relay_on(relay):
    relays[relay].on()

def relay_off(relay):
    relays[relay].off()

try:
    for i in range(6):
        print(f"Turn on relay {i+1} at pin {relays[i].pin}")
        relay_on(i)
        time.sleep(1)
        print(f"Turn off relay {i+1}")
        relay_off(i)
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting...")
finally:
    for i in range(6):
        relay_off(i)
