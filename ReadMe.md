# Getting started

This repository contains APIs to interact with RTMaps runtime from external process. Several languages are possible, including C++, Python, Matlab...

We do recommend Python and C++ since these are the most tested and used languages for RTMaps, by far.

For each language you have a dedicated folder containing the source code as well as code samples.

## About DLLs and Shared objects (.so)

To execute correctly, the exe should find rtmaps.dll and rtmaps_fd.dll, and many other dlls. Same problem with .so on Linux systems.

### Windows
On Windows, C:\ProgramFiles\Intempora\RTMaps 4\bin should be added the environment variable called `PATH`. Another option, put all DLLs from this bin/ directory next to your executable.

### Linux
On Linux systems, best way to use `rpath` during compilation. It will indicate location of necessary shared objects. This works very well.