# coding=utf-8
#
#  Copyright (C) INTEMPORA S.A.S
#  ALL RIGHTS RESERVED.

import atexit
import os
import sys
import logging
from pathlib import Path
import time
import xml.etree.ElementTree as et
from ctypes import Structure, POINTER, c_double, c_int32, c_int64, c_uint32, c_int8, sizeof
from ctypes import byref, create_string_buffer, cdll
from ctypes import c_void_p, c_char_p
from ctypes import c_int, c_long, c_longlong, c_double

from numpy import int64
if sys.platform == "win32":
    from ctypes import WINFUNCTYPE
else:
    from ctypes import CFUNCTYPE

invalid_name_characters = ('.', "=", "<", ">", "(", ")", ",", ":", "|", "-", "\"", "/", "\\")
valid_input_properties = ("subsampling", "readerType")
valid_output_properties = ("periodic", "fifosize", "subsampling")

class RTMapsException(Exception):
    __module__ = Exception.__module__
    '''Raise this exception to indicate errors within the RTMaps context'''


class RTMapsDefaults(object):
    rtmaps_install_variable = "RTMAPS_SDKDIR"


class _Singleton(type):
    """ A metaclass that creates a Singleton base class when called. """
    _instances = {}

    def on_exit(cls):
        del cls._instances[cls]

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(_Singleton, cls).__call__(*args, **kwargs)
            atexit.register(cls.on_exit)
        return cls._instances[cls]


class Singleton(_Singleton('SingletonMeta', (object,), {})): pass


class maps_ioelt_metadata_t(Structure):
            _fields_=[ 
                ("cbSize",c_int32),
                ("flags",c_uint32),
                ("timestamp",c_int64),
                ("timeOfIssue",c_int64),
                ("frequency",c_int64),
                ("quality",c_int32),
                ("misc1",c_int32),
                ("misc2",c_int32),
                ("misc3",c_int32),
            ]
            def __init__(self, cbSize=48): # setting default values
                super().__init__(cbSize)


class RTMapsWrapper(Singleton):
    """
    A very basic wrapper as received from Intempora with small improvements. It is intended as a direct interface
    to the underlying librtmaps.so/rtmaps.dll.
    The complete API as provided by librtmaps.so/rtmaps.dll is not covered yet, if you intend to extend it, please check
    the header file located at: C:\\Program Files\\Intempora\\RTMaps 4\\sdk\\*\\include\\rtmaps_api.h or
    /opt/rtmaps/sdk/*/include/rtmaps_api.h.
    """
    REPORT_INFO = 0
    REPORT_WARNING = 1
    REPORT_ERROR = 2

    def __init__(self, *args):

        if sys.platform == "linux" or sys.platform == "linux2":
            self.rtmaps_install_path = "/opt/rtmaps"
            rtmaps_library_filename = os.path.join(self.rtmaps_install_path, "lib", "librtmaps.so")
        elif sys.platform == "win32":
            self.rtmaps_install_path = os.environ.get(RTMapsDefaults.rtmaps_install_variable)
            rtmaps_library_filename = os.path.join(self.rtmaps_install_path, "bin", "rtmaps.dll")
            os.environ['PATH'] = os.path.join(self.rtmaps_install_path, "bin") + os.pathsep + os.environ['PATH']
        else:
            raise AssertionError("Platform '{}' not supported by RTMapsPlugin.".format(sys.platform))

        n_args = len(args)
        argc = c_int(n_args)
        argv = (c_char_p * n_args)()
        for i in range(n_args):
            argv[i] = args[i].encode('utf-8')

        try:
            self.lib = cdll.LoadLibrary(rtmaps_library_filename)
            self.lib.maps_init(argc, byref(argv))

        except:
            logging.error("Failed to load RTMaps library. "
                          "Please check environment variable '{}'!".format(RTMapsDefaults.rtmaps_install_variable))
            self.lib = None
            raise

        self._command_log = list()

    def __del__(self):
        if self.lib:
            self.lib.maps_exit()

    def run(self):
        self.lib.maps_run()

    def shutdown(self):
        self.lib.maps_shutdown()

    def reset(self):
        self._command_log.clear()
        self.lib.maps_reset()

    def _parse(self, command):
        response = self.lib.maps_parse(command.encode('utf-8'))
        if response != 0:
            raise RTMapsException("Error while parsing command '{}'".format(command))
        else:
            self._command_log.append(command)

    def register_package(self, package_name, package_folder=""):
        package_path = os.path.join(package_folder,  package_name)
        self._parse("register <<{}>>".format(package_path))

    def unregister_package(self, package_name):
        self._parse("unregister <<{}>>".format(package_name))

    def register_standard_package(self, package_name, package_sub_folder=""):
        package_path = os.path.join(self.rtmaps_install_path, "packages", package_sub_folder, package_name)
        self._parse("register <<{}>>".format(package_path))

    def report(self, message, level=REPORT_INFO):
        self.lib.maps_report(message.encode('utf-8'), level)
        
    def register_report_reader(self, cb):
        if sys.platform == "win32":
            CALLBACKTYPE = WINFUNCTYPE(None, c_void_p, c_int, c_char_p)
            self.decoratedcb = CALLBACKTYPE(cb)
            self.lib.maps_register_report_reader(self.decoratedcb, self.decoratedcb)
        else:
            CALLBACKTYPE = CFUNCTYPE(None, c_void_p, c_int, c_char_p)
            self.decoratedcb = CALLBACKTYPE(cb)
            self.lib.maps_register_report_reader(self.decoratedcb, self.decoratedcb)
        
    def play(self):
        self.lib.maps_play()

    def stop(self):
        self.lib.maps_stop()

    def pause(self):
        self.lib.maps_pause()

    def get_current_time(self):
        func = self.lib.maps_get_current_time
        func.argtypes = [POINTER(c_long)]
        current_time = c_long()
        func(byref(current_time))
        return current_time.value

    def get_integer_property(self, name):
        func = self.lib.maps_get_integer_property
        func.argtypes = [c_char_p, POINTER(c_long)]
        func.restype = c_int

        property_name = name.encode('utf-8')
        property_value = c_long()
        if func(property_name, byref(property_value)) == 0:
            return property_value.value
        else:
            return None
        
    def get_float_property(self, name):
        func = self.lib.maps_get_float_property
        func.argtypes = [c_char_p, POINTER(c_double)]
        func.restype = c_int

        property_name = name.encode('utf-8')
        property_value = c_double()
        if func(property_name, byref(property_value)) == 0:
            return property_value.value
        else:
            return None
        

    def get_string_property(self, name):
        size = c_int()
        self.lib.maps_get_string_property(name.encode('utf-8'), None, byref(size))
        buffer = create_string_buffer(size.value)
        self.lib.maps_get_string_property(name.encode('utf-8'), buffer, byref(size))
        return buffer.value.decode('utf-8')

    def get_enum_property(self, name):
        size = c_int()
        self.lib.maps_get_enum_property(name.encode('utf-8'), None, byref(size))
        buffer = create_string_buffer(size.value)
        self.lib.maps_get_enum_property(name.encode('utf-8'), buffer, byref(size))
        return buffer.value.decode('utf-8')

    def send_int32(self, name, value):
        func = self.lib.maps_send_int32
        func.argtypes = [c_char_p, c_int32]
        func.restype = c_int
        
        input_name = name.encode('utf-8')
        input_value = c_int32(value)

        return func(input_name, input_value)

    def send_int32_ts(self, name, value, timestamp):
        func = self.lib.maps_send_int32_ts
        func.argtypes = [c_char_p, c_int32, c_int64]
        func.restype = c_int
        
        input_name = name.encode('utf-8')
        input_value = c_int32(value)
        input_timestamp = c_int64(timestamp)

        return func(input_name, input_value, input_timestamp)

    def send_int64_ts(self, name, value, timestamp):
        func = self.lib.maps_send_int32_ts
        func.argtypes = [c_char_p, c_int64, c_int64]
        func.restype = c_int
        
        input_name = name.encode('utf-8')
        input_value = c_int64(value)
        input_timestamp = c_int64(timestamp)

        return func(input_name, input_value, input_timestamp)

    def read_int32(self, name, wait_for_data):
        func = self.lib.maps_read_int32
        func.argtypes = [c_char_p, c_int, POINTER(c_long), POINTER(c_longlong)]
        func.restype = c_int
        
        output_name = name.encode('utf-8')
        output_value = c_long()
        timestamp = c_longlong()
        wait_for_data_ = c_int(int(wait_for_data))

        if func(output_name, wait_for_data_, byref(output_value), byref(timestamp)) == 0:
            return output_value.value
        else:
            return None
    def read_int64(self, name, wait_for_data):
        func = self.lib.maps_read_int64
        func.argtypes = [c_char_p, c_int, POINTER(c_longlong), POINTER(c_longlong)]
        func.restype = c_int
        
        output_name = name.encode('utf-8')
        output_value = c_longlong()
        timestamp = c_longlong()
        wait_for_data_ = c_int(int(wait_for_data))

        if func(output_name, wait_for_data_, byref(output_value), byref(timestamp)) == 0:
            return output_value.value
        else:
            return None

    
    def read_int32_timeout(self, name, timeout):
        func = self.lib.maps_read_int32_timeout
        func.argtypes = [c_char_p, c_int64, POINTER(c_long), POINTER(c_longlong)]
        func.restype = c_int
        
        output_name = name.encode('utf-8')
        output_value = c_long()
        timestamp = c_longlong()
        timeout_ = c_int64(int64(timeout))

        result = func(output_name, timeout_, byref(output_value), byref(timestamp))
        if result == 0:
            return output_value.value
        else:
            return None

    def read_int64_timeout(self, name, timeout):
        func = self.lib.maps_read_int64_timeout
        func.argtypes = [c_char_p, c_int64, POINTER(c_long), POINTER(c_longlong)]
        func.restype = c_int
        
        output_name = name.encode('utf-8')
        output_value = c_long()
        timestamp = c_longlong()
        timeout_ = c_int64(int64(timeout))

        result = func(output_name, timeout_, byref(output_value), byref(timestamp))
        if result == 0:
            return output_value.value
        else:
            return None


    def read_float64_vector_timeout_meta(self, name, vector_size, timeout):
        class vector_of_doubles(Structure):
            _fields_ = [(f"elem{i}", c_double) for i in range(vector_size)] # vector type is dynamically created based on parameter vector_size

        func = self.lib.maps_read_float64_vector_timeout_meta
        func.argtypes = [c_char_p, c_int64, POINTER(vector_of_doubles), POINTER(c_int), POINTER(maps_ioelt_metadata_t)]
        func.restype = c_int
        
        output_name = name.encode('utf-8')
        timeout_ = c_int64(int64(timeout))
        output_vector = vector_of_doubles()
        vector_size_ = c_int(vector_size)
        meta = maps_ioelt_metadata_t()

        result = func(output_name, timeout_, byref(output_vector), byref(vector_size_), byref(meta))
        if result == 0:
            return [getattr(output_vector, a[0]) for a in output_vector._fields_]
        else:
            return None

    def read_user_structure_timeout_meta(self, component_dot_output, custom_structure_type, timeout):
        func = self.lib.maps_read_user_structure_timeout_meta
        func.argtypes = [c_char_p, c_int64, c_void_p, POINTER(c_int), POINTER(maps_ioelt_metadata_t)]
        func.restype = c_int
        
        custom_structure = custom_structure_type()

        output_name = component_dot_output.encode('utf-8')
        timeout_ = c_int64(int64(timeout))
        dataSize = c_int(sizeof(custom_structure))
        meta = maps_ioelt_metadata_t()

        result = func(output_name, timeout_, byref(custom_structure), byref(dataSize), byref(meta))
        if result == 0:
            return custom_structure
        else:
            return None


    def read_user_structure_vector_timeout_meta(self, component_dot_output, custom_structure_type, vector_size, timeout):
        func = self.lib.maps_read_user_structure_timeout_meta
        func.argtypes = [c_char_p, c_int64, c_void_p, POINTER(c_int), POINTER(maps_ioelt_metadata_t)]
        func.restype = c_int
        
        buffer_type = c_int8 * sizeof(custom_structure_type) * vector_size
        buffer = buffer_type()

        output_name = component_dot_output.encode('utf-8')
        timeout_ = c_int64(int64(timeout))
        dataSize = c_int(sizeof(buffer))
        meta = maps_ioelt_metadata_t()

        result = func(output_name, timeout_, byref(buffer), byref(dataSize), byref(meta))
        if result == 0:
            return [custom_structure_type.from_buffer(buffer, i * sizeof(custom_structure_type)) for i in range(vector_size)]
        else:
            return None


    def get_action_names_for_component(self, component):
        size = c_int()
        self.lib.maps_get_action_names_for_component(component.encode('utf-8'), None, byref(size))
        buffer = create_string_buffer(size.value)
        self.lib.maps_get_action_names_for_component(component.encode('utf-8'), buffer, byref(size))
        return buffer.value.decode('utf-8').split('|')

    def get_output_names_for_component(self, component):
        size = c_int()
        self.lib.maps_get_output_names_for_component(component.encode('utf-8'), None, byref(size))
        buffer = create_string_buffer(size.value)
        self.lib.maps_get_output_names_for_component(component.encode('utf-8'), buffer, byref(size))
        return buffer.value.decode('utf-8').split('|')
            
    def get_input_names_for_component(self, component):
        size = c_int()
        self.lib.maps_get_input_names_for_component(component.encode('utf-8'), None, byref(size))
        buffer = create_string_buffer(size.value)
        self.lib.maps_get_input_names_for_component(component.encode('utf-8'), buffer, byref(size))
        return buffer.value.decode('utf-8').split('|')

    def get_property_names_for_component(self, component):
        size = c_int()
        self.lib.maps_get_property_names_for_component(component.encode('utf-8'), None, byref(size))
        buffer = create_string_buffer(size.value)
        self.lib.maps_get_property_names_for_component(component.encode('utf-8'), buffer, byref(size))
        return buffer.value.decode('utf-8').split('|')
    def is_running(self):
        func = self.lib.maps_is_running
        func.argtypes = [POINTER(c_int)] # MAPS_BOOL is an int
        func.restype = c_int

        property_value = c_int()
        if func(byref(property_value)) == 0:
            return bool(property_value.value)

    def is_paused(self):
        func = self.lib.maps_is_paused
        func.argtypes = [POINTER(c_int)] # MAPS_BOOL is an int
        func.restype = c_int

        property_value = c_int()
        if func(byref(property_value)) == 0:
            return bool(property_value.value)
class RTMapsAbstraction(RTMapsWrapper):
    """ 
    A more abstract interface to the original RTMapsWrapper (yes, this name sucks but I could not think
    of a better one).
    
    It provides more convience features as it keeps track of all components added to the diagram. Furthermore, it checks if properties, inports or 
    outports do exists before executing the underlying commands. This class is not complete yet, feel free to add more features. 
    """
    def __init__(self):
        self._enable_checks = True
        self._components = set()
        if sys.platform == "linux" or sys.platform == "linux2":
            super(RTMapsAbstraction, self).__init__("--console", "--no-x11")
        elif sys.platform == "win32":
            super(RTMapsAbstraction, self).__init__("--console")

    def add_component(self, component_type: str, component_id: str, xpos = None, ypos = None, zpos = 0):
        if self._enable_checks:
            if component_id in self._components:
                raise RTMapsException("A component with name {} does already exist".format(component_id))
        command = "{} {}".format(component_type, component_id)
        self._parse(command)
        self._components.add(component_id)
        if (xpos is not None) and (ypos is not None):
            command = "set_location {} {:d} {:d} {:d}".format(component_id, int(xpos), int(ypos), int(zpos))
            self._parse(command)
    def remove_component(self, component_id: str):
        self.check_component_availability(component_id)
        command = "kill {}".format(component_id)
        self._parse(command)
        self._components.remove(component_id)
    def connect_components(self, producer_id, producer_outport, consumer_id, consumer_inport):
        self.check_component_availability(producer_id)
        self.check_component_availability(consumer_id)
        self.check_outport_availability(producer_id, producer_outport)
        self.check_inport_availability(consumer_id, consumer_inport)
        command = "{}.{} -> {}.{}".format(producer_id, producer_outport, consumer_id, consumer_inport)
        self._parse(command)

    def disconnect_components(self, producer_id, producer_outport, consumer_id, consumer_inport):
        self.check_component_availability(producer_id)
        self.check_component_availability(consumer_id)
        self.check_outport_availability(producer_id, producer_outport)
        self.check_inport_availability(consumer_id, consumer_inport)
        command = "{}.{} -X- {}.{}".format(producer_id, producer_outport, consumer_id, consumer_inport)
        self._parse(command)

    def execute_action(self, component_id: str, action: str):
        self.check_action_availability(component_id, action)
        command = "{}.{}".format(component_id, action)
        self._parse(command)

    def record_signal(self, producer_id, producer_outport, recorder_id, recording_method):
        self.check_component_availability(producer_id)
        self.check_outport_availability(producer_id, producer_outport)
        command = "record {}.{} in {} as {}".format(producer_id, producer_outport, recorder_id, recording_method)
        self._parse(command)

    def set_property(self, component_id, property_name, value):
        self.check_component_availability(component_id)
        self.check_property_availability(component_id, property_name)
        self.check_enum_property_validity(component_id, property_name, value)
        command = "{}.{} = {}".format(component_id, property_name, RTMapsAbstraction.format_value(value))
        self._parse(command)
    
    def set_input_property(self, component_id, input_name, property_name, value):
        self.check_component_availability(component_id)
        self.check_inport_availability(component_id, input_name)
        self.check_input_property_availability(property_name)
        command = "{}.{}.{} = {}".format(component_id, input_name, property_name, RTMapsAbstraction.format_value(value))
        self._parse(command)
    
    def set_output_property(self, component_id, output_name, property_name, value):
        self.check_component_availability(component_id)
        self.check_outport_availability(component_id, output_name)
        self.check_output_property_availability(property_name)
        command = "{}.{}.{} = {}".format(component_id, output_name, property_name, RTMapsAbstraction.format_value(value))
        self._parse(command)

    def print_rtm_script(self):
        for line in self._command_log:
            print(line)
    def write_rtm_script(self, path, overwrite=True):
        if not overwrite and os.path.isfile(path):
            raise RTMapsException("File {} already exists".format(path))
        with open(path, 'w') as file:
            for line in self._command_log:
                print(line, file=file)
    
    def export_rtd(self, file_path: str, overwrite: bool):
        command = "exportdiagramas <<{}>>".format(file_path)
        if overwrite:
            command += " overwrite"
        self._parse(command, add_to_command_log=False)

    def check_action_availability(self, component_id, action):
        if self._enable_checks:
            available_actions = self.get_action_names_for_component(component_id)
            action_name = "{}.{}".format(component_id, action)
            if action_name not in available_actions:
                raise RTMapsException("{} is not a valid action. Valid actions are: {}".format(action_name, available_actions))

    def check_outport_availability(self, component_id, outport):
        if self._enable_checks:
            available_outports = self.get_output_names_for_component(component_id)
            outport_name = "{}.{}".format(component_id, outport)
            if outport_name not in available_outports:
                raise RTMapsException("{} is not a valid outport. Valid outports are: {}".format(outport_name, available_outports))

    def check_inport_availability(self, component_id, inport):
        if self._enable_checks:
            available_inports = self.get_input_names_for_component(component_id)
            inport_name = "{}.{}".format(component_id, inport)
            if inport_name not in available_inports:
                raise RTMapsException("{} is not a valid inport. Valid inports are: {}".format(inport_name, available_inports))
    
    def check_property_availability(self, component_id, property_name):
        if self._enable_checks:    
            available_properties = self.get_property_names_for_component(component_id)
            property_name = "{}.{}".format(component_id, property_name)
            if property_name not in available_properties:
                raise RTMapsException("{} is not a valid property. Valid properties are: {}".format(property_name, available_properties))

    def check_input_property_availability(self, property_name):
        if self._enable_checks:    
            if property_name not in valid_input_properties:
                raise RTMapsException("{} is not a valid input property. Valid properties are: {}".format(property_name, valid_input_properties))
    
    def check_output_property_availability(self, property_name):
        if self._enable_checks:    
            if property_name not in valid_output_properties:
                raise RTMapsException("{} is not a valid output property. Valid properties are: {}".format(property_name, valid_output_properties))

    def check_component_availability(self, component_id):
        if self._enable_checks:    
            if component_id not in self._components:
                raise RTMapsException("{} is not a valid component id".format(component_id))

    def is_enum_property(self, component_id, property_name):
        enum_string = super(RTMapsAbstraction, self).get_enum_property("{}.{}".format(component_id, property_name))
        return "|" in enum_string

    def get_valid_enum_properties(self, component_id, property_name):
        enum_string = super(RTMapsAbstraction, self).get_enum_property("{}.{}".format(component_id, property_name))
        return enum_string.split("|")[2:]

    def check_enum_property_validity(self, component_id, property_name, value):
        if self.is_enum_property(component_id, property_name):
            valid_enum_values = self.get_valid_enum_properties(component_id, property_name)
            if type(value) is str:
                if value not in valid_enum_values:
                    raise RTMapsException("{} is not a valid enum value for property {}. Valid vales are {}".format(value, property_name, valid_enum_values))
            elif type(value) is int:
                if value < 0 or value >= len(valid_enum_values):
                    raise RTMapsException("{} is out of range for enum property {}. It must be [{},{})".format(value, property_name, 0, len(valid_enum_values)))
            else:
                raise RTMapsException("Type {} is not allowed for enum properties".format(type(value)))

    def get_integer_property(self, component_id, property_name):
        self.check_component_availability(component_id)
        self.check_property_availability(component_id, property_name)
        return super(RTMapsAbstraction, self).get_integer_property("{}.{}".format(component_id, property_name))
    
    def get_float_property(self, component_id, property_name):
        self.check_component_availability(component_id)
        self.check_property_availability(component_id, property_name)
        return super(RTMapsAbstraction, self).get_float_property("{}.{}".format(component_id, property_name))

    def get_string_property(self, component_id, property_name):
        self.check_component_availability(component_id)
        self.check_property_availability(component_id, property_name)
        return super(RTMapsAbstraction, self).get_string_property("{}.{}".format(component_id, property_name))

    def read_int32(self, component_id, output_name, wait_for_data):
        self.check_component_availability(component_id)
        self.check_outport_availability(component_id, output_name)
        return super(RTMapsAbstraction, self).read_int32("{}.{}".format(component_id, output_name), wait_for_data)

    def read_int32_timeout(self, component_id, output_name, timeout):
        self.check_component_availability(component_id)
        #self.check_outport_availability(component_id, output_name)
        return super(RTMapsAbstraction, self).read_int32_timeout(f"{component_id}.{output_name}", timeout)

    def read_int64_timeout(self, component_id, output_name, timeout):
        self.check_component_availability(component_id)
        #self.check_outport_availability(component_id, output_name)
        return super(RTMapsAbstraction, self).read_int64_timeout(f"{component_id}.{output_name}", timeout)

    def read_float64_vector(self, component_id, output_name, vector_size, wait4data):
        self.check_component_availability(component_id)
        self.check_outport_availability(component_id, output_name)
        return super(RTMapsAbstraction, self).read_float64_vector(f"{component_id}.{output_name}", vector_size, wait4data)
    
    def read_float64_vector_timeout_meta(self, component_id, output_name, vector_size, timeout):
        self.check_component_availability(component_id)
        self.check_outport_availability(component_id, output_name)
        return super(RTMapsAbstraction, self).read_float64_vector_timeout_meta(f"{component_id}.{output_name}", vector_size, timeout)

    def send_int32(self, component_id, input_name, value):
        self.check_component_availability(component_id)
        self.check_inport_availability(component_id, input_name)
        return super(RTMapsAbstraction, self).send_int32("{}.{}".format(component_id, input_name), value)

    def send_int32_ts(self, component_id, input_name, value, timestamp):
        self.check_component_availability(component_id)
        #self.check_inport_availability(component_id, input_name)
        return super(RTMapsAbstraction, self).send_int32_ts("{}.{}".format(component_id, input_name), value, timestamp)

    def send_int64_ts(self, component_id, input_name, value, timestamp):
        self.check_component_availability(component_id)
        #self.check_inport_availability(component_id, input_name)
        return super(RTMapsAbstraction, self).send_int64_ts("{}.{}".format(component_id, input_name), value, timestamp)

    def load_diagram(self, diagram_path, reset=True):
        path = Path(diagram_path)
        if not path.is_file():
            raise RTMapsException("{} is not a file".format(diagram_path))
        if path.suffix.lower() == ".rtd":
            self._load_rtd(diagram_path)
        elif path.suffix.lower() == ".rtm":
            self._load_rtm(diagram_path, reset=reset)
        else:
            raise RTMapsException("{} is not a valid diagram file".format(diagram_path))

    def _load_rtm(self, diagram_path, reset=True):
        if reset: self.reset()
        with open(diagram_path) as file:
            command = "loaddiagram <<{}>>".format(diagram_path)
            self._parse(command)
            for line in file:
                line_splitted = line.strip().split()
                # Check if line contains a component being added
                if not any(char in line for char in invalid_name_characters) and len(line_splitted) == 2:
                    self._components.add(line_splitted[1])

    def _load_rtd(self, file_path):
        self.reset()
        namespaces = {"int":"http://schemas.intempora.com/RTMaps/2011/RTMapsFiles"}
        root = et.parse(file_path)
        command = "loaddiagram <<{}>>".format(file_path)
        self._parse(command)
        for component_nodes in root.findall('int:Component', namespaces=namespaces):
            self._components.add(component_nodes.attrib["InstanceName"])
    
    def reset(self):
        self._components.clear()
        super(RTMapsAbstraction, self).reset()

    def register_std_report_reader(self):
        self.register_report_reader(stdReportReader)        

    @staticmethod
    def format_value(v):
        if type(v) is bool:
            return str(v).lower()
        elif type(v) is int or type(v) is float:
            return str(v)
        else:
            return "<<{}>>".format(str(v))

            
def stdReportReader(dummy, level, message):
    message=message.decode('utf-8')
    print("[RTMaps] {}".format(message))

