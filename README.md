# Water control system for garden

## Overview
This is a water control system for a garden. It monitors the humidity, pH, temperature, N, P and K levels of the garden 
zones throughout the day and schedules watering if the weather forecast is not rainy enough to cover the water needs of 
the garden. 

The system monitors the water consumption and records a trend.
The system provides a website for displaying the trended values of the sensor measurements and can also 
serve as a notification mechanism for the user if the levels are out of bounds for fertilization. 
An important feature of the website is that it allows the user to change the watering schedule and 
adjust system operating parameters. 

The system is controlled by a Raspberry Pi Zero 2W and a RS485 bus - all in a single Waveshare RPi Zero Relay housing.

### Water control system
There are three Orbit water valves (same type of system for lawn irrigation) controlled by relays connected at 
RPI GPIO output device addresses 16, 19, 20.
Each valve covers a different zone of the garden. The valves operate at 24 VAC, hence the need to engage relays.

### Sensors
The system reads the temperature, humidity, pH, Nitrogen/Phosphorous/Potassium of the garden zones through a set of 
DFRobot sensors connected through a RS485 bus to the Raspberry Pi. The RS485 bus is provided by the SP3485 chip
of the Waveshare RPi Zero Relay housing, connected to the Raspberry Pi serial port.

### Humidity
Each zone has a humidity sensor (SEN0604) connected through a RS485 bus to the Raspberry Pi.
The system monitors the humidity of the garden zones throughout the day and schedules watering.
Watering is done one zone at a time starting at 8:30pm. Each shift of watering lasts 10 minutes, 
or until the humidity of the zone is above 70%.

Watering is canceled for the day if the weather forecast is rainy. The system connects every 6 hours 
to a free API weather forecast service and checks the forecast for the next 24 hours. If the forecast 
is rainy over 60% chance with sufficient rainfall, the system cancels the watering.

### Nitrogen, Phosphorus and Potassium
Zone 2 is the only one that has also a nitrogen-phosphorus-potassium sensor (SEN0605).
The system monitors the N, P and K levels of the garden zones throughout the day and records a trend.
If the levels are out of bounds, the system notifies the user through the website for fertilization.

### Water consumption
The system monitors the water consumption through a pulse counter connected at GPIO 21 from a GREDIA 
water flow sensor. The sensor is connected to the Raspberry Pi via an optocoupler due to operating and signal 
voltage differences - sensor operates at 5-24 VDC, Raspberry Pi at 3.3 VDC. The optocoupler frequency response 
is adequate for the range of values the sensor can measure on the residential water system.

The specification says that the sensor's pulse frequency is 5.5 times water debit in litters/minute.
The system calculates the water consumption in liters/day or gallons/day and records it in a trend.

### Website
The website is a simple web management system for the watering system. It displays the current humidity 
and N, P and K levels of the garden and trends accumulated since the beginning of the season.
It allows changing the watering schedule and fertilization alert settings.

## Setup

### Parts List
#### Irrigation system
- 1 x [3 valves Orbit manifold](https://www.homedepot.com/p/Orbit-3-Valve-Inline-Manifold-Assembly-57253/202206757)
- 1 x [GREDIA water flow sensor](https://www.amazon.com/GRODIA-Sensor-Food-Grade-Flowmeter-Counter/dp/B07MY6LFPH/ref=pd_day0fbt_hardlines_d_sccl_2/141-1443129-8480303?pd_rd_w=3aSsR&content-id=amzn1.sym.06aea998-aa9c-454e-b467-b476407c7977&pf_rd_p=06aea998-aa9c-454e-b467-b476407c7977&pf_rd_r=P35P5YC4NSXM7682Z12C&pd_rd_wg=d8L4d&pd_rd_r=26e52950-42c6-4f66-ae71-dd618aafceeb&pd_rd_i=B07MY5ZN3Z&th=1)
- 1 x [Valves Box](https://www.homedepot.com/p/NDS-14-in-X-19-in-Rectangular-Valve-Box-Extension-and-Cover-Black-Extension-Green-ICV-Cover-115/100377392)
- 1 x [Drip Irrigation Kit](https://www.amazon.com/MIXC-Greenhouse-Irrigation-Distribution-Adjustable/dp/B08HCLFJCW/ref=sr_1_18?crid=2C3T35TT6ZM2T&dib=eyJ2IjoiMSJ9.3x9xKhnhYkriTWItFRjLqikhanpoaH8pzb2NztJYHqPG_FV8yXM_rhgnnpJAA_i12xzuUbL_MYtQdgp5IHM1gWX4ZDXKDrVAKGXSCivSFI3QW2tY5whje8K5uzSUYT2sBW7STYPuM-NANvlRM9Gu0nU4vN_GU3edtX75LNcbKvwcGvnN8gd-uyQc8_57ybLR89Q63k_Ylq4XMU5emcLxYEQPoO7ewuzxRJ-HHS1eC2AotIdCZaIIB-LACLBHJ_l2f_MVYAMtyo-Ye96mYb3xWtSchS2FiVbNvE3M8g_RboY.RyXDXyTscLIRJA09Vao5O3H3BtysZj4DwcTQCYXSgrU&dib_tag=se&keywords=drip%2Birrigation%2Bsystem&qid=1745726488&sprefix=drip%2Caps%2C216&sr=8-18&th=1)
- 1 x [Orbit manifold double swivel union](https://www.homedepot.com/p/Orbit-Manifold-Double-Swivel-Union-57184/202206762)
- 1 x [Orbit valve manifold 3/4" adapter - 5 pack](https://www.amazon.com/gp/product/B07B8BQ2S1/ref=sw_img_1?smid=A3MIP8D2FH3WRX&th=1)
- 3 x [Double Female Adapter](https://www.homedepot.com/p/Melnor-Metal-Double-Female-Adapter-59Z-FB-HD/206480253)
- 1 x [Flexible Stainless Steel Supply Line](https://www.homedepot.com/p/Everbilt-3-4-in-FIP-x-3-4-in-FIP-x-24-in-Stainless-Steel-Water-Heater-Supply-Line-EBBC-07-24a/206527409)

#### Sensors
- 3 x [DF Robot Moisture, Temperature, pH sensor](https://www.dfrobot.com/product-2830.html)
- 1 x [DF Robot Nitrogen, Phosphorus, Potassium sensor](https://www.dfrobot.com/product-2819.html)
- 1 x [Gredia water flow sensor](https://www.amazon.com/GRODIA-Sensor-Food-Grade-Flowmeter-Counter/dp/B07MY6LFPH/ref=pd_day0fbt_hardlines_d_sccl_2/141-1443129-8480303?pd_rd_w=3aSsR&content-id=amzn1.sym.06aea998-aa9c-454e-b467-b476407c7977&pf_rd_p=06aea998-aa9c-454e-b467-b476407c7977&pf_rd_r=P35P5YC4NSXM7682Z12C&pd_rd_wg=d8L4d&pd_rd_r=26e52950-42c6-4f66-ae71-dd618aafceeb&pd_rd_i=B07MY5ZN3Z&th=1)
- 1 x [Optocoupler signal adapter](https://www.amazon.com/NOYITO-1-Channel-Optocoupler-Optoelectronic-Anti-Interference/dp/B0B5383L69/ref=asc_df_B0B5373L4P?mcid=04249beddda531019854539f9e085c81&hvocijid=16912343195326707372-B0B5373L4P-&hvexpln=73&tag=hyprod-20&linkCode=df0&hvadid=721245378154&hvpos=&hvnetw=g&hvrand=16912343195326707372&hvpone=&hvptwo=&hvqmt=&hvdev=c&hvdvcmdl=&hvlocint=&hvlocphy=9019698&hvtargid=pla-2281435175938&th=1)
- 1 x [100 ft CAT 5 cable](https://www.homedepot.com/p/Southwire-300-ft-Tan-24-4-Solid-CU-CAT5e-CMR-CMX-Indoor-Outdoor-Data-Cable-56917648/313505342)
- 3 x [IP68 3-way 4 pin waterproof junction](https://www.amazon.com/dp/B0DQDBGP9S?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_2)

### Controller
- 1 x [Waveshare RPi Zero Relay](https://www.waveshare.com/rpi-zero-relay.htm)
- 1 x [Raspberry Pi Zero 2W](https://www.raspberrypi.org/products/raspberry-pi-zero-2-w/)
- 1 x [Waterproof plastic enclosure](https://www.amazon.com/dp/B07RVN91WB?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_4)
- 1 x [24VAC adjustable power adapter](https://www.amazon.com/UMLIFE-Converter-2-5-35V-Regulator-Adjustable/dp/B094ZTG5S8/ref=pd_sim_hxwPM1_sspa_dk_detail_d_sccl_4_3/141-1443129-8480303?pd_rd_w=iDI1m&content-id=amzn1.sym.3a852a98-d65f-4301-9bd0-9b589b14d1ef&pf_rd_p=3a852a98-d65f-4301-9bd0-9b589b14d1ef&pf_rd_r=KQZPXC2HY5G4Y29H4DX3&pd_rd_wg=lpw78&pd_rd_r=813f6b57-5bff-474c-800e-0ae3174427d8&pd_rd_i=B094ZTG5S8&th=1)
- 1 x [24VAC transformer](https://www.amazon.com/dp/B0BKS12NCW/ref=sspa_dk_detail_4?pd_rd_i=B0BKS12NCW&pd_rd_w=udlnP&content-id=amzn1.sym.f2f1cf8f-cab4-44dc-82ba-0ca811fb90cc&pf_rd_p=f2f1cf8f-cab4-44dc-82ba-0ca811fb90cc&pf_rd_r=D5GFYF526X2P83K2XK5M&pd_rd_wg=GUVIS&pd_rd_r=9a9f4e87-8e74-4752-b61d-acdf98c39043&s=electronics&sp_csd=d2lkZ2V0TmFtZT1zcF9kZXRhaWxfdGhlbWF0aWM&th=1)
- 5 x [IP68 2-way 4 pin waterproof coupler](https://www.amazon.com/dp/B0CT5SF9G1?ref_=ppx_hzsearch_conn_dt_b_fed_asin_title_3)


