#include <iostream> //for cout

#include "rtmaps_api.h"


// This sample illustrate the use of maps_save_diagram and 	maps_overwrite_diagram.
// Those two functions save the "current diagram", i.e. the current state of RTMaps,
// into an .rtd diagram.
// maps_save_diagram does nothing if the file already exists.
// These functions require a Studio license key (within e.g. a Developer license)

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

	std::cout << "Save diagram as saved_diagram..." << std::endl;
	maps_save_diagram_as("saved_diagram.rtd");

	//Change the diagram and save again
	maps_parse("v.nbInputs = 5");
	maps_parse("RandomImage img");
	maps_parse("img.outputIplImage -> v.input_1");

	std::cout << "Repeat save: it should fail because the file exists..." << std::endl;
	maps_save_diagram_as("saved_diagram.rtd");

	maps_parse("RandomCANFrames can");
	maps_parse("can.output -> v.input_2");
	std::cout << "Overwrite our diagram: it should succeed..." << std::endl;
	maps_save_diagram_as("saved_diagram.rtd", true);

	std::cout << "Overwrite a non-existing file: should succeed..." << std::endl;
	maps_save_diagram_as("overwrite_diagram.rtd", true);

	std::cout << "Save to an ill-formed file name: should fail..." << std::endl;
	maps_save_diagram_as("\\bad_path.rtd");

	std::cout << "Save to an empty file name: should fail..." << std::endl;
	maps_save_diagram_as("");

	std::cout << "Save to a NULL file name: should fail..." << std::endl;
	maps_save_diagram_as(NULL);

	maps_exit();

	return 0;
}
