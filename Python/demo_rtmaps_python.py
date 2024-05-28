#!/usr/bin/env python3
# coding=utf-8
#
#  Copyright (C) INTEMPORA S.A.S
#  ALL RIGHTS RESERVED.
#
import time
import sys
import os
rtmaps_api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rtmaps")
sys.path.insert(0, rtmaps_api_path)
from rtmaps import RTMapsWrapper

root_folder = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "linux" or sys.platform == "linux2":
    diagram_path = os.path.join(root_folder, "samples", "demo_ergo_linux.rtd")
elif sys.platform == "win32":
    diagram_path = os.path.join(root_folder, "samples", "demo_ergo.rtd")

dbc_path = os.path.join(root_folder, "samples", "databases", "demo_car.dbc")
rec_path = os.path.join(root_folder, "samples", "databases", "demo_ergo", "RecFile_5_20140729_221909.rec")

# Start an RTMaps Runtime engine instance, with console for logging
# and x11 module (under Linux) if started with a graphical environment for potential display.
# (could be also --no-x11 if started without such a graphical environment on Linux)
if sys.platform == "linux" or sys.platform == "linux2":
    rtmaps = RTMapsWrapper("--console", "--x11")
elif sys.platform == "win32":
    rtmaps = RTMapsWrapper("--console")

rtmaps.parse("loaddiagram <<" + diagram_path + ">>")  # Load the post-processing diagram.

rtmaps.parse("Player_1.file = <<" + rec_path + ">>")  # Set the dataset to play back in the Player component.

rtmaps.parse("CANDecoder_6.database=<<" + dbc_path + ">>")  # Set the .dbc file in the CAN Decoder component.


# Start post-processing
rtmaps.run()

# Periodically test progress, report about it, then shutdown.
player_percentage = rtmaps.get_integer_property("Player_1.percentage")
last_reported_percentage = 0
last_report_time = time.time()
while player_percentage < 100:
    if (player_percentage - last_reported_percentage >= 10) or (time.time() - last_report_time > 1):
        print("RTMaps progress... {}%".format(player_percentage))
        last_reported_percentage = player_percentage
        last_report_time = time.time()
    time.sleep(0.1)
    player_percentage = rtmaps.get_integer_property("Player_1.percentage")
last_rtmaps_time = rtmaps.get_current_time()
last_dataset_time = rtmaps.get_integer_property("Player_1.last")
time.sleep(0.5)
rtmaps.shutdown()


