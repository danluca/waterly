#  MIT License
#
#  Copyright (c) 2025 by Dan Luca. All rights reserved.
#

import json
import os
import threading

from enum import Enum
from typing import Any
from datetime import datetime, UTC
from .times import _json_datetime_encoder, _json_datetime_decoder
from ..model.trend import *     # needed to have available all model objects in the global scope
from ..model.times import *     # needed to have available all model objects in the global scope
from ..model.units import *     # needed to have available all model objects in the global scope
from ..model.weather_data import *     # needed to have available all model objects in the global scope
from ..model.zone import *     # needed to have available all model objects in the global scope
from ..model.measurement import *


#<editor-fold desc="JSON serialization helpers">
def _json_default(o):
    """
    JSON serializer for custom types used in this project.
    """
    # Datetime -> ISO string
    if isinstance(o, datetime):
        return _json_datetime_encoder(o)

    # Prefer a user-defined json_encode() when available
    obj_encoder = getattr(o, "json_encode", None)
    if callable(obj_encoder):
        # noinspection PyBroadException
        try:
            return obj_encoder()
        except Exception:
            # Fall through to other strategies if json_encode() fails
            pass

    # Enum -> value
    # noinspection PyBroadException
    try:
        if isinstance(o, Enum):
            return o.value
    except Exception:
        pass

    # Generic object: use its __dict__ as a last resort
    if hasattr(o, "__dict__"):
        return o.__dict__

    # Fallback to string representation
    return str(o)

def _json_object_hook(obj: dict) -> Any:
    """
    Decode a JSON object into a specific Python object or retain its dictionary form.
    This function tries to identify and decode objects based on their ``__type__`` field,
    if it is provided or utilizes class-specific decoders when available. If no specific
    decoding logic applies, the function returns the object as it is.

    :param obj: The JSON object or dictionary to decode.
    :type obj: dict
    :return: The decoded Python object or the original input if no specific decoding is applied.
    :rtype: Any
    """
    if not isinstance(obj, dict):
        return obj

    # Try to use class-specific decoder if type is specified
    if "__type__" in obj and isinstance(obj["__type__"], str):
        class_name:str = obj.get("__type__")
        match class_name:
            case "datetime":
                return _json_datetime_decoder(obj)
            case _:
                # Find our class in the current module
                cls = globals().get(class_name)
                if cls and "waterly." in cls.__module__ and hasattr(cls, "json_decode") and callable(cls.json_decode):
                    # noinspection PyBroadException
                    try:
                        return cls.json_decode(obj)
                    except Exception:
                        pass

    return obj

#</editor-fold>

def write_text_file(path: str, content: str) -> None:
    """
    Write the given text to 'path', overwriting if it exists.
    Uses a temporary file + atomic replace to avoid partial writes.
    Creates parent directories if they don't exist.
    """
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        # Atomic on POSIX; safe overwrite on Windows
        os.replace(tmp_path, path)
    finally:
        # Best-effort cleanup if something went wrong before replace
        # noinspection PyBroadException
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


class ThreadSafeJSON:
    """
    ThreadSafeJSON provides a thread-safe interface for reading and updating JSON
    configurations stored in a file.

    This class ensures proper synchronization using a reentrant lock, allowing
    safe concurrent access to the JSON file. It also creates the file's directory
    structure if it does not exist and initializes the file with a default value
    if it is missing. Operations such as reading and updating the file are
    protected to avoid race conditions or data corruption during concurrent use.

    :ivar path: Path to the JSON file.
    :type path: str
    :ivar default: Default value to initialize the file with if it does not exist.
    :type default: Any
    """
    def __init__(self, path: str, default: Any):
        self.path = path
        self.default = default
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            self._write(default)

    def _read(self) -> Any:
        """
        Reads and parses a JSON file using UTF-8 encoding.

        The method opens the file specified by the `path` attribute in read mode
        with UTF-8 encoding, then loads and returns its content as a Python object.
        The returned object represents the parsed JSON data.

        :return: The parsed JSON content as a Python object
        :rtype: Any
        """
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f, object_hook=_json_object_hook)

    def _write(self, content: Any):
        """
        Writes the given content to a temporary file in JSON format and renames
        it to the target file path. This ensures the atomicity of the write
        operation to avoid incomplete or corrupted writes.

        :param content: The content to be written to the file. It must be
            serializable to JSON format.
        """
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, default=_json_default)
        os.replace(tmp_path, self.path)

    def read(self) -> Any:
        """
        Reads data in a thread-safe manner. If an exception is encountered during the
        read operation, it resets the data to a default value and returns this default.

        :return: The value read by the internal `_read` method or the default value if
            an exception occurs.
        :rtype: Any
        """
        with self._lock:
            # noinspection PyBroadException
            try:
                return self._read()
            except Exception:
                self._write(self.default)
                return self.default

    def update(self, updater):
        """
        Updates the stored data using the provided updater function. The method reads
        the current data, applies the updater function to modify it, writes the updated
        data back, and returns the updated result.

        :param updater: Function that accepts the current data as an input and returns
                        the updated data.
        :type updater: Callable
        :return: The updated data after applying the updater function.
        :rtype: Any
        """
        with self._lock:
            data = self.read()
            updated = updater(data)
            self._write(updated)
            return updated


class RollingThreadSafeJSON(ThreadSafeJSON):
    """
    Provides a rolling mechanism for JSON data that allows safe updates across threads
    while dynamically updating file paths based on the current year.

    This class extends the functionality of ThreadSafeJSON to automatically adapt the
    storage path of JSON files according to the current year. It enforces the presence
    of a '%YEAR%' placeholder in the given path and resolves it during file operations.

    :ivar path: The file path template containing the '%YEAR%' placeholder.
    :type path: str
    :ivar default: The default data to use if the JSON file does not exist.
    :type default: Any
    """

    def __init__(self, path: str, default: Any):
        self._pathPattern = path
        if ("%YEAR%" not in self._pathPattern) and ("%MONTH%" not in self._pathPattern):
            raise ValueError("Path pattern must contain both %YEAR% and %MONTH% placeholders")
        # Initialize base with the resolved current-year path; the file is created at the correct location immediately
        super().__init__(self.get_current_file_path(), default)

    def get_current_file_path(self) -> str:
        """
        Gets the current file path with the placeholder for the year replaced by
        the current year.

        This method replaces the "%YEAR%" keyword in the file path with the actual
        current year retrieved via a helper function.

        :return: The updated file path with the year properly replaced.
        :rtype: str
        """
        dt = datetime.now(CONFIG[Settings.LOCAL_TIMEZONE])
        return self._pathPattern.replace("%YEAR%", dt.strftime("%Y")).replace("%MONTH%", dt.strftime("%m_%b"))

    def read(self) -> Any:
        """
        Reads data using the current file path through the parent `read` method.

        Updates the instance's file path based on the current year, then calls and
        returns data from the parent read operation. When the year advances, a new
        file is created with default content.

        :return: Data read from the file
        :rtype: Any
        """
        self.path = self.get_current_file_path()
        return super().read()

    def update(self, updater):
        """
        Updates the current file path and invokes the parent class update method.

        :param updater: The object used to perform the update operation.
        :return: The result of the update operation from the parent class method.
        """
        self.path = self.get_current_file_path()
        return super().update(updater)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _now_utc_str() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec='milliseconds') + "Z"


