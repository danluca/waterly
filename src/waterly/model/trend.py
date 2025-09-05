from .measurement import Measurement, convert_measurement

class Trend:
    """
    Represents a trend which holds and manages a collection of sampled values.

    The class provides functionality to add, retrieve, and manage a list of
    sampled values with a maximum defined size. It supports basic operations
    such as adding values, retrieving current data, and ensuring the list does
    not exceed its maximum size through trimming older entries.

    :ivar name: Name of the trend.
    :type name: str
    :ivar unit: Unit of measurement for the trend values.
    :type unit: str
    :ivar data: List maintaining added trend values.
    :type data: list[Measurement]
    :ivar maxSamples: Maximum number of samples the trend can hold.
    :type maxSamples: int
    """
    def __init__(self, name: str, unit: str, max_samples: int = 5000):
        """
        Initializes a new instance of the class with the provided name, unit, and optional
        maximum number of samples. The data list is initialized as an empty collection to
        store the numerical samples.

        :param name: The identifier or title associated with the instance.
        :type name: str
        :param unit: The unit of measurement related to the data values.
        :type unit: str
        :param max_samples: Optional maximum number of samples that can be stored. Defaults
                            to 5000 if not provided.
        :type max_samples: int
        """
        self.name: str = name
        self.unit: str = unit
        self.data: list[Measurement] = []
        self.maxSamples = max_samples

    def add_value(self, value: Measurement):
        """
        Adds a value to the data list and performs a trim operation.

        This method appends the provided value to the internal `data` list. Once the
        value is appended, the `trim` method is called to process or limit the contents
        of the `data` list.

        :param value: Value to be added to the data list.
        """
        self.data.append(value)
        self.trim()

    @property
    def values(self):
        """
        Gets the collection of data stored in the object.

        :return: The data stored in the object.
        :rtype: list[Measurement]
        """
        return self.data

    @property
    def size(self):
        """
        Returns the number of elements in the `data` attribute.

        :return: The count of elements in `data`.
        :rtype: int
        """
        return len(self.data)

    @property
    def max_size(self):
        """
        Retrieves the maximum sample size.

        This method returns the maximum number of samples that can be stored in this trend.

        :return: The maximum number of samples (`maxSamples`)
        :rtype: int
        """
        return self.maxSamples

    def trim(self):
        """
        Trims the data list to retain only the most recent `maxSamples` elements.
        This is achieved by slicing the data list from the end, utilizing the
        `maxSamples` attribute to determine the number of elements to preserve.

        :return: None
        """
        self.data = self.data[-self.maxSamples:]

    def clear(self):
        """
        Clears all items from the internal data structure.

        This method removes all elements stored in the internal data container,
        effectively resetting its state to be empty.

        :return: None
        """
        self.data.clear()

    def json_encode(self):
        return {
            "__type__": "Trend",
            "name": self.name,
            "unit": self.unit,
            "maxSamples": self.maxSamples,
            "data": self.data
        }

    @staticmethod
    def json_decode(obj):
        if "__type__" in obj and obj["__type__"] == "Trend":
            name = obj.get("name")
            unit = obj.get("unit")
            max_samples = obj.get("maxSamples")
            data = obj.get("data")
            t = Trend(name, unit, max_samples)
            t.data = data
            for d in t.data:
                d._unit = unit
            return t
        return None


class TrendSet:
    """
    Represents a collection of trends, categorized by zones, allowing for the addition, retrieval,
    and modification of trend data.

    This class is designed to manage multiple trends associated with different zones. Each trend
    is initialized with a name, unit, and maximum sample size. The class provides functionalities
    to add values to specific zone trends, retrieve trends by zone, clear all trend data, and apply
    functions to either specific trends or all trends simultaneously.

    :ivar trends: Stores the trends for each zone, where keys are zone names and values are
        corresponding `Trend` objects.
    :type trends: Dict[str, Trend]
    """
    def __init__(self, zone: list[str], name: str, unit: str, max_samples: int = 5000):
        """
        Initializes a collection of trends, each associated with a specific zone. The trends are used to track
        a specified metric within those zones, allowing for consistent monitoring and sampling. A maximum
        number of samples can be specified to limit memory usage.

        :param zone: A list of zone names for which trends will be created.
        :type zone: list[str]
        :param name: The name of the metric being tracked for each trend.
        :type name: str
        :param unit: The unit of the metric being measured.
        :type unit: str
        :param max_samples: The maximum number of samples to be held per trend. Defaults to 5000.
        :type max_samples: int
        """
        self._name: str = name
        self.trends: dict[str, Trend] = {}
        for zone_name in zone:
            self.trends[zone_name] = Trend(name, unit, max_samples)

    @property
    def name(self) -> str:
        """
        Retrieves the name of the trend.

        :return: The name of the trend.
        :rtype: str
        """
        return self._name

    def add_value(self, zone: str, value: Measurement) -> None:
        """
        Adds a new measurement value to the specified zone's trends.

        :param zone: The identifier of the zone where the measurement will be added.
        :type zone: str
        :param value: The measurement value to be added to the zone trends.
        :type value: Measurement
        :return: None
        """
        self.trends[zone].add_value(value)

    def trend(self, zone: str) -> Trend:
        """
        Retrieves the trend for the provided zone.

        This method looks up a specific trend based on the provided zone
        identifier and returns the corresponding trend information.

        :param zone: The zone identifier for which the trend information is requested.
        :type zone: str
        :return: The corresponding trend information for the given zone.
        :rtype: Trend
        """
        return self.trends[zone]

    def clear(self) -> None:
        """
        Clears all trends stored in the object.

        This method iterates through all trends in the `trends` dictionary and clears them individually.

        :return: None
        """
        for trend in self.trends.values():
            trend.clear()

    def update(self, zone: str, func) -> None:
        """
        Updates the trend data for a given zone by applying a provided function.

        The method modifies the data of the specified zone by passing it
        to the given function. This is used to dynamically manipulate or
        update the trend data associated with a zone.

        :param zone: The name of the zone whose data will be updated.
        :type zone: str
        :param func: A function that modifies the current data for the specified zone.
        :return: None
        :rtype: None
        """
        func(self.trends[zone].data)

    def update_all(self, func) -> None:
        """
        Applies a given function to the data of all trends in the collection.

        This method iterates over all trends in the `trends` dictionary and applies the
        provided function to each trend's data. The operation is in-place and modifies the
        data of each trend based on the behavior of the provided function.

        :param func: A callable that takes a single argument and performs an operation
            on the `data` attribute of each trend in the `trends` dictionary.
        :return: None
        """
        for trend in self.trends.values():
            func(trend.data)

    def json_encode(self):
        return {
            "__type__": "TrendSet",
            "name": self.name,
            "trends": self.trends
        }

    @staticmethod
    def json_decode(obj):
        if "__type__" in obj and obj["__type__"] == "TrendSet":
            name = obj.get("name")
            trends = obj.get("trends")
            t = TrendSet([], name, "")
            t.trends = trends
            return t
        return None