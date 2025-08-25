# Water control system for garden

## Setup
The system is controlled by a Raspberry Pi Zero 2W and a RS485 bus - 
all in a single Waveshare RPi Zero Relay housing.

## Overview
There are three valves controlled by relays at output device addresses 16, 19, 20.
Each valve covers a different zone of the garden. Each zone has a humidity sensor (SEN0604).
Zone 2 has also a nitrogen-phosphorus-potassium sensor (SEN0605).
All sensors are connected to the RS485 bus.

## Humidity
The system monitors the humidity of the garden zones throughout the day and schedules watering.
Watering is done one zone at a time starting at 8:30pm. Each shift of watering lasts 10 minutes, 
or until the humidity of the zone is above 70%.

Watering is canceled for the day if the weather forecast is rainy. The system connects every 6 hours 
to a free API weather forecast service and checks the forecast for the next 24 hours. If the forecast 
is rainy over 60% chance, the system cancels the watering.

## Nitrogen, Phosphorus and Potassium
The system monitors the N, P and K levels of the garden zones throughout the day and records a trend.
If the levels are out of bounds, the system notifies the user through the website for fertilization.

## Water consumption
The system monitors the water consumption through a pulse counter connected at GPIO 21 from a GREDIA 
water flow sensor. The specification says that the sensor's pulse frequency is 5.5 times water debit in litters/minute.
The system calculates the water consumption in liters/day or gallons/day and records it in a trend.

## Website
The website is a simple web management system for the watering system. It displays the current humidity 
and N, P and K levels of the garden and trends accumulated since the beginning of the season.
It allows changing the watering schedule and fertilization alert settings.




