########################## Details to use this script ##########################
# Author: Rustam Chochaev    email: rchochaev@gmail.com
# Based on gen_pb_or.tcl by Sayak Kundu (email: sakundu@ucsd.edu)
# Date: 12-27-2022
# This script converts LEF / DEF format to Placement format using OpenROAD.
# Follow the below steps to generate Placement file from LEF / DEF in the
# OpenROAD shell:
#   1. read_lef <tech lef>
#   2. read_lef <standard cell and macro lef one by one>
#   3. read_def <design def file>
#   4. source <This script file>
#   5. gen_plc <path of the output placement file>
################################################################################
proc count_ports { block } {
  set no_ports 0

  foreach port_ptr [$block getBTerms] {  
    #puts "#$no_ports PORT: [${port_ptr} getName]"
    incr no_ports
  }

  return $no_ports
}

proc count_pins { inst_ptr } {
  set pins 0

  foreach macro_pin_ptr [${inst_ptr} getITerms] {
    if {[${macro_pin_ptr} isInputSignal] || [${macro_pin_ptr} isOutputSignal]} {
      incr pins
    }
  }

  return $pins
}

proc count_instances { block } {

  set no_hard_macros     0
  set no_hard_macro_pins 0
  set no_soft_macros     0
  set no_soft_macro_pins 0
  set no_macros          0
  set no_macro_pins      0
  set no_stdcells        0

  foreach inst_ptr [$block getInsts] {
   ### Hard Macro ###
    if { [${inst_ptr} isBlock] } {
      set inst_master [${inst_ptr} getMaster]
      
      set no_pins [count_pins ${inst_ptr}]

      if { [string match [${inst_master} getType] "BLOCK_SOFT"] } {
        #puts "#$no_soft_macros SOFT: [${inst_ptr} getName]"

        incr no_soft_macros
        incr no_soft_macro_pins $no_pins

      } else {
        #puts "#$no_hard_macros HARD: [${inst_ptr} getName]"

        incr no_hard_macros 
        incr no_hard_macro_pins $no_pins
      }
      
      incr no_macros
      incr no_macro_pins $no_pins
    } elseif { [${inst_ptr} isCore] } {
      #puts "#$no_stdcells STDCELL: [${inst_ptr} getName]"
      incr no_stdcells
    }
  }

  dict set results hm "$no_hard_macros" 
  dict append results hmp "$no_hard_macro_pins"
  dict append results sm "$no_soft_macros" 
  dict append results smp "$no_soft_macro_pins"
  dict append results m "$no_macros" 
  dict append results mp "$no_macro_pins"
  dict append results stdc "$no_stdcells"

  return $results
}

#### Print the design header ####
proc print_header { fp } {
  set block [ord::get_db_block]
  set design [$block getName]
  set user [exec whoami]
  set date [exec date]
  set run_dir [exec pwd]
  set canvas_width [ord::dbu_to_microns [[$block getCoreArea] dx]]
  set canvas_height [ord::dbu_to_microns [[$block getCoreArea] dy]]
  set canvas_area [expr $canvas_width * $canvas_height]

  set node_types [count_instances $block]
  set no_ports   [count_ports $block]

  ## Add dummy Column and Row info ##
  puts $fp "# Columns: 22 Rows: 25"
  puts $fp "# Width: $canvas_width  Height: $canvas_height"
  puts $fp "# Area: $canvas_area"
  puts $fp "# Counts of node types:"
  puts $fp "# HARD_MACROs     :       [dict get $node_types hm]"
  puts $fp "# HARD_MACRO_PINs :       [dict get $node_types hmp]"
  puts $fp "# MACROs          :       [dict get $node_types m]"
  puts $fp "# MACRO_PINs      :       [dict get $node_types mp]"
  puts $fp "# PORTs           :       $no_ports"
  puts $fp "# SOFT_MACROs     :       [dict get $node_types sm]"
  puts $fp "# SOFT_MACRO_PINs :       [dict get $node_types smp]"
  puts $fp "# STDCELLs        :       [dict get $node_types stdc]"
  puts $fp "# node_index x y orientation fixed"
}

### Helper to convert Orientation format ###
proc get_orient { tmp_orient } {
  set orient "N"
  if { $tmp_orient == "R0"} {
    set orient "N"
  } elseif { $tmp_orient == "R180" } {
    set orient "S"
  } elseif { $tmp_orient == "R90" } {
    set orient "W"
  } elseif { $tmp_orient == "R270" } {
    set orient "E"
  } elseif { $tmp_orient == "MY" } {
    set oreint "FN"
  } elseif { $tmp_orient == "MX" } {
    set oreint "FS"
  } elseif { $tmp_orient == "MX90" } {
    set orient "FW" 
  } elseif { $tmp_orient == "MY90" } {
    set orient "FE"
  }
  return $orient
}

### Procedure Find Mid Point ###
proc find_mid_point_bbox { rect } {
  set xmin [$rect xMin]
  set ymin [$rect yMin]
  set dx [$rect getDX]
  set dy [$rect getDY]
  set pt_x [expr $xmin + $dx/2]
  set pt_y [expr $ymin + $dy/2]
  return [list $pt_x $pt_y]
}

#### Procedure to write Ports ####
proc write_node_port { port_idx port_ptr fp } {

  ### Adjusting Core and Die ###
  set term_box [$port_ptr getBBox]
  set mid_pts [find_mid_point $term_box]
  set X [ord::dbu_to_microns [lindex $mid_pts 0]]
  set Y [ord::dbu_to_microns [lindex $mid_pts 1]]
  set dx [ord::dbu_to_microns [[[ord::get_db_block] getDieArea] dx]]
  set dy [ord::dbu_to_microns [[[ord::get_db_block] getDieArea] dy]]
  set die_llx [ord::dbu_to_microns [[[ord::get_db_block] getDieArea] xMin]]
  set die_lly [ord::dbu_to_microns [[[ord::get_db_block] getDieArea] yMin]]
  set side [find_bterm_side [expr $X - $die_llx] [expr $Y - $die_lly]\
            $dx $dy]
  
  ### Attribute: X, Y and Side ###
  set origin_x [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] xMin]]
  set origin_y [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] yMin]]

  ### Attribute: X ###
  if {$side == "top" || $side == "bottom"} {
    set X [expr $X - $origin_x]
  } elseif { $side == "right" } {
    set X [expr $X - 2*$origin_x]
  }
  
  ### Attribute: Y ###
  if {$side == "left" || $side == "right"} {
    set Y [expr $Y - $origin_y]
  } elseif { $side == "top" } {
    set Y [expr $Y - 2*$origin_y]
  }
  
  ### Attribute: Orient ###
  set orient "-"

  ### Attribute: isFixed ###
  # set isFixed [$port_ptr isFixed]
  set isFixed 0

  ### Print ###
  puts $fp [format "%u %.2f %.2f %s %u" $port_idx $X $Y $orient $isFixed]
  
}

#### Procedure to write Macros ####
proc write_node_macro { macro_idx macro_ptr fp } {

  set inst_box [$macro_ptr getBBox]
  set pts [find_mid_point_bbox $inst_box]
  set origin_x [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] xMin]]
  set origin_y [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] yMin]]

  ### Attribute: X ###
  set X [ord::dbu_to_microns [lindex $pts 0]]
  set X [expr $X - $origin_x]

  ### Attribute: Y ###
  set Y [ord::dbu_to_microns [lindex $pts 1]]
  set Y [expr $Y - $origin_y]
  
  ### Attribute: Orient ###
  set tmp_orient [${macro_ptr} getOrient]
  set orient [get_orient $tmp_orient]

  ### Attribute: isFixed ###
  # set isFixed [$macro_ptr isFixed]
  set isFixed 0

  ### Print ###
  puts $fp [format "%u %.2f %.2f %s %u" $macro_idx $X $Y $orient $isFixed]
}

#### Procedure to Write Std-cell ###
proc write_node_stdcell { inst_idx inst_ptr fp } {

  set inst_box [$inst_ptr getBBox]
  set pts [find_mid_point_bbox $inst_box]
  set origin_x [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] xMin]]
  set origin_y [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] yMin]]

  ### Attribute: X ###
  set X [ord::dbu_to_microns [lindex $pts 0]]
  set X [expr $X - $origin_x]

  ### Attribute: Y ###
  set Y [ord::dbu_to_microns [lindex $pts 1]]
  set Y [expr $Y - $origin_y]

  ### Attribute: Orient ###
  set tmp_orient [${inst_ptr} getOrient]
  set orient [get_orient $tmp_orient]

  ### Attribute: isFixed ###
  # set isFixed [$inst_ptr isFixed]
  set isFixed 0

  ### Print ###
  puts $fp [format "%u %.2f %.2f %s %u" $inst_idx $X $Y $orient $isFixed]
}

#### Generate protobuff format netlist ####
proc gen_plc { {file_name ""} } {
  set block [ord::get_db_block]
  set design [$block getName]
  
  if { $file_name != "" } {
    set out_file ${file_name}
  } else {
    set out_file "${design}.plc"
  }
  
  set plc_idx 0
  set fp [open $out_file w+]

  print_header $fp

  foreach port_ptr [$block getBTerms] {  
    write_node_port $plc_idx $port_ptr $fp
    incr plc_idx
  }

  foreach inst_ptr [$block getInsts] {
    ### Macro ###
    if { [${inst_ptr} isBlock] } {
      write_node_macro $plc_idx $inst_ptr $fp
      incr plc_idx
      foreach macro_pin_ptr [${inst_ptr} getITerms] {
        if {[${macro_pin_ptr} isInputSignal] || [${macro_pin_ptr} isOutputSignal]} {
          incr plc_idx
        }
      }
    } elseif { [${inst_ptr} isCore] } {
      ### Standard Cells ###
      write_node_stdcell $plc_idx $inst_ptr $fp
      incr plc_idx
    }
  }
  close $fp
  puts "Output netlist: $out_file"
}
