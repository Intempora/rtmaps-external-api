cmake_minimum_required(VERSION 3.10)

################################################################################
##     This file is part of RTMaps                                            ##
##     Copyright (c) Intempora S.A. All rights reserved.                      ##
################################################################################

project(BasicCppExternalAPI)

## IMPORTANT: Set the same C++ standard for the whole project ######################################

set(CMAKE_CXX_STANDARD          17)   # Proper C++ >= 11 is required
set(CMAKE_CXX_STANDARD_REQUIRED ON)   # Enforce the C++ standard requirement
set(CMAKE_CXX_EXTENSIONS        OFF)  # Non-portable compiler-specific extensions are NOT required

## IMPORTANT: Locate the RTMaps SDK ################################################################

if (NOT DEFINED RTMAPS_SDKDIR)
    if (DEFINED ENV{RTMAPS_SDKDIR})
        set(RTMAPS_SDKDIR "$ENV{RTMAPS_SDKDIR}" CACHE PATH "")  # Use the default RTMaps installation
    else()
        message(FATAL_ERROR "RTMAPS_SDKDIR not defined. Either pass -D\"RTMAPS_SDKDIR=...\" to CMake or define an RTMAPS_SDKDIR environment variable")
    endif()
endif()

include("${RTMAPS_SDKDIR}/templates.u/rtmaps.cmake")

if (CMAKE_SYSTEM_NAME STREQUAL "Linux")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,-rpath=${RTMAPS_SDKDIR}/bin")
endif()

add_executable(BasicCppExternalAPI src/rtmaps_external_api_basic_example.cpp)

target_link_libraries(BasicCppExternalAPI PRIVATE rtmaps_api)