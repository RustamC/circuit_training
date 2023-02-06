import math
import re
import sys
import io

from PyQt5.QtWidgets \
    import \
    QApplication, QWidget, \
    QDesktopWidget, QMessageBox, \
    QMainWindow, QAction, qApp, QFileDialog, QVBoxLayout

from matplotlib.backends.backend_qt5agg import (
    FigureCanvas, NavigationToolbar2QT as NavigatorToolbar)
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

class PData:

    def __init__(self):
        self.netlist_file = None
        self.place_file = None

        # net information
        self.net_cnt = 0

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

        # macro to pins look-up table: [MACRO_NAME] => [PIN_NAME]
        self.hard_macros_to_inpins = {}
        self.soft_macros_to_inpins = {}

        # Placed macro
        self.placed_macro = []

        self.info_dict = None

        # default canvas width/height based on cell area
        self.width = 0
        self.height = 0

        self.grid_col = 100
        self.grid_row = 100

    def read_protobuf(self):
        """
        private function: Protobuf Netlist Parser
        """
        with open(self.netlist_file) as fp:
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
                            line_item = re.findall(r'\w+[^\:\n\\{\}\s"]*', line)
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
                            line_item = re.findall(r'\w+[^\:\n\\{\}\s"]*', line)

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
                            line_item = re.findall(r'\-*\w+\.*\/{0,1}\w*[\w+\/{0,1}\w*]*', line)

                            attr_dict[key] = line_item

                            line = fp.readline()
                            line = fp.readline()
                            line = fp.readline()

                            line_item = re.findall(r'\w+', line)

                    if node_name == "__metadata__":
                        # skipping metadata header
                        pass
                    elif attr_dict['type'][1] == 'macro':
                        # soft macro
                        # check if all required information is obtained
                        try:
                            assert 'x' in attr_dict.keys()
                        except AssertionError:
                            QMessageBox.warning(self, "[ERROR NETLIST PARSER] x is not defined", QMessageBox.Ok)
                        try:
                            assert 'y' in attr_dict.keys()
                        except AssertionError:
                            QMessageBox.warning(self, "[ERROR NETLIST PARSER] y is not defined", QMessageBox.Ok)

                        soft_macro = self.SoftMacro(name=node_name, width=attr_dict['width'][1],
                                                    height=attr_dict['height'][1],
                                                    x=attr_dict['x'][1], y=attr_dict['y'][1])
                        self.modules_w_pins.append(soft_macro)
                        self.modules.append(soft_macro)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt - 1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt - 1] = node_name
                        # store current node indx
                        self.soft_macro_indices.append(node_cnt - 1)

                    elif attr_dict['type'][1] == 'macro_pin':
                        # [MACRO_NAME]/[PIN_NAME]
                        soft_macro_name = node_name.rsplit('/', 1)[0]
                        # soft macro pin
                        soft_macro_pin = self.SoftMacroPin(name=node_name, ref_id=None,
                                                           x=attr_dict['x'][1],
                                                           y=attr_dict['y'][1],
                                                           macro_name=attr_dict['macro_name'][1])

                        if 'weight' in attr_dict.keys():
                            soft_macro_pin.set_weight(float(attr_dict['weight'][1]))

                        # if pin has net info
                        if input_list:
                            # net count should be factored by net weight
                            if 'weight' in attr_dict.keys():
                                self.net_cnt += 1 * float(attr_dict['weight'][1])
                            else:
                                self.net_cnt += 1
                            soft_macro_pin.add_sinks(input_list)

                        self.modules_w_pins.append(soft_macro_pin)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt - 1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt - 1] = node_name
                        # store current node indx
                        self.soft_macro_pin_indices.append(node_cnt - 1)

                        if soft_macro_name in self.soft_macros_to_inpins.keys():
                            self.soft_macros_to_inpins[soft_macro_name] \
                                .append(soft_macro_pin.get_name())
                        else:
                            self.soft_macros_to_inpins[soft_macro_name] \
                                = [soft_macro_pin.get_name()]

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
                        self.mod_name_to_indices[node_name] = node_cnt - 1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt - 1] = node_name
                        # store current node indx
                        self.hard_macro_indices.append(node_cnt - 1)

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
                            hard_macro_pin.set_weight(float(attr_dict['weight'][1]))

                        # if pin has net info
                        if input_list:
                            # net count should be factored by net weight
                            if 'weight' in attr_dict.keys():
                                self.net_cnt += 1 * float(attr_dict['weight'][1])
                            else:
                                self.net_cnt += 1
                            hard_macro_pin.add_sinks(input_list)

                        self.modules_w_pins.append(hard_macro_pin)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt - 1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt - 1] = node_name
                        # store current node indx
                        self.hard_macro_pin_indices.append(node_cnt - 1)

                        # add to dict
                        if hard_macro_name in self.hard_macros_to_inpins.keys():
                            self.hard_macros_to_inpins[hard_macro_name] \
                                .append(hard_macro_pin.get_name())
                        else:
                            self.hard_macros_to_inpins[hard_macro_name] \
                                = [hard_macro_pin.get_name()]

                    elif attr_dict['type'][1] == 'PORT':
                        # port
                        port = self.Port(name=node_name,
                                         x=attr_dict['x'][1],
                                         y=attr_dict['y'][1],
                                         side=attr_dict['side'][1])

                        # if pin has net info
                        if input_list:
                            self.net_cnt += 1
                            port.add_sinks(input_list)
                            # ports does not have pins so update connection immediately
                            port.add_connections(input_list)

                        self.modules_w_pins.append(port)
                        self.modules.append(port)
                        # mapping node_name ==> node idx
                        self.mod_name_to_indices[node_name] = node_cnt - 1
                        # mapping node idx ==> node_name
                        self.indices_to_mod_name[node_cnt - 1] = node_name
                        # store current node indx
                        self.port_indices.append(node_cnt - 1)

        # mapping connection degree to each macros
        self.__update_connection()

        # all hard macros are placed on canvas initially
        self.__update_init_placed_node()

        self.width = math.sqrt(self.get_area() / 0.6)
        self.height = math.sqrt(self.get_area() / 0.6)

    def __read_plc(self):
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

        for cnt, line in enumerate(open(self.place_file, 'r')):
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
            elif "Area" in line_item:
                # Total core area of modules
                _area = float(line_item[1])
            elif "Block" in line_item:
                # The block name of the testcase
                _block = str(line_item[1])
            elif all(it in line_item for it in \
                     ['Routes', 'per', 'micron', 'hor', 'ver']):
                # For routing congestion computation
                _routes_per_micron_hor = float(line_item[4])
                _routes_per_micron_ver = float(line_item[6])
            elif all(it in line_item for it in \
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
            elif all(it in line_item for it in ['HARD', 'MACROs']) \
                    and len(line_item) == 3:
                _hard_macros_cnt = int(line_item[2])
            elif all(it in line_item for it in ['HARD', 'MACRO', 'PINs']) \
                    and len(line_item) == 4:
                _hard_macro_pins_cnt = int(line_item[3])
            elif all(it in line_item for it in ['PORTs']) \
                    and len(line_item) == 2:
                _ports_cnt = int(line_item[1])
            elif all(it in line_item for it in ['SOFT', 'MACROs']) \
                    and len(line_item) == 3:
                _soft_macros_cnt = int(line_item[2])
            elif all(it in line_item for it in ['SOFT', 'MACRO', 'PINs']) \
                    and len(line_item) == 4:
                _soft_macro_pins_cnt = int(line_item[3])
            elif all(it in line_item for it in ['STDCELLs']) \
                    and len(line_item) == 2:
                _stdcells_cnt = int(line_item[1])
            elif all(it in line_item for it in ['MACROs']) \
                    and len(line_item) == 2:
                _macros_cnt = int(line_item[1])
            elif all(re.match(r'[0-9NEWS\.\-]+', it) for it in line_item) \
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

        self.width = math.sqrt(self.get_area() / 0.6)
        self.height = math.sqrt(self.get_area() / 0.6)

        return info_dict

    def load_plc(self, filename: str):
        self.place_file = filename
        info_dict = self.__read_plc()

        for mod_idx in info_dict['node_plc'].keys():
            mod_x = mod_y = mod_orient = mod_ifFixed = None
            try:
                mod_x = float(info_dict['node_plc'][mod_idx][0])
                mod_y = float(info_dict['node_plc'][mod_idx][1])
                mod_orient = info_dict['node_plc'][mod_idx][2]
                mod_ifFixed = int(info_dict['node_plc'][mod_idx][3])
            except Exception as e:
                QMessageBox.warning(None, '[ERROR PLC PARSER] {}'.format(str(e)), QMessageBox.Ok)

            # TODO ValueError: Error in calling RestorePlacement with ('./Plc_client/test/ariane/initial.plc',): Can't place macro i_ariane/i_frontend/i_icache/sram_block_3__tag_sram/mem/mem_inst_mem_256x45_256x16_0x0 at (341.75, 8.8835). Exceeds the boundaries of the placement area..

            self.modules_w_pins[mod_idx].set_pos(mod_x, mod_y)

            if mod_orient and mod_orient != '-':
                self.modules_w_pins[mod_idx].set_orientation(mod_orient)

            if mod_ifFixed == 0:
                self.modules_w_pins[mod_idx].set_fix_flag(False)
            elif mod_ifFixed == 1:
                self.modules_w_pins[mod_idx].set_fix_flag(True)

    def is_node_soft_macro(self, node_idx) -> bool:
        """
        Return if node is a soft macro
        """
        try:
            return node_idx in self.soft_macro_indices
        except IndexError:
            QMessageBox.warning(None, "[ERROR INDEX OUT OF RANGE] Can not process index at {}".format(node_idx), QMessageBox.Ok)
            exit(1)

    def get_node_type(self, node_idx: int) -> str:
        """
        Return node type
        """
        try:
            return self.modules_w_pins[node_idx].get_type()
        except IndexError:
            # NOTE: Google's API return NONE if out of range
            QMessageBox.warning(None, "[WARNING INDEX OUT OF RANGE] Can not process index at {}", QMessageBox.Ok)
            return None

    def get_area(self) -> float:
        """
        Compute Total Module Area
        """
        total_area = 0.0
        for mod in self.modules_w_pins:
            if hasattr(mod, 'get_area'):
                total_area += mod.get_area()
        return total_area

    def get_ref_node_id(self, node_idx=-1):
        """
        ref_node_id is used for macro_pins. Refers to the macro it belongs to.
        """
        if node_idx != -1:
            if node_idx in self.soft_macro_pin_indices or node_idx in self.hard_macro_pin_indices:
                pin = self.modules_w_pins[node_idx]
                return self.mod_name_to_indices[pin.get_macro_name()]
        return -1

    def get_pin_position(self, pin_idx):
        """
        private function for getting pin location
            * PORT = its own position
            * HARD MACRO PIN = ref position + offset position
            * SOFT MACRO PIN = ref position
        """
        try:
            assert (self.modules_w_pins[pin_idx].get_type() == 'MACRO_PIN' or \
                    self.modules_w_pins[pin_idx].get_type() == 'PORT')
        except Exception:
            QMessageBox.warning(None, "[ERROR PIN POSITION] Not a MACRO PIN", QMessageBox.Ok)
            exit(1)

        # Retrieve node that this pin instantiated on
        ref_node_idx = self.get_ref_node_id(pin_idx)

        if ref_node_idx == -1:
            if self.modules_w_pins[pin_idx].get_type() == 'PORT':
                return self.modules_w_pins[pin_idx].get_pos()
            else:
                print("[ERROR PIN POSITION] Parent Node Not Found.")
                exit(1)

        # Parent node
        ref_node = self.modules_w_pins[ref_node_idx]
        ref_node_x, ref_node_y = ref_node.get_pos()

        # Retrieve current pin node position
        pin_node = self.modules_w_pins[pin_idx]
        pin_node_x_offset, pin_node_y_offset = pin_node.get_offset()

        return (ref_node_x + pin_node_x_offset, ref_node_y + pin_node_y_offset)

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
                    QMessageBox.warning(None, "[ERROR UPDATE CONNECTION] MACRO pins not found", QMessageBox.Ok)
                    continue

            # Soft macro
            elif self.is_node_soft_macro(macro_idx):
                if macro_name in self.soft_macros_to_inpins.keys():
                    pin_names = self.soft_macros_to_inpins[macro_name]
                else:
                    QMessageBox.warning(None, "[ERROR UPDATE CONNECTION] macro pins not found", QMessageBox.Ok)
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

    # Board Entity Definition
    class Port:
        def __init__(self, name, x=0.0, y=0.0, side="BOTTOM"):
            self.name = name
            self.x = float(x)
            self.y = float(y)
            self.side = side  # "BOTTOM", "TOP", "LEFT", "RIGHT"
            self.sink = {}  # standard cells, macro pins, ports driven by this cell
            self.connection = {}  # [module_name] => edge degree
            self.fix_flag = True
            self.placement = 0  # needs to be updated
            self.orientation = None
            self.ifPlaced = True

        def get_name(self):
            return self.name

        def get_orientation(self):
            return self.orientation

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

        def set_side(self, side):
            self.side = side

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

        def get_connection(self):
            return self.connection

        def get_type(self):
            return "PORT"

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

        def get_fix_flag(self):
            return self.fix_flag

        def set_placed_flag(self, ifPlaced):
            self.ifPlaced = ifPlaced

        def get_placed_flag(self):
            return self.ifPlaced

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
            self.ifPlaced = True
            self.location = 0  # needs to be updated

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

        def get_connection(self):
            return self.connection

        def set_orientation(self, orientation):
            self.orientation = orientation

        def get_orientation(self):
            return self.orientation

        def get_area(self):
            return self.width * self.height

        def get_height(self):
            return self.height

        def get_width(self):
            return self.width

        def set_height(self, height):
            self.height = height

        def set_width(self, width):
            self.width = width

        def set_location(self, grid_cell_idx):
            self.location = grid_cell_idx

        def get_location(self):
            return self.location

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

        def get_fix_flag(self):
            return self.fix_flag

        def set_placed_flag(self, ifPlaced):
            self.ifPlaced = ifPlaced

        def get_placed_flag(self):
            return self.ifPlaced

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

        def set_ref_id(self, ref_id):
            self.ref_id = ref_id

        def get_ref_id(self):
            return self.ref_id

        def get_weight(self):
            return self.weight

        def get_name(self):
            return self.name

        def get_macro_name(self):
            return self.macro_name

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
            self.ifPlaced = True
            self.location = 0  # needs to be updated

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

        def get_connection(self):
            return self.connection

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

        def get_area(self):
            return self.width * self.height

        def get_height(self):
            return self.height

        def get_width(self):
            return self.width

        def set_location(self, grid_cell_idx):
            self.location = grid_cell_idx

        def get_location(self):
            return self.location

        def set_fix_flag(self, fix_flag):
            self.fix_flag = fix_flag

        def get_fix_flag(self):
            return self.fix_flag

        def set_placed_flag(self, ifPlaced):
            self.ifPlaced = ifPlaced

        def get_placed_flag(self):
            return self.ifPlaced

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
            self.ifPlaced = True

        def set_ref_id(self, ref_id):
            self.ref_id = ref_id

        def get_ref_id(self):
            return self.ref_id

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

        def get_name(self):
            return self.name

        def get_macro_name(self):
            return self.macro_name

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


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.main_widget = QWidget(self)
        self.pdata = PData()

        self._figure = None
        self._plot_canvas = None
        self._static_ax = None

        self._showAnnotation = False
        self._amplify = False

        self.init_ui()

    def init_ui(self):
        self.init_menu()
        self.statusBar().showMessage('Ready')
        self.setGeometry(300, 300, 600, 600)
        self.center()
        self.setWindowTitle('ProtoBuf circuit visualizer')

        layout = QVBoxLayout(self.main_widget)
        self._figure = Figure(figsize=(5, 3))
        self._plot_canvas = FigureCanvas(self._figure)
        layout.addWidget(self._plot_canvas)
        self.addToolBar(NavigatorToolbar(self._plot_canvas, self))

        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

        self._static_ax = self._plot_canvas.figure.subplots()
        self._static_ax.grid(True)

        self.show()

    def init_menu(self):
        exit_action = QAction('&Exit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit app')
        exit_action.triggered.connect(qApp.quit)

        open_netlist_action = QAction('&Open netlist', self)
        open_netlist_action.setShortcut('Ctrl+O')
        open_netlist_action.setStatusTip('Open netlist')
        open_netlist_action.triggered.connect(self.show_openproto_dialog)

        open_place_action = QAction('Open &placement', self)
        open_place_action.setShortcut('Ctrl+P')
        open_place_action.setStatusTip('Open placement')
        open_place_action.triggered.connect(self.show_openplace_dialog)

        show_annotation_action = QAction('&Show annotation', self)
        show_annotation_action.setCheckable(True)
        show_annotation_action.setShortcut('Ctrl+S')
        show_annotation_action.triggered.connect(self.check_annotation)

        amplify_annotation_action = QAction('&Amplify images', self)
        amplify_annotation_action.setCheckable(True)
        amplify_annotation_action.setShortcut('Ctrl+A')
        amplify_annotation_action.triggered.connect(self.check_amplify)

        about_action = QAction('&About', self)
        about_action.triggered.connect(self.show_about_dialog)

        self.statusBar()

        menubar = self.menuBar()

        file_menu = menubar.addMenu('&File')
        file_menu.addAction(open_netlist_action)
        file_menu.addAction(open_place_action)
        file_menu.addAction(exit_action)

        options_menu = menubar.addMenu('&Options')
        options_menu.addAction(show_annotation_action)
        options_menu.addAction(amplify_annotation_action)


        help_menu = menubar.addMenu('&Help')
        help_menu.addAction(about_action)

    def show_about_dialog(self):
        QMessageBox.about(self, "ProtoBuf circuit visualizer",
                          "ProtoBuf circuit visualizer.\nVersion 0.0.1")

    def check_annotation(self):
        self._showAnnotation = not self._showAnnotation
        self.update_plot()

    def check_amplify(self):
        self._amplify = not self._amplify
        self.update_plot()

    def show_openproto_dialog(self):
        filename = QFileDialog.getOpenFileName(
            self, 'Open file', '.', "Netlist files (*.pb.txt)")

        if filename.__len__() > 0:
            filename = filename[0]
        else:
            return

        if not filename:
            return

        self.pdata = PData()
        self.pdata.netlist_file = filename

        try:
            self.pdata.read_protobuf()
            self.update_plot()
        except ValueError:
            QMessageBox.warning(self, "Warning while reading netlist", QMessageBox.Ok)

    def show_openplace_dialog(self):
        filename = QFileDialog.getOpenFileName(
            self, 'Open file', '.', "Placement files (*.plc)")

        if filename.__len__() > 0:
            filename = filename[0]
        else:
            return

        if not filename:
            return

        try:
            self.pdata.load_plc(filename)
            self.update_plot()
        except ValueError:
            QMessageBox.warning(self, "Warning while reading placement", QMessageBox.Ok)

    def remove_plots(self):
        if self._static_ax is not None:
            self._static_ax.clear()
            self._static_ax.grid(True)

        if self._plot_canvas is not None:
            self._plot_canvas.draw()

    def update_plot(self):
        self.remove_plots()

        if self._amplify:
            PORT_SIZE = 4
            FONT_SIZE = 10
            PIN_SIZE = 4
        else:
            PORT_SIZE = 2
            FONT_SIZE = 5
            PIN_SIZE = 2

        annotate = self._showAnnotation
        self._static_ax.set_aspect('equal')
        self._static_ax.plot(0, 0)

        for mod in self.pdata.modules_w_pins:
            if mod.get_type() == 'PORT' and mod.get_placed_flag():
                self._static_ax.plot(*mod.get_pos(), 'ro', markersize=PORT_SIZE)
            elif mod.get_type() == 'MACRO' and mod.get_placed_flag():
                if not self.pdata.is_node_soft_macro(self.pdata.mod_name_to_indices[mod.get_name()]):
                    # hard macro
                    self._static_ax.add_patch(
                        Rectangle((mod.get_pos()[0] - mod.get_width() / 2, mod.get_pos()[1] - mod.get_height() / 2), \
                                  mod.get_width(), mod.get_height(), \
                                  alpha=0.5, zorder=1000, facecolor='b', edgecolor='darkblue'))
                    if annotate:
                        self._static_ax.annotate(mod.get_name(), mod.get_pos(), wrap=True, color='r', weight='bold',
                                    fontsize=FONT_SIZE, ha='center', va='center')
                else:
                    # soft macro
                    self._static_ax.add_patch(
                        Rectangle((mod.get_pos()[0] - mod.get_width() / 2, mod.get_pos()[1] - mod.get_height() / 2), \
                                  mod.get_width(), mod.get_height(), \
                                  alpha=0.5, zorder=1000, facecolor='y'))
                    if annotate:
                        self._static_ax.annotate(mod.get_name(), mod.get_pos(), wrap=True, color='r', weight='bold',
                                    fontsize=FONT_SIZE, ha='center', va='center')
            elif mod.get_type() == 'MACRO_PIN':
                pin_idx = self.pdata.mod_name_to_indices[mod.get_name()]
                macro_idx = self.pdata.get_ref_node_id(pin_idx)
                macro = self.pdata.modules_w_pins[macro_idx]
                if macro.get_placed_flag():
                    self._static_ax.plot(*self.pdata.get_pin_position(pin_idx), 'bo', markersize=PIN_SIZE)
            # elif mod.get_type() == 'macro' :
            #     ax.add_patch(Rectangle((mod.get_pos()[0] - mod.get_width()/2, mod.get_pos()[1] - mod.get_height()/2),\
            #         mod.get_width(), mod.get_height(),\
            #         alpha=0.5, zorder=1000, facecolor='y'))
            #     if annotate:
            #         ax.annotate(mod.get_name(), mod.get_pos(), wrap=True,color='r', weight='bold', fontsize=FONT_SIZE, ha='center', va='center')

        self._plot_canvas.draw()

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Message', "Are you sure to quit",
                                     QMessageBox.No | QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = MainWindow()

    sys.exit(app.exec_())
