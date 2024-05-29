#include <iostream> //for cout

#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#define Sleep(x) usleep((x)*1000)
#endif

#include "rtmaps_api.h"

int main (int argc, char* argv[])
{
	maps_init(0, NULL);
	
	//The 3 following lines build a very basic diagram.
	//It is usually more convenient to load an existing diagram:
	//maps_parse("loaddiagram <<diagram.rtd>>");
	maps_parse("Randint ri");
	maps_parse("DataViewer v");
	maps_parse("ri.outputInteger -> v.input_0");

	//use this line to get the RTMaps console into your own console
#ifdef WIN32
	maps_parse("load Win32Console");
#else
	maps_parse("load UnixConsole");
#endif

	std::cout << "Running RTMaps..." << std::endl;
	//The run function does not block.
	maps_run();

	std::cout << "Waiting 4 seconds..." << std::endl;
	Sleep(4000);
	
	int value;
	long long int timestamp;
	//note that wait4data is false, so the function returns the last value and does not block.
	int result = maps_read_int32("ri.outputInteger", MAPS_FALSE, &value, &timestamp);
	if (MAPS_OK == result){
		std::cout << "Read value: " << value << " with timestamp: " << timestamp << " microseconds" << std::endl;
	} else {
		std::cout << "Failed to read value. Error: " << result << std::endl;
	}

	maps_shutdown();
	maps_exit();

	return 0;	
}
