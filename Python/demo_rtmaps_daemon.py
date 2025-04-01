import time

from rtmaps import RTMapsDaemonWrapper, RTMapsEngineWrapper, RTMapsDefaults
import sys, os

if __name__ == '__main__':
    if sys.platform == "linux" or sys.platform == "linux2":
        rtmaps_install_path = "/opt/rtmaps"
        diagram_path = os.path.join(rtmaps_install_path, "samples", "demo_ergo_linux.rtd")
    elif sys.platform == "win32":
        rtmaps_install_path = os.environ.get(RTMapsDefaults.rtmaps_install_variable)
        diagram_path = os.path.join(rtmaps_install_path, "samples", "demo_ergo.rtd")
    else:
        raise AssertionError("Platform '{}' not supported by RTMapsPlugin.".format(sys.platform))

    dbc_path = os.path.join(rtmaps_install_path, "samples", "databases", "demo_car.dbc")
    rec_path = os.path.join(rtmaps_install_path, "samples", "databases", "demo_ergo", "RecFile_5_20140729_221909.rec")

    daemon = RTMapsDaemonWrapper()
    daemon.connect("127.0.0.1", 10056, "","")
    daemon.delete_all_engines()
    engine = daemon.create_engine("Test", diagram_path)
    engine.connect(10070)

    engine.parse("Player_1.file = <<" + rec_path + ">>")  # Set the dataset to play back in the Player component.
    engine.parse("CANDecoder_6.database=<<" + dbc_path + ">>")  # Set the .dbc file in the CAN Decoder component.

    # Start post-processing
    engine.run()

    try:
        # Periodically test progress, report about it, then shutdown.
        player_percentage = engine.get_integer_value("Player_1.percentage")
        last_reported_percentage = 0
        last_report_time = time.time()
        while player_percentage < 50:
            if (player_percentage - last_reported_percentage >= 10) or (time.time() - last_report_time > 1):
                print("RTMaps progress... {}%".format(player_percentage))
                last_reported_percentage = player_percentage
                last_report_time = time.time()
            time.sleep(0.1)
            player_percentage = engine.get_integer_value("Player_1.percentage")
            engine.send_integer_value("Gauge_6.input", player_percentage)
        last_rtmaps_time = engine.get_current_time()
        last_dataset_time = engine.get_integer_value("Player_1.last")
        time.sleep(0.5)
        engine.shutdown()
    except Exception as e:
        print(e)
        daemon.delete_all_engines()
