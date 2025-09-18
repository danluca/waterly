#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#
import queue

__scheduler_queue = queue.Queue()

def send_message_to_scheduler(msg: str):
    __scheduler_queue.put(msg)

