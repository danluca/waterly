#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#
import queue
from enum import Enum
from typing import Any

__scheduler_queue = queue.Queue()


class Action(Enum):
    UPDATE_CONFIG = 1
    START_WATERING = 2
    STOP_WATERING = 3

class QueueMessage:
    """
    Represents a message in a queue.

    Stores information about an action and associated data that
    represent the content or payload of a queue message. This class
    is primarily used for transferring data asynchronously between threads.

    :ivar _action: Represents the action associated with this message.
    :type _action: Action
    :ivar _data: Represents the data associated with this message.
    :type _data: Any
    """
    def __init__(self, action: Action, data: Any = None):
        self._action = action
        self._data = data

    @property
    def action(self) -> Action:
        return self._action

    @property
    def data(self) -> Any:
        return self._data


def send_message_to_scheduler(msg: QueueMessage):
    """
    Sends a message to the scheduler queue.

    This function adds the provided message object to the scheduler's internal
    queue to be processed accordingly.

    :param msg: The message object to be sent to the scheduler. Must be a
                valid instance of QueueMessage containing necessary data.
    """
    __scheduler_queue.put(msg)

def receive_scheduler_message() -> QueueMessage|None:
    """
    Fetch a message from the scheduler queue if available.

    This function attempts to retrieve a message from the scheduler queue. If the
    queue is empty, it returns None.

    :return: The retrieved message from the queue or None if the queue is empty.
    :rtype: QueueMessage or None
    """
    if not __scheduler_queue.empty():
        return __scheduler_queue.get(block=False)
    return None

