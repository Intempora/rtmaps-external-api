################################################################################
# File:    rtmaps_runtime_ext.py
# Company: dSPACE GmbH
#
# Copyright 2024, dSPACE GmbH. All rights reserved.
################################################################################

if __name__ == "__main__":  # if called from subprocess
    from rtmaps import RTMapsAbstraction
else:  # if called from import
    from rtmaps import RTMapsAbstraction

import time
import argparse
import sys
import os
import distutils.util
import textwrap
import datetime
import re

DEATH_TIMEOUT = 1800  # seconds (Timeout to prevent deadlocks when a Death() method never returns)

g_errorOccurred = False
g_timeoutErrorOccurred = False
g_exitRequest = False
g_tolerateAllErrors = False
g_logFileHandler = None
g_componentsInDeath = set()
g_rtmapsFirstErrorMessage = ""

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


__version__ = "1.0.0"


def log(message):
    """Writes the message to the log file."""
    logMessage = "[Wrapper][{}] {}".format(datetime.datetime.now(), message)
    print(logMessage)
    if g_logFileHandler:
        g_logFileHandler.write(logMessage + "\n")
        g_logFileHandler.flush()


def errorIsTolerated(message):
    """Checks if message is an error and is tolerated."""
    return bool(
        re.search(
            "Error: component .*: (Interrupted|eof|Unable to request data!)|Error: component dSPACE_StructFilter.*|Error: Package .* already registered.*",
            message,
        )
    )


def errorIsToleratedInShutdown(message):
    """Checks if message is an error and is tolerated during shutdown."""
    return bool(re.search("Error: component .*: (Got receive exception:|Unable to request data!|Error while processing data: ) .*", message))


def errorIsTimeoutError(message):
    """Checks if message is a timeout error."""
    return bool(
        re.search(
            "Error: component .*: (Timeout reached before packet arrival --> shutting down|Timeout reached before all players are done --> shutting down)",
            message,
        )
    )


def manageDeathMethods(message):
    """Registers/Deregisters components in Death."""
    if not message.startswith("Info: component"):  # only consider info messages by components
        return
    component = message.split(" ")[2][:-1]
    command = message.split(" ")[-1]
    if command == "LONG_DEATH":
        g_componentsInDeath.add(component)
    elif command == "DEATH_FINISHED":
        g_componentsInDeath.remove(component)


def onRtmapsReport(dummy, level: int, msg: bytes):
    """RTMaps message handle."""
    global g_errorOccurred, g_exitRequest, g_logFileHandler, g_timeoutErrorOccurred, g_rtmapsFirstErrorMessage
    REPORT_INFO = 0
    REPORT_WARNING = 1
    REPORT_ERROR = 2
    REPORT_CMD = 3

    message = msg.decode("utf-8")
    manageDeathMethods(message)
    logMessage = "[Runtime][{}] {}".format(datetime.datetime.now(), message)
    print(logMessage)

    if g_logFileHandler:
        g_logFileHandler.write(logMessage + "\n")
        g_logFileHandler.flush()

    if level == REPORT_ERROR:
        if g_tolerateAllErrors or errorIsTolerated(message) or (g_exitRequest and errorIsToleratedInShutdown(message)):
            log("Ignoring this error, because it is explicitly tolerated.")
        else:
            log("TRIGGERING ABORT due to unexpected error ...")
            if not g_rtmapsFirstErrorMessage:
                g_rtmapsFirstErrorMessage = message
            if errorIsTimeoutError(message):
                g_timeoutErrorOccurred = True
            g_errorOccurred = True
    if level == REPORT_CMD and message == "exit" and sys.platform == "win32":
        # Under Linux, the RTMaps exit command leads to a shutdown+KeyboardInterrupt.
        # Under Windows, neither a shutdown nor a KeyboardInterrupt happens.
        # This is why this case must be handled explicitly under Windows.
        g_exitRequest = True


def diagramIsRunning(maps):
    """Returns RTMaps diagram state."""
    return maps.get_current_time() != 0


def appendTimeStampToLogFile(logFile: str):
    """Appends a current timestamp as prefix to the log file name."""
    try:
        if logFile:
            logFile = os.path.abspath(logFile)
            logFileBaseName = os.path.basename(logFile)
            if logFileBaseName:
                logFileBaseNameWithTimeStamp = timestamp + "_" + logFileBaseName
                logFile = logFile.replace(logFileBaseName, logFileBaseNameWithTimeStamp)
                os.makedirs(os.path.dirname(logFile), exist_ok=True)
                return logFile
        return None
    except Exception as ex:
        # Something went wrong while processing the path, e.g. path might not be a valid file path
        log("Log file does not seem to be valid, file logging not possible")
        return None


def main(diagramFile: str, logFile: str):
    """Main method for the execution of the RTMaps diagram/script."""
    global g_errorOccurred, g_exitRequest, g_tolerateAllErrors, g_logFileHandler, g_timeoutErrorOccurred

    logFile = appendTimeStampToLogFile(logFile)
    if logFile:
        g_logFileHandler = open(logFile, "a")

    maps = None
    try:
        diagramFile = os.path.abspath(diagramFile)
        os.chdir(os.path.dirname(diagramFile))

        tolerateAllErrorsEnvVar = os.getenv("ADT_TOLERATE_RTMAPS_ERRORS")
        if tolerateAllErrorsEnvVar is not None:
            try:
                g_tolerateAllErrors = bool(distutils.util.strtobool(tolerateAllErrorsEnvVar))
            except:
                raise Exception("Environment variable ADT_TOLERATE_RTMAPS_ERRORS has invalid truth value '{}'".format(tolerateAllErrorsEnvVar))

        log("Initializing RTMaps engine")
        maps = RTMapsAbstraction()
        maps.register_report_reader(onRtmapsReport)
        log("Loading diagram")
        maps.load_diagram(diagramFile)
        if not diagramIsRunning(maps) and not g_errorOccurred:
            log("Diagram is not running --> calling 'run'")
            maps.run()
        while diagramIsRunning(maps):
            time.sleep(1)
            if g_errorOccurred:
                log("Stopping diagram, because an error was reported!")
                maps.shutdown()
            if g_exitRequest:
                log("Stopping diagram, because exit was requested")
                maps.shutdown()

        log("Waiting for component shutdown")
        time.sleep(2)
    except Exception as ex:
        log("Exception '{}': {}".format(type(ex).__name__, str(ex)))
        g_errorOccurred = True
    except KeyboardInterrupt:
        log("Exit/Keyboard interrupt occurred")
        g_exitRequest = True
        if maps:
            maps.shutdown()

    waitForDeathStarted = datetime.datetime.now()
    while g_componentsInDeath and not g_errorOccurred:  # waiting for DEATH_FINISHED from all registered death methods
        if datetime.datetime.now() - waitForDeathStarted > datetime.timedelta(seconds=DEATH_TIMEOUT):
            g_errorOccurred = True
            log(f"Death timeout while {g_componentsInDeath} is still in Death() method.")
            break
        time.sleep(1)

    exitCode = 0
    if g_errorOccurred:
        exitCode = 2 if g_timeoutErrorOccurred else 1
    log("Terminating process with exit code {}".format(exitCode))
    if g_logFileHandler:
        g_logFileHandler.close()
        g_logFileHandler = None
    logErrorSummary(g_rtmapsFirstErrorMessage)
    return exitCode


def logErrorSummary(errorMessage: str):
    """
    Creates error summary with the from the provided error message.
    Reformats the error output to more easily point the user to the problem.
    """
    if not errorMessage:
        return

    errorMessageLines = errorMessage.splitlines()

    if bool(re.search("Error: component .*: Traceback \(most recent call last\)", errorMessageLines[0])):
        errorMessageLines = [errorMessageLines[0].split("Traceback")[0], errorMessageLines[-1]]

    log("### Error summary: ###")
    for line in errorMessageLines:
        log(f"# {line}")
    log("######################")
    sys.stderr.write("\n".join(errorMessageLines))


def cli(argList):
    description = textwrap.dedent(
        """
        This script implements an "extended" runtime wrapper to execute RTMaps diagrams and scripts.
        The script terminates immediately, if an error occurs during diagram execution. The error 
        status is returned via exit code of the process (0=success, 1=error occurred).
        The file argument (script or diagram) is mandatory and the diagram will automatically be 
        started.
        For compatibility with rtmaps_runtime.exe, the optional arguments "--run" and "--no-X11"
        are allowed, but have no effect.
        
        Environment variables:
          ADT_TOLERATE_RTMAPS_ERRORS  If set to "true" or "1", an error will not cause a shutdown                 
    """
    )
    parser = argparse.ArgumentParser(description=description, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=str, help="Script or diagram to be executed")
    parser.add_argument("--run", dest="run", action="store_true", default=False, help="Only dummy option to be compatible with rtmaps_runtime")
    parser.add_argument("--no-X11", dest="noX11", action="store_true", default=False, help="Only dummy option to be compatible with rtmaps_runtime")
    parser.add_argument("--version", action="version", version="%(prog)s (" + __version__ + ")")
    parser.add_argument("--logfile", type=str, required=False, help="Path to log file in which the rtmaps runtime log should be saved.")
    args = parser.parse_args(argList)

    exitCode = main(diagramFile=args.file, logFile=args.logfile)
    sys.exit(exitCode)


if __name__ == "__main__":
    cli(sys.argv[1:])
