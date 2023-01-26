import os
import io
import sys
import argparse
import json
import re
from pathlib import Path
from typing import Text
from absl import logging

class LoadProBuf:

    def __init__(self,
                 pb_file: Text,
                 plc_file: Text) -> None:
        """
        Creates a ProBufFormat2LefDef object.
        """
        self.pb_file = pb_file
        self.plc_file = plc_file

        # All modules look-up table
        self.modules = []
        self.modules_w_pins = []

        # modules to index look-up table
        self.indices_to_mod_name = {}
        self.mod_name_to_indices = {}

        # indices storage
        self.port_indices = []
        self.hard_macro_indices = []
        self.hard_macro_pin_indices = []
        self.soft_macro_indices = []
        self.soft_macro_pin_indices = []
        self.std_cell_indices = []

        # macro to pins look-up table: [MACRO_NAME] => [PIN_NAME]
        self.hard_macros_to_inpins = {}
        self.soft_macros_to_inpins = {}

        # Placed macro
        self.placed_macro = []

        self.read_protobuf()
        self.load_placement()

    def read_plc(self):
        """
        Plc file Parser
        """
        # meta information
        _columns = 0
        _rows = 0
        _width = 0.0
        _height = 0.0
        _area = 0.0
        _block = None
        _routes_per_micron_hor = 0.0
        _routes_per_micron_ver = 0.0
        _routes_used_by_macros_hor = 0.0
        _routes_used_by_macros_ver = 0.0
        _smoothing_factor = 0
        _overlap_threshold = 0.0

        # node information
        _hard_macros_cnt = 0
        _hard_macro_pins_cnt = 0
        _macros_cnt = 0
        _macro_pin_cnt = 0
        _ports_cnt = 0
        _soft_macros_cnt = 0
        _soft_macro_pins_cnt = 0
        _stdcells_cnt = 0

        # node placement
        _node_plc = {}

        for _, line in enumerate(open(self.plc_file, 'r')):
            line_item = re.findall(r'[0-9A-Za-z\.\-]+', line)

            # skip empty lines
            if len(line_item) == 0:
                continue

            if 'Columns' in line_item and 'Rows' in line_item:
                # Columns and Rows should be defined on the same one-line
                _columns = int(line_item[1])
                _rows = int(line_item[3])
            elif "Width" in line_item and "Height" in line_item:
                # Width and Height should be defined on the same one-line
                _width = float(line_item[1])
                _height = float(line_item[3])
            elif all(it in line_item for it in ['Area', 'stdcell', 'macros']):
                # Total core area of modules
                _area = float(line_item[3])
            elif "Area" in line_item:
                # Total core area of modules
                _area = float(line_item[1])
            elif "Block" in line_item:
                # The block name of the testcase
                _block = str(line_item[1])
            elif all(it in line_item for it in
                     ['Routes', 'per', 'micron', 'hor', 'ver']):
                # For routing congestion computation
                _routes_per_micron_hor = float(line_item[4])
                _routes_per_micron_ver = float(line_item[6])
            elif all(it in line_item for it in
                     ['Routes', 'used', 'by', 'macros', 'hor', 'ver']):
                # For MACRO congestion computation
                _routes_used_by_macros_hor = float(line_item[5])
                _routes_used_by_macros_ver = float(line_item[7])
            elif all(it in line_item for it in ['Smoothing', 'factor']):
                # smoothing factor for routing congestion
                _smoothing_factor = int(line_item[2])
            elif all(it in line_item for it in ['Overlap', 'threshold']):
                # overlap
                _overlap_threshold = float(line_item[2])
            elif all(it in line_item for it in ['HARD', 'MACROs'])\
                    and len(line_item) == 3:
                _hard_macros_cnt = int(line_item[2])
            elif all(it in line_item for it in ['HARD', 'MACRO', 'PINs'])\
                    and len(line_item) == 4:
                _hard_macro_pins_cnt = int(line_item[3])
            elif all(it in line_item for it in ['PORTs'])\
                    and len(line_item) == 2:
                _ports_cnt = int(line_item[1])
            elif all(it in line_item for it in ['SOFT', 'MACROs'])\
                    and len(line_item) == 3:
                _soft_macros_cnt = int(line_item[2])
            elif all(it in line_item for it in ['SOFT', 'MACRO', 'PINs'])\
                    and len(line_item) == 4:
                _soft_macro_pins_cnt = int(line_item[3])
            elif all(it in line_item for it in ['STDCELLs'])\
                    and len(line_item) == 2:
                _stdcells_cnt = int(line_item[1])
            elif all(it in line_item for it in ['MACROs'])\
                    and len(line_item) == 2:
                _macros_cnt = int(line_item[1])
            elif all(re.match(r'[0-9FNEWS\.\-]+', it) for it in line_item)\
                    and len(line_item) == 5:
                # [node_index] [x] [y] [orientation] [fixed]
                _node_plc[int(line_item[0])] = line_item[1:]

        # return as dictionary
        info_dict = {"columns": _columns,
                     "rows": _rows,
                     "width": _width,
                     "height": _height,
                     "area": _area,
                     "block": _block,
                     "routes_per_micron_hor": _routes_per_micron_hor,
                     "routes_per_micron_ver": _routes_per_micron_ver,
                     "routes_used_by_macros_hor": _routes_used_by_macros_hor,
                     "routes_used_by_macros_ver": _routes_used_by_macros_ver,
                     "smoothing_factor": _smoothing_factor,
                     "overlap_threshold": _overlap_threshold,
                     "hard_macros_cnt": _hard_macros_cnt,
                     "hard_macro_pins_cnt": _hard_macro_pins_cnt,
                     "macros_cnt": _macros_cnt,
                     "macro_pin_cnt": _macro_pin_cnt,
                     "ports_cnt": _ports_cnt,
                     "soft_macros_cnt": _soft_macros_cnt,
                     "soft_macro_pins_cnt": _soft_macro_pins_cnt,
                     "stdcells_cnt": _stdcells_cnt,
                     "node_plc": _node_plc
                     }

        return info_dict

    def get_node_type(self, node_idx: int) -> str:
        """
        Return node type
        """
        try:
            return self.modules_w_pins[node_idx].get_type()
        except IndexError:
            # NOTE: Google's API return NONE if out of range
            print("[WARNING INDEX OUT OF RANGE] Can not process index at {}".format(node_idx))
            return None

    def update_macro_orientation(self, node_idx, orientation):
        """ 
        Update macro orientation if node is 'MACRO'
        """
        mod = None

        try:
            mod = self.modules_w_pins[node_idx]
            assert mod.get_type() in ['MACRO']
        except AssertionError:
            print("[ERROR MACRO ORIENTATION] Found {}. Only 'MACRO'".format(mod.get_type())
                    +" are considered to be ORIENTED")
            exit(1)
        except Exception:
            print("[ERROR MACRO ORIENTATION] Could not find module by node index")
            exit(1)
        
        mod.set_orientation(orientation)

        macro = self.modules_w_pins[node_idx]
        macro_name = macro.get_name()
        hard_macro_pins = self.hard_macros_to_inpins[macro_name]
        
        orientation = macro.get_orientation()

        # update all pin offset
        for pin_name in hard_macro_pins:
            pin = self.modules_w_pins[self.mod_name_to_indices[pin_name]]

            x_offset, y_offset = pin.get_offset()
            x_offset_org = x_offset
            if orientation == "N":
                pass
            elif orientation == "FN":
                x_offset = -x_offset
                pin.set_offset(x_offset, y_offset)
            elif orientation == "S":
                x_offset = -x_offset
                y_offset = -y_offset
                pin.set_offset(x_offset, y_offset)
            elif orientation == "FS":
                y_offset = -y_offset
                pin.set_offset(x_offset, y_offset)
            elif orientation == "E":
                x_offset = y_offset
                y_offset = -x_offset_org
                pin.set_offset(x_offset, y_offset)
            elif orientation == "FE":
                x_offset = -y_offset
                y_offset = -x_offset_org
                pin.set_offset(x_offset, y_offset)
            elif orientation == "W":
                x_offset = -y_offset
                y_offset = x_offset_org
                pin.set_offset(x_offset, y_offset)
            elif orientation == "FW":
                x_offset = y_offset
                y_offset = x_offset_org
                pin.set_offset(x_offset, y_offset)

    def is_node_soft_macro(self, node_idx) -> bool:
        """
        Return if node is a soft macro
        """
        try:
            return node_idx in self.soft_macro_indices
        except IndexError:
            print("[ERROR INDEX OUT OF RANGE] Can not process index at {}".format(node_idx))
            exit(1)

    def __update_connection(self):
        """
        Update connection degree for each macro pin
        """
        for macro_idx in (self.hard_macro_indices + self.soft_macro_indices):
            macro = self.modules_w_pins[macro_idx]
            macro_name = macro.get_name()

            # Hard macro
            if not self.is_node_soft_macro(macro_idx):
                if macro_name in self.hard_macros_to_inpins.keys():
                    pin_names = self.hard_macros_to_inpins[macro_name]
                else:
                    print("[ERROR UPDATE CONNECTION] MACRO pins not found")
                    continue

                # also update pin offset based on macro orientation
                orientation = macro.get_orientation()
                self.update_macro_orientation(macro_idx, orientation)

            # Soft macro
            elif self.is_node_soft_macro(macro_idx):
                if macro_name in self.soft_macros_to_inpins.keys():
                    pin_names = self.soft_macros_to_inpins[macro_name]
                else:
                    print("[ERROR UPDATE CONNECTION] macro pins not found")
                    continue

            for pin_name in pin_names:
                pin = self.modules_w_pins[self.mod_name_to_indices[pin_name]]
                inputs = pin.get_sink()

                if inputs:
                    for k in inputs.keys():
                        if self.get_node_type(macro_idx) == "MACRO":
                            weight = pin.get_weight()
                            macro.add_connections(inputs[k], weight)

    def __update_init_placed_node(self):
        """
        Place all hard macros on node mask initially
        """
        for macro_idx in (self.hard_macro_indices + self.soft_macro_indices):
            self.placed_macro.append(macro_idx)

    def __peek(self, f: io.TextIOWrapper):
        """
        Return String next line by peeking into the next line without moving file descriptor
        """
        pos = f.tell()
        t_line = f.readline()
        f.seek(pos)
        return t_line

    def read_protobuf(self):
        """
        Protobuf Netlist Parser
        """
        print("#[INFO] Reading from " + self.pb_file)
        with open(self.pb_file) as fp:
            line = fp.readline()
            node_cnt = 0

            while line:
                line_item = re.findall(r'\w+', line)

                # skip empty lines
                if len(line_item) == 0:
                    # advance ptr
                    line = fp.readline()
                    continue

                # skip comments
                if re.search(r"\S", line)[0] == '#':
                    # advance ptr
                    line = fp.readline()
                    continue

                # node found
                if line_item[0] == 'node':
                    node_name = ''
                    input_list = []

                    # advance ptr
                    line = fp.readline()
                    line_item = re.findall(r'\w+[^\:\n\\{\}\s"]*', line)
                    # retrieve node name
                    if line_item[0] == 'name':
                        node_name = line_item[1]
                        # skip metadata header
                        if node_name == "__metadata__":
                            pass
                        else:
                            node_cnt += 1
                    else:
                        node_name = 'N/A name'

                    # advance ptr
                    line = fp.readline()
                    line_item = re.findall(r'\w+[^\:\n\\{\}\s"]*', line)
                    # retrieve node input
                    if line_item[0] == 'input':
                        input_list.append(line_item[1])

                        while re.findall(r'\w+[^\:\n\\{\}\s"]*', self.__peek(fp))[0] == 'input':
                            line = fp.readline()
                            line_item = re.findall(
                                r'\w+[^\:\n\\{\}\s"]*', line)
                            input_list.append(line_item[1])

                        line = fp.readline()
                        line_item = re.findall(r'\w+[^\:\n\\{\}\s"]*', line)
                    else:
                        input_list = None

                    # advance, expect multiple attributes
                    attr_dict = {}
                    while len(line_item) != 0 and line_item[0] == 'attr':

                        # advance, expect key
                        line = fp.readline()
                        line_item = re.findall(r'\w+', line)
                        key = line_item[1]

                        if key == "macro_name":
                            # advance, expect value
                            line = fp.readline()
                            line_item = re.findall(r'\w+', line)

                            # advance, expect value item
                            line = fp.readline()
                            line_item = re.findall(
                                r'\w+[^\:\n\\{\}\s"]*', line)

                            attr_dict[key] = line_item

                            line = fp.readline()
                            line = fp.readline()
                            line = fp.readline()

                            line_item = re.findall(r'\w+', line)
                        else:
                            # advance, expect value
                            line = fp.readline()
                            line_item = re.findall(r'\w+', line)

                            # advance, expect value item
                            line = fp.readline()
                            line_item = re.findall(
                                r'\-*\w+\.*\/{0,1}\w*[\w+\/{0,1}\w*]*', line)

                            attr_dict[key] = line_item

                            line = fp.readline()
                            line = fp.readline()
                            line = fp.readline()

                            line_item = re.findall(r'\w+', line)

                    if node_name == "__metadata__":
                        # skipping metadata header
                        logging.info(
                            '[INFO NETLIST PARSER] skipping invalid net input')

                    elif attr_dict['type'][1] == 'macro':
                        # soft macro
                        # check if all required information is obtained
                        try:
                            assert 'x' in attr_dict.keys()
                        except AssertionError:
                            logging.warning(
                                '[ERROR NETLIST PARSER] x is not defined')

                        try:
                            assert 'y' in attr_dict.keys()
                        except AssertionError:
                            logging.warning(
                                '[ERROR NETLIST PARSER] y is not defined')

                        soft_macro = self.SoftMacro(name=node_name, width=attr_dict['width'][1],
                                                    height=attr_dict['height'][1],
                                                    x=attr_dict['x'][1], y=attr_dict['y'][1])
                        self.modules_w_pins.append(soft_macro)
                        self.modules.append(soft_macro)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt-1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt-1] = node_name
                        # store current node indx
                        self.soft_macro_indices.append(node_cnt-1)

                    elif attr_dict['type'][1] == 'macro_pin':
                        # [MACRO_NAME]/[PIN_NAME]
                        soft_macro_name = node_name.rsplit('/', 1)[0]
                        # soft macro pin
                        soft_macro_pin = self.SoftMacroPin(name=node_name, ref_id=None,
                                                           x=attr_dict['x'][1],
                                                           y=attr_dict['y'][1],
                                                           macro_name=attr_dict['macro_name'][1])

                        if 'weight' in attr_dict.keys():
                            soft_macro_pin.set_weight(
                                float(attr_dict['weight'][1]))

                        # if pin has net info
                        if input_list:
                            soft_macro_pin.add_sinks(input_list)

                        self.modules_w_pins.append(soft_macro_pin)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt-1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt-1] = node_name
                        # store current node indx
                        self.soft_macro_pin_indices.append(node_cnt-1)

                        if soft_macro_name in self.soft_macros_to_inpins.keys():
                            self.soft_macros_to_inpins[soft_macro_name]\
                                .append(soft_macro_pin.get_name())
                        else:
                            self.soft_macros_to_inpins[soft_macro_name]\
                                = [soft_macro_pin.get_name()]

                    elif attr_dict['type'][1] == 'STDCELL':
                        # check if all required information is obtained
                        try:
                            assert 'x' in attr_dict.keys()
                        except AssertionError:
                            logging.warning(
                                '[ERROR NETLIST PARSER] x is not defined')

                        try:
                            assert 'y' in attr_dict.keys()
                        except AssertionError:
                            logging.warning(
                                '[ERROR NETLIST PARSER] y is not defined')

                        std_cell = self.StdCell(name=node_name, width=attr_dict['width'][1],
                                                height=attr_dict['height'][1],
                                                x=attr_dict['x'][1], y=attr_dict['y'][1])

                        self.modules_w_pins.append(std_cell)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt-1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt-1] = node_name
                        # store current node indx
                        self.std_cell_indices.append(node_cnt - 1)
                    elif attr_dict['type'][1] == 'MACRO':
                        # hard macro
                        hard_macro = self.HardMacro(name=node_name,
                                                    width=attr_dict['width'][1],
                                                    height=attr_dict['height'][1],
                                                    x=attr_dict['x'][1],
                                                    y=attr_dict['y'][1],
                                                    orientation=attr_dict['orientation'][1])

                        self.modules_w_pins.append(hard_macro)
                        self.modules.append(hard_macro)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt-1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt-1] = node_name
                        # store current node indx
                        self.hard_macro_indices.append(node_cnt-1)

                    elif attr_dict['type'][1] == 'MACRO_PIN':
                        # [MACRO_NAME]/[PIN_NAME]
                        hard_macro_name = node_name.rsplit('/', 1)[0]
                        # hard macro pin
                        hard_macro_pin = self.HardMacroPin(name=node_name, ref_id=None,
                                                           x=attr_dict['x'][1],
                                                           y=attr_dict['y'][1],
                                                           x_offset=attr_dict['x_offset'][1],
                                                           y_offset=attr_dict['y_offset'][1],
                                                           macro_name=attr_dict['macro_name'][1])

                        # if net weight is defined, set weight
                        if 'weight' in attr_dict.keys():
                            hard_macro_pin.set_weight(
                                float(attr_dict['weight'][1]))

                        # if pin has net info
                        if input_list:
                            hard_macro_pin.add_sinks(input_list)

                        self.modules_w_pins.append(hard_macro_pin)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt-1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt-1] = node_name
                        # store current node indx
                        self.hard_macro_pin_indices.append(node_cnt-1)

                        # add to dict
                        if hard_macro_name in self.hard_macros_to_inpins.keys():
                            self.hard_macros_to_inpins[hard_macro_name]\
                                .append(hard_macro_pin.get_name())
                        else:
                            self.hard_macros_to_inpins[hard_macro_name]\
                                = [hard_macro_pin.get_name()]

                    elif attr_dict['type'][1] == 'PORT':
                        # port
                        port = self.Port(name=node_name,
                                         x=attr_dict['x'][1],
                                         y=attr_dict['y'][1],
                                         side=attr_dict['side'][1])

                        # if pin has net info
                        if input_list:
                            port.add_sinks(input_list)
                            # ports does not have pins so update connection immediately
                            port.add_connections(input_list)

                        self.modules_w_pins.append(port)
                        self.modules.append(port)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt-1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt-1] = node_name
                        # store current node indx
                        self.port_indices.append(node_cnt-1)

        # 1. mapping connection degree to each macros
        # 2. update offset based on Hard macro orientation
        self.__update_connection()

        # all hard macros are placed on canvas initially
        self.__update_init_placed_node()

    class Port:
        def __init__(self, name, x=0.0, y=0.0, side="BOTTOM"):
            self.name = name
            self.x = float(x)
            self.y = float(y)
            self.side = side  # "BOTTOM", "TOP", "LEFT", "RIGHT"
            self.sink = {}  # standard cells, macro pins, ports driven by this cell
            self.connection = {}  # [module_name] => edge degree
            self.fix_flag = True
            self.orientation = None

        def get_name(self):
            return self.name

        def get_orientation(self):
            return self.orientation

        def get_height(self):
            return 0

        def get_width(self):
            return 0

        def add_connection(self, module_name):
            # NOTE: assume PORT names does not contain slash
            ifPORT = False
            module_name_splited = module_name.rsplit('/', 1)
            if len(module_name_splited) == 1:
                ifPORT = not ifPORT

            if ifPORT:
                # adding PORT
                self.connection[module_name] = 1
            else:
                # adding soft/hard macros
                if module_name_splited[0] in self.connection.keys():
                    self.connection[module_name_splited[0]] += 1
                else:
                    self.connection[module_name_splited[0]] = 1

        def add_connections(self, module_names):
            # NOTE: assume PORT names does not contain slash
            for module_name in module_names:
                self.add_connection(module_name)

        def set_pos(self, x, y):
            self.x = x
            self.y = y

        def get_pos(self):
            return self.x, self.y

        def add_sink(self, sink_name):
            # NOTE: assume PORT names does not contain slash
            ifPORT = False
            sink_name_splited = sink_name.rsplit('/', 1)
            if len(sink_name_splited) == 1:
                ifPORT = not (ifPORT)

            if ifPORT:
                # adding PORT
                self.sink[sink_name] = [sink_name]
            else:
                # adding soft/hard macros
                if sink_name_splited[0] in self.sink.keys():
                    self.sink[sink_name_splited[0]].append(sink_name)
                else:
                    self.sink[sink_name_splited[0]] = [sink_name]

        def add_sinks(self, sink_names):
            # NOTE: assume PORT names does not contain slash
            for sink_name in sink_names:
                self.add_sink(sink_name)

        def get_sink(self):
            return self.sink

        def get_type(self):
            return "PORT"

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

    class StdCell:
        def __init__(self, name, width, height, x=0.0, y=0.0):
            self.name = name
            self.width = float(width)
            self.height = float(height)
            self.x = float(x)
            self.y = float(y)
            self.connection = {}  # [module_name] => edge degree
            self.orientation = None
            self.fix_flag = False

        def get_name(self):
            return self.name

        def set_pos(self, x, y):
            self.x = x
            self.y = y

        def get_pos(self):
            return self.x, self.y

        def get_type(self):
            return "MACRO"

        def set_orientation(self, orientation):
            self.orientation = orientation

        def get_orientation(self):
            return self.orientation

        def get_height(self):
            return self.height

        def get_width(self):
            return self.width

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

    class SoftMacro:
        def __init__(self, name, width, height, x=0.0, y=0.0):
            self.name = name
            self.width = float(width)
            self.height = float(height)
            self.x = float(x)
            self.y = float(y)
            self.connection = {}  # [module_name] => edge degree
            self.orientation = None
            self.fix_flag = False

        def get_name(self):
            return self.name

        def add_connection(self, module_name, weight):
            # NOTE: assume PORT names does not contain slash
            ifPORT = False
            module_name_splited = module_name.rsplit('/', 1)
            if len(module_name_splited) == 1:
                ifPORT = not (ifPORT)

            if ifPORT:
                # adding PORT
                self.connection[module_name] = 1 * weight
            else:
                # adding soft/hard macros
                if module_name_splited[0] in self.connection.keys():
                    self.connection[module_name_splited[0]] += 1 * weight
                else:
                    self.connection[module_name_splited[0]] = 1 * weight

        def add_connections(self, module_names, weight):
            # NOTE: assume PORT names does not contain slash
            # consider weight on soft macro pins
            for module_name in module_names:
                self.add_connection(module_name, weight)

        def set_pos(self, x, y):
            self.x = x
            self.y = y

        def get_pos(self):
            return self.x, self.y

        def get_type(self):
            return "MACRO"

        def set_orientation(self, orientation):
            self.orientation = orientation

        def get_orientation(self):
            return self.orientation

        def get_height(self):
            return self.height

        def get_width(self):
            return self.width

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

    class SoftMacroPin:
        def __init__(self, name, ref_id,
                     x=0.0, y=0.0,
                     macro_name="", weight=1.0):
            self.name = name
            self.ref_id = ref_id
            self.x = float(x)
            self.y = float(y)
            self.x_offset = 0.0  # not used
            self.y_offset = 0.0  # not used
            self.macro_name = macro_name
            self.weight = weight
            self.sink = {}

        def set_weight(self, weight):
            self.weight = weight

        def get_weight(self):
            return self.weight

        def get_name(self):
            return self.name

        def set_pos(self, x, y):
            self.x = x
            self.y = y

        def get_pos(self):
            return self.x, self.y

        def get_offset(self):
            return self.x_offset, self.y_offset

        def add_sink(self, sink_name):
            # NOTE: assume PORT names does not contain slash
            ifPORT = False
            sink_name_splited = sink_name.rsplit('/', 1)
            if len(sink_name_splited) == 1:
                ifPORT = not (ifPORT)

            if ifPORT:
                # adding PORT
                self.sink[sink_name] = [sink_name]
            else:
                # adding soft/hard macros
                if sink_name_splited[0] in self.sink.keys():
                    self.sink[sink_name_splited[0]].append(sink_name)
                else:
                    self.sink[sink_name_splited[0]] = [sink_name]

        def add_sinks(self, sink_names):
            # NOTE: assume PORT names does not contain slash
            for sink_name in sink_names:
                self.add_sink(sink_name)

        def get_sink(self):
            return self.sink

        def get_weight(self):
            return self.weight

        def get_type(self):
            return "MACRO_PIN"

    class HardMacro:
        def __init__(self, name, width, height,
                     x=0.0, y=0.0, orientation="N"):
            self.name = name
            self.width = float(width)
            self.height = float(height)
            self.x = float(x)
            self.y = float(y)
            self.orientation = orientation
            self.connection = {}  # [module_name] => edge degree
            self.fix_flag = False

        def get_name(self):
            return self.name

        def add_connection(self, module_name, weight):
            # NOTE: assume PORT names does not contain slash
            ifPORT = False
            module_name_splited = module_name.rsplit('/', 1)
            if len(module_name_splited) == 1:
                ifPORT = not (ifPORT)

            if ifPORT:
                # adding PORT
                self.connection[module_name] = 1 * weight
            else:
                # adding soft/hard macros
                if module_name_splited[0] in self.connection.keys():
                    self.connection[module_name_splited[0]] += 1 * weight
                else:
                    self.connection[module_name_splited[0]] = 1 * weight

        def add_connections(self, module_names, weight):
            # NOTE: assume PORT names does not contain slash
            # consider weight on soft macro pins
            for module_name in module_names:
                self.add_connection(module_name, weight)

        def set_pos(self, x, y):
            self.x = x
            self.y = y

        def get_pos(self):
            return self.x, self.y

        def set_orientation(self, orientation):
            self.orientation = orientation

        def get_orientation(self):
            return self.orientation

        def get_type(self):
            return "MACRO"

        def get_height(self):
            return self.height

        def get_width(self):
            return self.width

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

    class HardMacroPin:
        def __init__(self, name, ref_id,
                     x=0.0, y=0.0,
                     x_offset=0.0, y_offset=0.0,
                     macro_name="", weight=1.0):
            self.name = name
            self.ref_id = ref_id
            self.x = float(x)
            self.y = float(y)
            self.x_offset = float(x_offset)
            self.y_offset = float(y_offset)
            self.macro_name = macro_name
            self.weight = weight
            self.sink = {}

        def set_weight(self, weight):
            self.weight = weight

        def get_weight(self):
            return self.weight

        def set_pos(self, x, y):
            self.x = x
            self.y = y

        def get_pos(self):
            return self.x, self.y

        def get_offset(self):
            return self.x_offset, self.y_offset

        def set_offset(self, x_offset, y_offset):
            self.x_offset = x_offset
            self.y_offset = y_offset

        def get_name(self):
            return self.name

        def add_sink(self, sink_name):
            # NOTE: assume PORT names does not contain slash
            ifPORT = False
            sink_name_splited = sink_name.rsplit('/', 1)
            if len(sink_name_splited) == 1:
                ifPORT = not (ifPORT)

            if ifPORT:
                # adding PORT
                self.sink[sink_name] = [sink_name]
            else:
                # adding soft/hard macros
                if sink_name_splited[0] in self.sink.keys():
                    self.sink[sink_name_splited[0]].append(sink_name)
                else:
                    self.sink[sink_name_splited[0]] = [sink_name]

        def add_sinks(self, sink_names):
            # NOTE: assume PORT names does not contain slash
            for sink_name in sink_names:
                self.add_sink(sink_name)

        def get_sink(self):
            return self.sink

        def get_type(self):
            return "MACRO_PIN"

    def load_placement(self):
        # if plc is an initial placement
        
        # extracted information from .plc file
        info_dict = self.read_plc()

        for mod_idx in info_dict['node_plc'].keys():
            mod_x = mod_y = mod_orient = mod_ifFixed = None
            try:
                mod_x = float(info_dict['node_plc'][mod_idx][0])
                mod_y = float(info_dict['node_plc'][mod_idx][1])
                mod_orient = info_dict['node_plc'][mod_idx][2]
                mod_ifFixed = int(info_dict['node_plc'][mod_idx][3])
                
            except Exception as e:
                print('[ERROR PLC PARSER] %s' % str(e))

            try:
                self.modules_w_pins[mod_idx].set_pos(mod_x, mod_y)
            
                if mod_orient and mod_orient != '-':
                    self.modules_w_pins[mod_idx].set_orientation(mod_orient)
                
                if mod_ifFixed == 0:
                    self.modules_w_pins[mod_idx].set_fix_flag(False)
                elif mod_ifFixed == 1:
                    self.modules_w_pins[mod_idx].set_fix_flag(True)
            except IndexError:
                try:
                    self.modules[mod_idx].set_pos(mod_x, mod_y)

                    if mod_orient and mod_orient != '-':
                        self.modules[mod_idx].set_orientation(mod_orient)
                    if mod_ifFixed == 0:
                        self.modules[mod_idx].set_fix_flag(False)
                    elif mod_ifFixed == 1:
                        self.modules[mod_idx].set_fix_flag(True)
                except IndexError as e:
                    print('[ERROR PC PARSER] %s' % str(e))


class ProBufFormat2LefDef(LoadProBuf):
    def __init__(self,
                 design: Text,
                 lef_list,
                 def_file: Text,
                 lib_list,
                 netlist: Text,
                 pb_file: Text,
                 plc_file: Text,
                 openroad_exe: Text) -> None:
        super().__init__(pb_file, plc_file)
        self.design = design
        self.lef_list = lef_list
        self.def_file = def_file
        self.lib_list = lib_list
        self.netlist = netlist
        self.openroad_exe = openroad_exe
    
    def convert(self):
        file_name = 'tmp_update_def.tcl'
        line = 'set top_design ' + self.design + '\n'
        line += 'set netlist ' + self.netlist + '\n'
        line += 'set def_file ' + self.def_file + '\n'

        line += 'set ALL_LEFS "' + '\n'
        for lef in self.lef_list:
            line += '    ' + lef + '\n'
        line += '"\n'

        line += 'set LIB_BC "' + '\n'
        for lib in self.lib_list:
            line += '    ' + lib + '\n'
        line += '"\n'

        # TODO: Set site name as param for __init__
        line += 'set site "unithd"' + '\n'

        line += 'foreach lef_file ${ALL_LEFS} {' + '\n'
        line += '    read_lef $lef_file' + '\n'
        line += '}' + '\n'

        line += 'foreach lib_file ${LIB_BC} {' + '\n'
        line += '    read_liberty $lib_file' + '\n'
        line += '}' + '\n'

        line += 'read_def ' + self.def_file + '\n'
        line += 'set plc_ports {}' + '\n'
        line += 'set plc_cells {}' + '\n'
        line += 'set plc_cells_pins {}' + '\n'

        # Here magic begins
        # for mod_idx in sorted(self.hard_macro_indices + self.soft_macro_indices + self.port_indices):
        for mod_idx in sorted(self.hard_macro_indices + self.soft_macro_indices + self.std_cell_indices):
            # [name] [x] [y] [orientation]
            mod = self.modules_w_pins[mod_idx]
            mod_name = mod.get_name()

            h = mod.get_height()
            w = mod.get_width()
            x, y = mod.get_pos()
            x = x - w / 2
            y = y - h / 2
            orient = mod.get_orientation()

            line += 'lappend plc_cells [dict create name "{}" x {:g} y {:g} orient "{}"]'.format(
                mod_name, x, y, orient) + '\n'

        # Here magic ends

        p = Path(self.def_file)
        new_def = str(p.parent / (p.stem + '.new.def'))

        line += 'source gen_def.tcl' + '\n'
        line += 'gen_updated_def ' + new_def + \
            ' $plc_ports $plc_cells $plc_cells_pins' + '\n'
        line += 'exit' + '\n'

        with open(file_name, 'w') as f:
            f.write(line)
            f.close()

        cmd = self.openroad_exe + ' ' + file_name
        os.system(cmd)

        cmd = "rm " + file_name
        os.system(cmd)


class LefDef2ProBufFormat:

    def __init__(self, design, lef_list, def_file, pb_file, plc_file, openroad_exe, net_size_threshold):

        self.design = design
        self.lef_list = lef_list
        self.def_file = def_file

        self.pb_file = pb_file
        self.plc_file = plc_file

        self.openroad_exe = openroad_exe
        self.net_size_threshold = net_size_threshold

    def convert(self):
        file_name = 'tmp_to_proto.tcl'
        line = ''
        line += 'set ALL_LEFS "' + '\n'
        for lef in self.lef_list:
            line += '    ' + lef + '\n'
        line += '"\n'

        line += 'set site "unithd"' + '\n'

        line += 'foreach lef_file ${ALL_LEFS} {' + '\n'
        line += '    read_lef $lef_file' + '\n'
        line += '}' + '\n'

        line += 'read_def ' + self.def_file + '\n'
        line += 'source gen_pb_or.tcl' + '\n'
        line += 'gen_pb_netlist ' + self.pb_file + '\n'
        line += 'source gen_plc.tcl' + '\n'
        line += 'gen_plc ' + self.plc_file + '\n'
        line += 'exit'

        with open(file_name, 'w') as f:
            f.write(line)
            f.close()

        cmd = self.openroad_exe + ' ' + file_name
        os.system(cmd)

        cmd = "rm " + file_name
        os.system(cmd)

class ProBufFormat2MacroCfg(LoadProBuf):
    
    def __init__(self,
                 design: Text,
                 lef_list,
                 def_file: Text,
                 lib_list,
                 netlist: Text,
                 pb_file: Text,
                 plc_file: Text,
                 macrocfg_file: Text,
                 openroad_exe: Text) -> None:
        super().__init__(pb_file, plc_file)
        self.design = design
        self.lef_list = lef_list
        self.def_file = def_file
        self.lib_list = lib_list
        self.netlist = netlist
        self.macrocfg_file = macrocfg_file
        self.openroad_exe = openroad_exe

    def convert(self):
        file_name = 'tmp_gen_macrocfg.tcl'
        line = 'set top_design ' + self.design + '\n'
        line += 'set netlist ' + self.netlist + '\n'
        line += 'set def_file ' + self.def_file + '\n'

        line += 'set ALL_LEFS "' + '\n'
        for lef in self.lef_list:
            line += '    ' + lef + '\n'
        line += '"\n'

        line += 'set LIB_BC "' + '\n'
        for lib in self.lib_list:
            line += '    ' + lib + '\n'
        line += '"\n'

        # TODO: Set site name as param for __init__
        line += 'set site "unithd"' + '\n'

        line += 'foreach lef_file ${ALL_LEFS} {' + '\n'
        line += '    read_lef $lef_file' + '\n'
        line += '}' + '\n'

        line += 'foreach lib_file ${LIB_BC} {' + '\n'
        line += '    read_liberty $lib_file' + '\n'
        line += '}' + '\n'

        line += 'read_def ' + self.def_file + '\n'
        line += 'set plc_cells {}' + '\n'

        for mod_idx in sorted(self.hard_macro_indices):
                # [name] [x] [y] [orientation]
                mod = self.modules_w_pins[mod_idx]
                mod_name = mod.get_name()

                h = mod.get_height()
                w = mod.get_width()
                x, y = mod.get_pos()
                x = x - w / 2
                y = y - h / 2
                orient = mod.get_orientation()

                line += 'lappend plc_cells [dict create name "{}" x {:g} y {:g} orient "{}"]'.format(
                mod_name, x, y, orient) + '\n'
        
        line += 'source gen_macrocfg.tcl' + '\n'
        line += 'gen_macrocfg ' + self.macrocfg_file + \
            ' $plc_cells' + '\n'
        line += 'exit' + '\n'

        with open(file_name, 'w') as f:
            f.write(line)
            f.close()

        cmd = self.openroad_exe + ' ' + file_name
        os.system(cmd)

        cmd = "rm " + file_name
        os.system(cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Protobuf to DEF convertor")
    parser.add_argument('config', type=str)

    args = vars(parser.parse_args())

    with open(args['config'], 'r') as f:
        data = json.load(f)

    convertor_types = ["p2d", "d2p", "p2m"]
    conv_t = data['CONVERTOR']

    if conv_t not in convertor_types:
        print("Unknown convertor: {}!".format(conv_t))
        exit(1)

    design = data['DESIGN']
    netlist = data['NETLIST']
    def_file = data['DEF']
    lef_list = data['LEFS']
    lib_list = data['LIBS']
    pb_file = data['PB_FILE']
    plc_file = data['PLC_FILE']
    openroad_exe = data['OPENROAD_EXE']

    if conv_t == "p2d":
        convertor = ProBufFormat2LefDef(
            design, lef_list, def_file, lib_list, netlist, pb_file, plc_file, openroad_exe)
        convertor.convert()
    elif conv_t == "d2p":
        net_size_threshold = 300

        convertor = LefDef2ProBufFormat(
            design, lef_list, def_file, pb_file, plc_file, openroad_exe, net_size_threshold)
        convertor.convert()
    elif conv_t == "p2m":
        macrocfg = data['MACRO_CFG']

        convertor = ProBufFormat2MacroCfg(
            design, lef_list, def_file, lib_list, netlist, pb_file, plc_file, macrocfg, openroad_exe)
        convertor.convert()
