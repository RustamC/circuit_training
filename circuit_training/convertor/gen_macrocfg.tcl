########################## Details to use this script ##########################
# Author: Rustam Chochaev    email: rchochaev@gmail.com
# Date: 11-22-2022
# This script creates macrocfg file from initial DEF and plc file using OpenROAD.
# macrocfg file is a file that contains placement data for hard macros.
# Follow the below steps to create macrocfg file in the
# OpenROAD shell:
#   1. read_lef <tech lef>
#   2. read_lef <standard cell and macro lef one by one>
#   3. read_def <design def file>
#   4. source <This script file>
#   5. gen_macrocfg <path of the output def>
################################################################################

#### Procedure to Update Macros ####
proc write_macro {file_ptr macro_ptr} {
  set origin_x [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] xMin]]
  set origin_y [ord::dbu_to_microns [[[ord::get_db_block] getCoreArea] yMin]]

  ### Attribute: name ###
  set name [dict get $macro_ptr name]

  set macro [[ord::get_db_block] findInst "$name"]
  if {$macro == "NULL"} {
    puts stderr "$name is not found in LEF/DEF database!"
    exit 1
  }

  ### Attribute: X ###
  set x [dict get $macro_ptr x]
  set x [expr $x + $origin_x]

  ### Attribute: Y ###
  set y [dict get $macro_ptr y]
  set y [expr $y + $origin_y]

  ### Attribute: Orient ###
  set orient [dict get $macro_ptr orient]

  puts $file_ptr [format "%s %.3f %.3f %s" $name $x $y $orient]
}

#### Generate def format plc ####
proc gen_macrocfg { {file_name ""} {plc_cells {}} } {
  set db [ord::get_db]
  set block [ord::get_db_block]
  set design [$block getName]

  if { $file_name != "" } {
    set out_file ${file_name}
  } else {
    set out_file "${design}.cfg"
  }

  set fp [open $out_file w]

  foreach inst_ptr [$block getInsts] {
    ### Macro ###
    set macro_ptr [lsearch -index 1 -inline $plc_cells [${inst_ptr} getName]]
    
    if { $macro_ptr != "" } {
      if { [${inst_ptr} isBlock] } {
        write_macro $fp $macro_ptr
      }
    }
  }

  puts "Output cfg: $out_file"
  close $fp
}
