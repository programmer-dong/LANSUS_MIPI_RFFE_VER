from datetime import datetime
import os
import random
import shutil
import subprocess
import pandas as pd
import sys
import xlrd

mipi_reserver_all_reg = ["0x1c", "0x1d", "0x1e", "0x1f",
                         "0x20", "0x21", "0x22", "0x23",
                         "0x24", "0x2a", "0x2b", "0x2c",
                         "0x2d", "0x2e", "0x2f", "0x30",
                         "0x31", "0x32", "0x33", "0x34",
                         "0x35", "0x36", "0x37", "0x37",
                         "0x38", "0x39", "0x3a", "0x3b",
                         "0x3c", "0x3d", "0x3e", "0x3f"]


def get_excel_data(register_file):
    try:
        excel_file = xlrd.open_workbook(register_file)
        mipi_sheet = excel_file.sheet_by_name("MIPI")
        command_dict = {
            (mipi_sheet.cell_value(0, 4)).strip(): (mipi_sheet.cell_value(0, 5)).strip(),  # E1单元格作为键，F1单元格作为值
            (mipi_sheet.cell_value(1, 4)).strip(): (mipi_sheet.cell_value(1, 5)).strip()  # E2单元格作为键，F2单元格作为值
        }
        df = pd.read_excel(register_file, sheet_name="MIPI", skiprows=3)
        reg_dict = {}
        prev_reg_address = None
        reg_values = []  # 初始化reg_values
        # 新建command_dict来存储E1和E2单元格作为键，F1和F2单元格作为值

        for index, row in df.iterrows():
            reg_address = row[df.columns[0]]
            if pd.isnull(reg_address):
                reg_address = prev_reg_address

                # 如果寄存器地址发生变化，则将上一个寄存器地址的数据存储到字典中
            if prev_reg_address is not None and reg_address != prev_reg_address:
                reg_dict[prev_reg_address] = reg_values
                reg_values = []  # 重置reg_values

            # 组装除第一列外的其余列的值
            if prev_reg_address not in mipi_reserver_all_reg:
                reg_other = [row[col] for col in df.columns[1:]]
            else:
                reg_other = [row[col] for col in df.columns[1:] if df.columns.get_loc(col) != 4]

            reg_values.append(reg_other)
            prev_reg_address = reg_address

            # 存储最后一个寄存器地址的数据到字典中
        if prev_reg_address is not None:
            reg_dict[prev_reg_address] = reg_values

        return reg_dict, command_dict
    except Exception as e:
        print(f"Error reading the Excel file: {e}")
        sys.exit(1)


def reg_data_process(reg_data_all):  
    no_trigger_dict = {}  
    standard_trigger_dict = {}  
    extended_trigger_dict = {}  
    mipi_reserved_dict = {}  
    udr_set_dict = {}  
    # 遍历字典  
    for reg_address, reg_value in reg_data_all.items():  
        if reg_address.lower() not in mipi_reserver_all_reg:  
            if reg_value[0][6].lower() == "no":  
                no_trigger_dict[reg_address] = reg_value  # 直接使用 reg_value  
            elif reg_value[0][6].lower() in ["trigger_0", "trigger_1", "trigger_2"]:  
                standard_trigger_dict[reg_address] = reg_value  # 直接使用 reg_value  
            elif "mt" in reg_value[0][6].lower():  
                extended_trigger_dict[reg_address] = reg_value  # 直接使用 reg_value  
        else:  
            mipi_reserved_dict[reg_address] = reg_value  # 直接使用 reg_value  
    for reg_address_udr, reg_values in reg_data_all.items():  
        if reg_address_udr.lower() not in mipi_reserver_all_reg:  
            if len(reg_values) != 2:
                if reg_values[0][0].lower() == "udr_set" or "udr_set" in reg_values[0][2].lower(): 
                    udr_set_data = []  
                    for each_list in reg_values:  
                        udr_set_data.append([each_list[1], each_list[2]])  
                    udr_set_dict[reg_address_udr] = udr_set_data   
            if len(reg_values) == 2:
                if reg_values[0][0].lower() == "udr_set" or "udr_set" in reg_values[0][2].lower() or "udr_set" in reg_values[1][2].lower(): 
                    udr_set_data = []  
                    for each_list in reg_values:  
                        udr_set_data.append([each_list[1], each_list[2]])  
                    udr_set_dict[reg_address_udr] = udr_set_data   
    return no_trigger_dict, standard_trigger_dict, extended_trigger_dict, mipi_reserved_dict, udr_set_dict

def generate_random_integer():  
    return random.randint(1, 1000) 


# 生成随机写数据 “8’hxx”
def generate_hex_random():
    # 生成一个0到0xFFFF之间的随机数
    random_number = random.randint(0, 0xFF)
    hex_random = format(random_number, '02X')
    hex_random = "8'h" + hex_random
    return hex_random

def generate_random_list(length):  
    # 生成指定长度的随机数列表  
    return [generate_hex_random() for _ in range(length)]  

# 生成随机写数据 “8’hxx”
def generate_hex_random_two():
    # 生成一个0到0xFFFF之间的随机数
    random_number = random.randint(0, 0xFF)
    hex_random = format(random_number, '02X')
    hex_random = "9'h0" + hex_random
    return hex_random

def write_other_reg(file, test_reg, all_reg, ext_com_support):
    result_reg_data = {}
    file.write("$display(\"//******************************************//\");" + code_style)
    file.write("$display(\"//*****write other reg except test reg******//\");" + code_style)
    file.write("$display(\"//******************************************//\");" + code_style)
    file.write("begin"+code_style)
    for each_reg in all_reg:
        if each_reg != test_reg:
            reg_format = each_reg.split("x")[1]
            decimal_number = int(reg_format, 16)
            write_data = generate_hex_random()
            if decimal_number < 31:
                file.write(first_style + "reg_write(usid_user,8'h" + reg_format + "," + write_data + ");\n" + "     ")
                result_reg_data[each_reg] = write_data
            elif decimal_number > 31 and ext_com_support == "support":
                file.write(first_style + "ext_reg_write(usid_user,8'h" + reg_format + ",8'h00," + write_data + ");\n" + "     ")
                result_reg_data[each_reg] = write_data
    file.write("end"+code_style)
    return result_reg_data

def write_data_begin(file):
    file.write("bit [7:0] data;\n")
    file.write("bit [7:0] data_two;\n")
    file.write("bit [7:0] data_pre;\n")


def read_other_reg(file, result_write_reg, ext_com_support, first_indent):
    file.write(first_indent + "$display(\"//******************************************//\");" + code_style)
    file.write(first_indent + "$display(\"//******read other reg except test reg******//\");" + code_style)
    file.write(first_indent + "$display(\"//******************************************//\");" + code_style)
    file.write(first_indent + "begin"+code_style)
    for key_result, value_result in result_write_reg.items():
        parts = key_result.split("x")
        if len(parts) > 1:
            reg_format = parts[1]
            decimal_number = int(reg_format, 16)
            reserved_write = "" 
            if reserved_len != 0:  # Ensure reserved_len is defined somewhere  
                if key_result in reg_reserved_dicr:  
                    reserved_write = generate_mask_strings(reg_reserved_dicr[key_result])  
  
            if decimal_number < 31:  
                if reserved_write:  
                    file.write(loop_style + "reg_read_chk(usid_user,8'h" + reg_format  
                              + "," + value_result + reserved_write + ");" + code_style)  
                else:  
                    file.write(loop_style + "reg_read_chk(usid_user,8'h" + reg_format  
                              + "," + value_result + ");" + code_style)  
  
            elif decimal_number > 31 and ext_com_support == "support":  
                if reserved_write:  
                    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h" + reg_format  
                              + ",8'h00," + value_result + reserved_write + ");" + code_style)  
                else:  
                    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h" + reg_format  
                              + ",8'h00," + value_result + ");" + code_style)  
  
    file.write(first_indent + "end" + code_style)



def check_mipi_default_value(all_trigger_dict, command_support):
    with open("sim_default_value.v", 'w', encoding='utf-8') as sim_defult_file:
        sim_defult_file.write("task sim_default_value;\n")
        display_start_fun(sim_defult_file, "default value check ")
        for each_trigger, each_value in all_trigger_dict.items():
            if each_trigger.lower() not in mipi_reserver_all_reg:
                trigger_format = each_trigger.split("x")[1]
                value_str = ''.join([val[4] for val in each_value])
                default_value_dict[each_trigger] = value_str
                write_reg_chk(sim_defult_file, trigger_format, value_str, command_support)
        sim_defult_file.write("reg_read_chk(usid_user,8'h1c,9'h080);"+code_style)
        sim_defult_file.write("reg_read_chk(usid_user,8'h1d,{1'b0,product_id_user[7:0]});"+code_style)
        sim_defult_file.write("reg_read_chk(usid_user,8'h1e,{1'b0,man_id_uses[7:0]});"+code_style)
        sim_defult_file.write("reg_read_chk(usid_user,8'h1f,{1'b0,man_id_user[11:8],usid_user});"+code_style) 
        if '0x20' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h20,8'h00,{1'b0,ext_product_id_user[7:0]});"+code_style)
        if '0x21' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h21,8'h00,{1'b0,revision_id_user[7:0]});"+code_style)
        if '0x22' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h22,8'h00,{1'b0,8'h00});"+code_style)
        if '0x23' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h23,8'h00,{1'b0,8'h00});"+code_style)
        if '0x24' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h24,8'h00,{1'b0,8'h00});"+code_style)
        if '0x2b' in mipi_reserved_reg or '0x2B' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,{1'b0,busld_user[7:0]});"+code_style)
        if '0x2c' in mipi_reserved_reg or '0x2C' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h2c,8'h00,{1'b0,8'hd2});"+code_style)
        if '0x2d' in mipi_reserved_reg or '0x2D' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h2d,8'h00,{1'b0,8'h00});"+code_style)
        if '0x2e' in mipi_reserved_reg or '0x2E' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h2e,8'h00,{1'b0,8'h00});"+code_style)
        if '0x2f' in mipi_reserved_reg or '0x2F' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h2f,8'h00,{1'b0,8'h00});"+code_style)
        if '0x30' in mipi_reserved_reg:
            sim_defult_file.write("ext_reg_read_chk(usid_user,8'h30,8'h00,{1'b0,8'h00});"+code_style)
        sim_defult_file.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_default_value.v")
    shutil.move("sim_default_value.v", os.path.join("sim_case_list", "sim_default_value.v"))


def write_reg_chk(file, trigger_format, value_str, command_support):
    number_int = int(trigger_format, 16)
    if command_support == "support" and number_int > 31:
        file.write(f"ext_reg_read_chk(usid_user,8'h{trigger_format}, 8'h00, 9'b0{value_str});\n" + "     ")
    elif number_int <= 31:
        file.write(f"reg_read_chk(usid_user,8'h{trigger_format}, 9'b0{value_str});\n" + "     ")



'''
    tag=0:reg0_write no_trigger
    tag=1:reg_write no_trigger
    tag=2:ext_reg_write no_trigger
    tag=3:ext_reg_write_long no_trigger
    tag=4:reg0_write trigger
'''


def reg_trigger_test(file, reg_single, trigger, command, write_data, trigger_before):
    reg_format = reg_single.split("x")[1]
    if "trigger_0" in trigger.lower():
        if command == "reg0_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1011_0000);"+code_style)
            file.write("reg0_write(usid_user,"+write_data+");"+code_style)
            file.write("reg_read_chk(usid_user,8'h00,"+trigger_before+"&8'h7f);"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1011_0001);"+code_style)
            file.write("reg_read_chk(usdi_user,8'h00,"+write_data+"&8'h7f);" + code_style)
        elif command == "reg_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1011_0000);"+code_style)
            file.write("reg_write(usid_user,8'h"+reg_format+","+write_data+");"+code_style)
            file.write("reg_read_chk(usid_user,8'h"+reg_format+","+trigger_before+");"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1011_0001);"+code_style)
            file.write("reg_read_chk(usdi_user,8'h"+reg_format+","+write_data+");" + code_style)
        elif command == "ext_reg_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1011_0000);"+code_style)
            file.write("ext_reg_write(usid_user,8'h"+reg_format+",8'h00,"+write_data+");"+code_style)
            file.write("ext_reg_read_chk(usid_user,8'h"+reg_format+",8'h00,"+trigger_before+");"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1011_0001);"+code_style)
            file.write("ext_reg_read_chk(usdi_user,8'h"+reg_format+",8'h00,"+write_data+");" + code_style)
    elif "trigger_1" in trigger.lower():
        if command == "reg0_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1010_1000);"+code_style)
            file.write("reg0_write(usid_user,"+write_data+");"+code_style)
            file.write("reg_read_chk(usid_user,8'h00,"+trigger_before+"&8'h7f);"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1010_1010);"+code_style)
            file.write("reg_read_chk(usdi_user,8'h00,"+write_data+"&8'h7f);" + code_style)
        elif command == "reg_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1010_1000);"+code_style)
            file.write("reg_write(usid_user,8'h"+reg_format+","+write_data+");"+code_style)
            file.write("reg_read_chk(usid_user,8'h"+reg_format+","+trigger_before+");"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1010_1010);"+code_style)
            file.write("reg_read_chk(usdi_user,8'h"+reg_format+","+write_data+");" + code_style)
        elif command == "ext_reg_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1010_1000);"+code_style)
            file.write("ext_reg_write(usid_user,8'h"+reg_format+",8'h00,"+write_data+");"+code_style)
            file.write("ext_reg_read_chk(usid_user,8'h"+reg_format+",8'h00,"+trigger_before+");"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1010_1010);"+code_style)
            file.write("ext_reg_read_chk(usdi_user,8'h"+reg_format+",8'h00,"+write_data+");" + code_style)
    elif "trigger_2" in trigger.lower():
        if command == "reg0_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1001_1000);"+code_style)
            file.write("reg0_write(usid_user,"+write_data+");"+code_style)
            file.write("reg_read_chk(usid_user,8'h00,"+trigger_before+"&8'h7f);"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1001_1100);"+code_style)
            file.write("reg_read_chk(usdi_user,8'h00,"+write_data+"&8'h7f);" + code_style)
        elif command == "reg_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1001_1000);"+code_style)
            file.write("reg_write(usid_user,8'h"+reg_format+","+write_data+");"+code_style)
            file.write("reg_read_chk(usid_user,8'h"+reg_format+","+trigger_before+");"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1001_1100);"+code_style)
            file.write("reg_read_chk(usdi_user,8'h"+reg_format+","+write_data+");" + code_style)
        elif command == "ext_reg_write":
            file.write("//write data "+write_data+" by trigger" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1001_1000);"+code_style)
            file.write("ext_reg_write(usid_user,8'h"+reg_format+",8'h00,"+write_data+");"+code_style)
            file.write("ext_reg_read_chk(usid_user,8'h"+reg_format+",8'h00,"+trigger_before+");"+code_style)
            file.write("reg_write(usid_user,8'h1c,8'b1001_1100);"+code_style)
            file.write("ext_reg_read_chk(usdi_user,8'h"+reg_format+",8'h00,"+write_data+");" + code_style)

def write_spec_data(file, reg_single, tag):
    reg_format = reg_single.split("x")[1]
    file.write("$display(\"//******************************************//\");" + code_style)
    file.write("$display(\"//*******write special data to reg"+reg_format+"*******//\");" + code_style)
    file.write("$display(\"//******************************************//\");" + code_style)
    file.write("begin"+code_style)
    trigger = ""
    for reg_name, reg_value in sta_trigger_reg.items():
        if reg_name == reg_single:
            trigger = reg_value[0][6]   
    write_data_list = ["8'h55", "8'haa", "8'h66", "8'h99","8'h33", "8'hcc", "8'hff", "8'h00"]
    read_check_list = ["8'h00", "8'h55", "8'haa", "8'h66", "8'h99","8'h33", "8'hcc", "8'hff"]
    masked_write_data = ["8'haa,8'h55", "8'h66,8'h99", "8'hcc,8'h33", "8'hff,8'h00", "8'h00,8'h00"]
    masked_check = ["8'h55", "8'hdd", "8'hff", "8'hff", "8'h00"]
    decimal_number = int(reg_format, 16)
    for write_data, check_data in zip(masked_write_data, masked_check):
        if tag == 7 :
            file.write(first_style + "masked_write(usid_user,8'h"+reg_format+","+write_data+");"+code_style)     
            if decimal_number <= 31:
                reserved_written = False
                if reserved_len != 0:
                    for re_reg, re_value in reg_reserved_dicr.items():
                        if reg_single == re_reg:
                            reserved_write = generate_mask_strings(re_value)
                            file.write(first_style+"reg_read_chk(usid_user,8'h"+reg_format+","+"{1'b0,"+check_data+reserved_write+"});"+code_style)
                            reserved_written = True
                            break
                if not reserved_written:
                    file.write(first_style+"reg_read_chk(usid_user,8'h"+reg_format+","+"{1'b0,"+check_data+"});"+code_style)
            else:
                reserved_written = False
                if reserved_len != 0:
                    for re_reg, re_value in reg_reserved_dicr.items():
                        if reg_single == re_reg:
                            reserved_write = generate_mask_strings(re_value)
                            file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + "," + "8'h00,{1'b0,"+check_data + reserved_write+"});"+code_style)
                            reserved_written = True
                            break
                if not reserved_written:
                    file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + "," + "8'h00,{1'b0,"+check_data + "});"+code_style)
    for write_data, check_data in zip(write_data_list, read_check_list):
        if tag == 0:
            file.write(first_style + "reg0_write(usid_user," + write_data + ");\n" + "     ")
            file.write(first_style + "reg_read_chk(usid_user,8'h00," + "{1'b0,"+write_data + "&8'h7f});\n" + "     ")
        elif tag == 1:
            file.write(first_style + "reg_write(usid_user,8'h" + reg_format + "," + write_data + ");\n" + "     ")
            reserved_written = False
            if reserved_len != 0:
                for re_reg, re_value in reg_reserved_dicr.items():
                    if reg_single == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + "," + "{1'b0,"+write_data + reserved_write+"});\n" + "     ")
                        reserved_written = True
                        break
            if not reserved_written:
                file.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + "," + "{1'b0,"+write_data + "});\n" + "     ")
        elif tag == 2:
            file.write(first_style + "ext_reg_write(usid_user,8'h" + reg_format + ",8'h00," + write_data + ");\n" + "     ")
            reserved_written = False
            if reserved_len != 0:
                for re_reg, re_value in reg_reserved_dicr.items():
                    if reg_single == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + "," + "8'h00,{1'b0,"+write_data + reserved_write+"});\n" + "     ")
                        reserved_written = True
                        break
            if not reserved_written:
                file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + "," + "8'h00,{1'b0,"+write_data + "});\n" + "     ")
        elif tag == 3:
            file.write(first_style + "ext_reg_write_long(usid_user,16'h00" + reg_format + ",8'h00," + write_data + ");\n" + "     ")
            reserved_written = False
            if reserved_len != 0:
                for re_reg, re_value in reg_reserved_dicr.items():
                    if reg_single == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write(first_style + "ext_reg_read_long_chk(usid_user,16'h00" + reg_format + "," + "8'h00,{1'b0,"+write_data + reserved_write+"});\n" + "     ")
                        reserved_written = True
                        break
            if not reserved_written:
                file.write(first_style + "ext_reg_read_long_chk(usid_user,16'h00" + reg_format + "," + "8'h00,{1'b0,"+write_data + "});\n" + "     ")
        elif tag == 4 and "trigger" in trigger.lower():
            reg_trigger_test(file, reg_single, trigger, "reg0_write", write_data, check_data)
        elif tag == 5 and "trigger" in trigger.lower():
            reg_trigger_test(file, reg_single, trigger, "reg_write", write_data, check_data)
        elif tag == 6 and "trigger" in trigger.lower():
            reg_trigger_test(file, reg_single, trigger, "ext_reg_write", write_data, check_data)
    file.write("end"+code_style)

def reg_reset_command(file):
    file.write("// reset all\n" + "     ")
    file.write("reg_write(usid_user,8'h1c, 8'h40);\n" + "     ")


def usid_programmable_mode(mipi_reserved, command_support):
    with open("sim_usid_programmable.v", 'w', encoding='utf-8') as sim_usid_programmable_file:
        sim_usid_programmable_file.write("task sim_usid_programmable;\n")
        for mode in range(1, 4):
            sim_usid_programmable_file.write("\n" + f"$display(\"//===============================//\");\n")
            sim_usid_programmable_file.write(f"$display(\"//   usid programmable mode {mode}    //\");\n")
            sim_usid_programmable_file.write(f"$display(\"//===============================//\");\n" + "     ")
            if mode == 1:
                sim_usid_programmable_file.write("sclk_sel(0); //52M\n" + "     ")
                for i in range(1, 16):
                    sa_hex = hex(i)[2:].upper()
                    sim_usid_programmable_file.write(f"set_p1_sa(4'h{sa_hex});\n" + "     ")
                    sim_usid_programmable_file.write(
                        "reg_read_chk(usid_user,8'h1f,{man_id_user[11:8],4'h" + f"{sa_hex}}});\n" + "     ")
            elif mode == 2 and command_support == "support":
                for i in range(1, 16):
                    sa_hex = hex(i)[2:].upper()
                    sim_usid_programmable_file.write(f"set_p2_sa(4'h{sa_hex});\n" + "     ")
                    sim_usid_programmable_file.write(
                        "ext_reg_read_chk(usid_user,8'h1f,8'h00,{man_id_user[11:8],4'h" + f"{sa_hex}}});\n" + "     ")
            elif mode == 3 and "0x20" in mipi_reserved and command_support == "support":
                for i in range(1, 16):
                    sa_hex = hex(i)[2:].upper()
                    sim_usid_programmable_file.write(f"set_p3_sa(4'h{sa_hex});\n" + "     ")
                    sim_usid_programmable_file.write(
                        "ext_reg_read_chk(usid_user,8'h1f,8'h00,{man_id_user[11:8],4'h" + f"{sa_hex}}});\n" + "     ")
        reg_reset_command(sim_usid_programmable_file)
        sim_usid_programmable_file.write("\n" + "endtask" + "\n")

    remove_empty_lines("sim_usid_programmable.v")
    shutil.move("sim_usid_programmable.v", os.path.join("sim_case_list", "sim_usid_programmable.v"))


def sim_reg0_write_command(reg_dict, all_reg, reg_com_support):
    with open("sim_reg0_write_no_trigger.v", 'w', encoding='utf-8') as sim_reg0_write:
        write_data_begin(sim_reg0_write)
        sim_reg0_write.write("task sim_reg0_write_no_trigger;\n")
        display_start_fun(sim_reg0_write, "reg0_write_command ")
        if '0x00' in all_reg:
            trigger_disable(sim_reg0_write, reg_dict)
            result_reg_dict = write_other_reg(sim_reg0_write, '0x00', all_reg, reg_com_support)
            write_spec_data(sim_reg0_write, '0x00', 0)
            reg0_command_loop_body(sim_reg0_write, "usid_user", result_reg_dict, reg_com_support)
        reg_reset_command(sim_reg0_write)
        sim_reg0_write.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_reg0_write_no_trigger.v")
    shutil.move("sim_reg0_write_no_trigger.v", os.path.join("sim_case_list", "sim_reg0_write_no_trigger.v"))


def trigger_disable(file, all_reg_trigger):
    file.write("$display(\"****standard trigger disable****\");" + code_style)
    file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'hb8);" + "\n" + "     ")
    file.write("reg_read_chk(usid_user,8'h1c,9'h0b8);" + "\n" + "     ")
    if '0x2D' in all_reg_trigger or '0x2d' in all_reg_trigger:
        file.write("$display(\"****extended trigger disable****\");" + code_style)
        file.write("//============= trigger 3-10 ==============|0x2D" + code_style)
        file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + "\n" + "     ")
        file.write("ext_reg_read_chk(usid_user,8'h2d,8'h00,9'h0ff);" + "\n" + "     ")
    if '0x30' in all_reg_trigger:
        file.write("$display(\"****extended trigger disable****\");" + code_style)
        file.write("//============ trigger 11-17 ==============|0x30" + code_style)
        file.write("ext_reg_write(usid_user,8'h30,8'h00,8'hff);" + "\n" + "     ")
        file.write("ext_reg_read_chk(usid_user,8'h30,8'h00,9'h0ff);" + "\n" + "     ")

def trigger_enable(file, all_reg_trigger):
    file.write("$display(\"****standard trigger enable****\");" + code_style)
    file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h80);" + "\n" + "     ")
    file.write("reg_read_chk(usid_user,8'h1c,9'h080);" + "\n" + "     ")
    if '0x2D' in all_reg_trigger or '0x2d' in all_reg_trigger:
        file.write("$display(\"****extended trigger enable****\");" + code_style)
        file.write("//============= trigger 3-10 ==============|0x2D" + code_style)
        file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'h00);" + "\n" + "     ")
        file.write("ext_reg_read_chk(usid_user,8'h2d,8'h00,9'h000);" + "\n" + "     ")
    if '0x30' in all_reg_trigger:
        file.write("$display(\"****extended trigger enable****\");" + code_style)
        file.write("//============ trigger 11-17 ==============|0x30" + code_style)
        file.write("ext_reg_write(usid_user,8'h30,8'h00,8'h00);" + "\n" + "     ")
        file.write("ext_reg_read_chk(usid_user,8'h30,8'h00,9'h000);" + "\n" + "     ")

def reg0_command_loop_body(file, usid_user, result_reg_dict, ext_com_support):
    file.write("packet_rand = new(" + str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    reg0_write(usid_user,data);" + code_style)
    file.write("    reg_read_chk(usid_user,8'h00,{1'b0,data&8'b0111_1111});" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)


def reg0_command_trigger_loop_body(file, usid_user, result_reg_dict, ext_com_support, trigger_list):
    file.write("packet_rand = new(" + str(generate_random_integer()) + ");" +code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "packet_rand.randomize();" + code_style)
    file.write(first_style + "data = packet_rand.data_packet;" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[0] + ");" + code_style)
    file.write(first_style + "$display(\"****write data to reg00_shadow****\");" + code_style)
    file.write(first_style + "reg0_write(usid_user,data);" + code_style)
    file.write(first_style + "if(i==0)begin" + code_style)
    file.write(loop_style + "reg_read_chk(usid_user,8'h00,{1'b0,8'h00});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    file.write(loop_style + "reg_read_chk(usid_user,8'h00,{1'b0,(data_pre)&(8'b0111_1111)});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "$display(\"****trigger data to reg00_direct****\");" + code_style)
    if trigger_list[1] == trigger_0_reg:
        file.write(first_style + "// trigger_0" + code_style)
    elif trigger_list[1] == trigger_1_reg:
        file.write(first_style + "// trigger_1" + code_style)
    elif trigger_list[1] == trigger_2_reg:
        file.write(first_style + "// trigger_2" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[1] + ");" + code_style)
    file.write(first_style + "reg_read_chk(usid_user,8'h00,{1'b0,data&8'b0111_1111});" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;")

 
def reg_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support):
    reg_format = each_reg.split("x")[1]
    decimal_number = int(reg_format, 16)
    write_spec_data(file, each_reg, 1)
    if decimal_number <= 31:
        file.write("packet_rand = new(" +str(generate_random_integer())+ ");" + code_style)
        file.write("for(i=0; i<=255; i++) begin" + code_style)
        file.write("    packet_rand.randomize();" + code_style)
        file.write("    data = packet_rand.data_packet;" + code_style)
        file.write("    reg_write(" + usid_user + ",8'h" + reg_format + ",data);" + code_style)
        reserved_written = False
        if reserved_len != 0:
            for re_reg, re_value in reg_reserved_dicr.items():
                if each_reg == re_reg:
                    reserved_write = generate_mask_strings(re_value)
                    file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data"+reserved_write+"});" + code_style)
                    reserved_written = True
                    break
        if not reserved_written:
             file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data});" + code_style)
        read_other_reg(file, result_reg_dict, ext_com_support, first_style)
        file.write("end" + code_style)
        file.write("packet_rand = null;"+code_style)

def reg_command_trigger_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, trigger_list):
    reg_format = each_reg.split("x")[1]
    write_spec_data(file, each_reg, 5)
    file.write("// reg" + reg_format + code_style)
    file.write("$display(\"****reg"+reg_format+" trigger test****\");" + code_style)
    file.write("packet_rand = new(" +str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "packet_rand.randomize();" + code_style)
    file.write(first_style + "data = packet_rand.data_packet;" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[0] + ");" + code_style)
    file.write(first_style + "$display(\"****write data to reg"+reg_format+"_shadow****\");" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h" + reg_format + ",data);" + code_style)
    file.write(first_style + "if(i==0)begin" + code_style)
    file.write(loop_style + "reg_read_chk(usid_user,8'h"+reg_format+",{1'b0,8'h00});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    if reserved_len != 0:
        reserved_written = False
        for re_reg, re_value in reg_reserved_dicr.items():
            if each_reg == re_reg:
                reserved_write = generate_mask_strings(re_value)
                file.write(loop_style + "reg_read_chk(usid_user,8'h"+reg_format+",{1'b0,data_pre"+reserved_write+"});" + code_style)
                reserved_written = True
    if not reserved_written:
        file.write(loop_style + "reg_read_chk(usid_user,8'h"+reg_format+",{1'b0,data_pre});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "$display(\"****trigger data to reg"+reg_format+"_direct****\");" + code_style)
    if trigger_list[1] == trigger_0_reg:
        file.write(first_style + "// trigger_0" + code_style)
    elif trigger_list[1] == trigger_1_reg:
        file.write(first_style + "// trigger_1" + code_style)
    elif trigger_list[1] == trigger_2_reg:
        file.write(first_style + "// trigger_2" + code_style)
    file.write(first_style + "reg_write("+ usid_user + ",8'h1c," + trigger_list[1] + ");" + code_style)
    if reserved_len != 0:
        reserved_written = False
        for re_reg, re_value in reg_reserved_dicr.items():
            if each_reg == re_reg:
                reserved_write = generate_mask_strings(re_value)
                file.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data"+reserved_write+"});" + code_style)
                reserved_written = True
                break
    if not reserved_written:
        file.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data});" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)
    file.write("// reset reg1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'hb8);" + code_style)
    if '0x2d' in mipi_reserved_reg or '0x2D' in mipi_reserved_reg:
        file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + code_style)
    if '0x30' in mipi_reserved_reg:
        file.write("ext_reg_write(usid_user,8'h30,8'h00,8'hff);" + code_style)

def ext_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support):
    reg_format = each_reg.split("x")[1]
    write_spec_data(file, each_reg, 2)
    file.write("packet_rand = new("+str(generate_random_integer())+");" + code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    ext_reg_write(" + usid_user + ",8'h" + reg_format + ",8'h00,data);" + code_style)
    if reserved_len != 0:
        reserved_written = False
        for re_reg, re_value in reg_reserved_dicr.items():
            if each_reg == re_reg:
                reserved_write = generate_mask_strings(re_value)
                file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data"+reserved_write+"});" + code_style)
                reserved_written = True
    if not reserved_written:
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data});" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_null = null;"+code_style)


def ext_command_trigger_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, trigger_list, write_command):
    reg_format = each_reg.split("x")[1]
    write_spec_data(file, each_reg, 6)
    file.write("// reg" + reg_format + code_style)
    file.write("$display(\"****reg"+reg_format+" trigger test****\");" + code_style)
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[0] + ");" + code_style)
    file.write(first_style + "$display(\"****write data to reg"+reg_format+"_shadow****\");" + code_style)
    file.write(first_style + write_command[0] +"(usid_user,8'h" + reg_format + ",8'h00,data);" + code_style)
    file.write(first_style + "if(i==0)begin" + code_style)
    file.write(loop_style + write_command[1] +"(usid_user,8'h"+reg_format+",8'h00,{1'b0,8'h00});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    if reserved_len != 0:
        reserved_written = False
        for re_reg, re_value in reg_reserved_dicr.items():
            if each_reg == re_reg:
                reserved_write = generate_mask_strings(re_value)
                file.write(loop_style +  write_command[1] + "(usid_user,8'h"+reg_format+",8'h00,{1'b0,(data_pre)"+reserved_write+"});" + code_style)
                reserved_written = True
                break
    if not reserved_written:
        file.write(loop_style +  write_command[1] + "(usid_user,8'h"+reg_format+",8'h00,{1'b0,data_pre});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "$display(\"****trigger data to reg"+reg_format+"_direct****\");" + code_style)
    if trigger_list[1] == trigger_0_reg:
        file.write(first_style + "// trigger_0" + code_style)
    elif trigger_list[1] == trigger_1_reg:
        file.write(first_style + "// trigger_1" + code_style)
    elif trigger_list[1] == trigger_2_reg:
        file.write(first_style + "// trigger_2" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[1] + ");" + code_style)
    if reserved_len != 0:
        reserved_written = False
        for re_reg, re_value in reg_reserved_dicr.items():
            if each_reg == re_reg:
                reserved_write = generate_mask_strings(re_value)
                file.write(first_style +  write_command[1] + "(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data"+reserved_write+"});" + code_style)
                reserved_written = True
    if not reserved_written:
         file.write(first_style +  write_command[1] + "(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data});" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("// reset reg1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'hb8);" + code_style)
    if '0x2d' in mipi_reserved_reg or '0x2D' in mipi_reserved_reg:
        file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + code_style)
    if '0x30' in mipi_reserved_reg:
        file.write("ext_reg_write(usid_user,8'h30,8'h00,8'hff);" + code_style)

def ext_long_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support):
    reg_format = each_reg.split("x")[1]
    write_spec_data(file, each_reg, 3)
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    ext_reg_write_long(" + usid_user + ",8'h" + reg_format + ",8'h00,data);" + code_style)
    if reserved_len != 0:
        reserved_written = False
        for re_reg, re_value in reg_reserved_dicr.items():
            if each_reg == re_reg:
                reserved_write = generate_mask_strings(re_value)
                file.write("    ext_reg_read_long_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data"+reserved_write+"});" + code_style)
                reserved_write = True
                break
    if not reserved_written:
        file.write("    ext_reg_read_long_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data});" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)


def masked_write_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support):
    parts = each_reg.split("x")
    if len(parts) > 1:
        reg_format = parts[1]
        decimal_number = int(reg_format, 16)
        if decimal_number <= 31:
            write_spec_data(file, each_reg, 7)
            file.write("data_pre = 8'b" +default_value_dict[each_reg] +";"+code_style)
            file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
            file.write("packet_rand_two = new("+str(generate_random_integer())+");"+code_style)
            file.write("for(i=0; i<=255; i++) begin" + code_style)
            file.write("    bit [7:0] masked_result;" + code_style)
            file.write("    packet_rand.randomize();" + code_style)
            file.write("    packet_rand_two.randomize();" + code_style)
            file.write("    data = packet_rand.data_packet;" + code_style)
            file.write("    data_two = packet_rand_two.data_two_packet;" + code_style)
            file.write("    masked_result = (data_pre&data)|((~data)&data_two);" + code_style)
            file.write("    " + "masked_write(usid_user,8'h" + reg_format + ",data[7:0],data_two[7:0]);"
                       + "\n" + "     ")
            if reserved_len != 0:
                reserved_written = False
                for re_reg, re_value in reg_reserved_dicr.items():
                    if each_reg == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,masked_result"+reserved_write+"});"
                                + code_style)
                        reserved_written = True
                        break
            if not reserved_written:
                file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,masked_result});"+ code_style)
            file.write("    data_pre = masked_result;" + code_style)
            read_other_reg(file, result_reg_dict, ext_com_support, first_style)
            file.write("end" + code_style)
            file.write("packet_rand = null;"+code_style)
            file.write("packet_rand_two = null;"+code_style)
        elif decimal_number > 31 and ext_com_support == "support":
            write_spec_data(file, each_reg, 7)
            file.write("data_pre = 8'b" +default_value_dict[each_reg] +";"+code_style)
            file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
            file.write("packet_rand_two = new("+str(generate_random_integer())+");"+code_style)
            file.write("for(i=0; i<=255; i++) begin" + code_style)
            file.write("    bit [7:0] masked_result;" + code_style)
            file.write("    packet_rand.randomize();" + code_style)
            file.write("    packet_rand_two.randomize();" + code_style)
            file.write("    data = packet_rand.data_packet;" + code_style)
            file.write("    data_two = packet_rand_two.data_two_packet;" + code_style)
            file.write("    masked_result = (data_pre&data)|((~data)&data_two);" + code_style)
            file.write(
                "    " + "masked_write(usid_user,8'h" + reg_format + ",data[7:0],data_two[7:0]);" + "\n" + "     ")
            if reserved_len != 0:
                reserved_written = False
                for re_reg, re_value in reg_reserved_dicr.items():
                    if each_reg == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write(
                            "    ext_reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,masked_result"+reserved_write+"});" + code_style)
                        reserved_written = True
                        break
            if not reserved_written:
                file.write(
                            "    ext_reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,masked_result});" + code_style)
            file.write("    data_pre = masked_result;" + code_style)
            read_other_reg(file, result_reg_dict, ext_com_support, first_style)
            file.write("end" + code_style)
            file.write("packet_rand = null;"+code_style)
            file.write("packet_rand_two = null;"+code_style)


def masked_write_command_trigger_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, trigger_list):
    parts = each_reg.split("x")
    if len(parts) > 1:
        reg_format = parts[1]
        decimal_number = int(reg_format, 16)
        if decimal_number <= 31:
            write_spec_data(file, each_reg, 7)
            file.write("$display(\"*****standard trigger enble*****\");" + code_style)
            file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'h80);" + "\n" + "     ")
            file.write("reg_read_chk(usid_user,8'h1c,9'h080);" + "\n" + "     ")
            file.write("// reg" + reg_format + code_style)
            file.write("$display(\"****reg"+reg_format+" trigger test****\");" + code_style)
            file.write("data_pre = 8'b" +default_value_dict[each_reg] +";"+code_style)
            file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
            file.write("packet_rand_two = new("+str(generate_random_integer())+");"+code_style)
            file.write("for(i=0; i<=255; i++) begin" + code_style)
            file.write("    bit [7:0] masked_result;" + code_style)
            file.write("    packet_rand.randomize();" + code_style)
            file.write("    packet_rand_two.randomize();" + code_style)
            file.write("    data = packet_rand.data_packet;" + code_style)
            file.write("    data_two = packet_rand_two.data_two_packet;" + code_style)
            file.write("    masked_result = (data_pre&data)|((~data)&data_two);" + code_style)
            file.write("    " + "masked_write(usid_user,8'h" + reg_format + ",data[7:0],data_two[7:0]);"
                       + "\n" + "     ")
            if trigger_list[1] == trigger_0_reg:
                file.write(first_style + "// trigger_0" + code_style)
            elif trigger_list[1] == trigger_1_reg:
                file.write(first_style + "// trigger_1" + code_style)
            elif trigger_list[1] == trigger_2_reg:
                file.write(first_style + "// trigger_2" + code_style)
            file.write("    reg_write(usid_user,8'h1c,"+trigger_list[1]+");" + code_style)
            if reserved_len != 0:
                reserved_written = False
                for re_reg, re_value in reg_reserved_dicr.items():
                    if each_reg == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,masked_result"+reserved_write+"});"
                        + code_style)
                        reserved_written == True
                        break
            if not reserved_written:
                 file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,masked_result});"
                        + code_style)
            file.write("    data_pre = masked_result;"+ code_style)
            file.write("\n     ")
            read_other_reg(file, result_reg_dict, ext_com_support, first_style)
            file.write("end" + code_style)
            file.write("packet_rand = null;"+code_style)
            file.write("packet_rand_two = null;"+code_style)
            file.write("// reset reg1c" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'hb8);" + code_style)
            if '0x2d' in mipi_reserved_reg or '0x2D' in mipi_reserved_reg:
                file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + code_style)
            if '0x30' in mipi_reserved_reg:
                file.write("ext_reg_write(usid_user,8'h30,8'h00,8'hff);" + code_style)
        elif decimal_number > 31 and ext_com_support == "support":
            write_spec_data(file, each_reg, 7)
            file.write("$display(\"*****standard trigger enble*****\");" + code_style)
            file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'h80);" + "\n" + "     ")
            file.write("reg_read_chk(usid_user,8'h1c,9'h080);" + "\n" + "     ")
            file.write("// reg" + reg_format + code_style)
            file.write("$display(\"****reg"+reg_format+" trigger test****\");" + code_style)
            file.write("data_pre = 8'b" +default_value_dict[each_reg] +";"+code_style)
            file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
            file.write("packet_rand_two = new("+str(generate_random_integer())+");"+code_style)
            file.write("for(i=0; i<=255; i++) begin" + code_style)
            file.write("    bit [7:0] masked_result;" + code_style)
            file.write("    packet_rand.randomize();" + code_style)
            file.write("    packet_rand_two.randomize();" + code_style)
            file.write("    data = packet_rand.data_packet;" + code_style)
            file.write("    data_two = packet_rand_two.data_two_packet;" + code_style)
            file.write("    masked_result = (data_pre&data)|((~data)&data_two);" + code_style)
            file.write(
                "    " + "masked_write(usid_user,8'h" + reg_format + ",data[7:0],data_two[7:0]);" + "\n" + "     ")
            if trigger_list[1] == trigger_0_reg:
                file.write(first_style + "// trigger_0" + code_style)
            elif trigger_list[1] == trigger_1_reg:
                file.write(first_style + "// trigger_1" + code_style)
            elif trigger_list[1] == trigger_2_reg:
                file.write(first_style + "// trigger_2" + code_style)
            file.write("    reg_write(usid_user,8'h1c,"+trigger_list[1]+");" + code_style)
            if reserved_len != 0:
                reserved_written = False
                for re_reg, re_value in reg_reserved_dicr.items():
                    if each_reg == re_reg:
                        reserved_write = generate_mask_strings(re_value)
                        file.write(
                            "    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,masked_result"+reserved_write+"});" + code_style)
                        reserved_written = True
                        break
            if not reserved_write:
                 file.write(
                            "    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,masked_result});" + code_style)
            file.write("    data_pre = masked_result;"+ code_style)
            file.write("\n     ")
            read_other_reg(file, result_reg_dict, ext_com_support, first_style)
            file.write("end" + code_style)
            file.write("packet_rand = null;"+code_style)
            file.write("packet_rand_two = null;"+code_style)
            file.write("// reset reg1c" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
            file.write("reg_write(usid_user,8'h1c,8'hb8);" + code_style)
            if '0x2d' in mipi_reserved_reg or '0x2D' in mipi_reserved_reg:
                file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + code_style)
            if '0x30' in mipi_reserved_reg:
                file.write("ext_reg_write(usid_user,8'h30,8'h00,8'hff);" + code_style)

def extended_trigger_loop_body(file, usid_user,tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user):
    split_line(file, " start:" + tri_mask + " ")
    file.write("// trigger_mask_" + tri_mask.split("_")[1] + code_style)
    if tri_mask in ext_trigger_3_10:
        file.write("ext_reg_write(usid_user,8'h2d,8'h00," + tri_reg[0] + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h2d,8'h00," + tri_reg[0] + ");" + code_style)
    elif tri_mask in ext_trigger_11_17:
        file.write("ext_reg_write(usid_user,8'h30,8'h00," + tri_reg[0] + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h30,8'h00," + tri_reg[0] + ");" + code_style)
    file.write("$display(\"****select reg"+reg_format_udr+" trigger is " + tri_mask + "****\");" + code_style)
    if reg_value[1] in ['3:0', '3：0']:
        file.write("ext_reg_write(usid_user,8'h"+reg_format_udr+",8'h00,{4'b0000," + ext_udr_mapped[tri_mask] + "});" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h"+reg_format_udr+",8'h00,{4'b0000," + ext_udr_mapped[tri_mask] + "});" + code_style)
    elif reg_value[1] in ['7:4', '7：4']:
        file.write("ext_reg_write(usid_user,8'h"+reg_format_udr+",8'h00,{" + ext_udr_mapped[tri_mask] + ",4'b0000});" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h"+reg_format_udr+",8'h00,{" + ext_udr_mapped[tri_mask] + ",4'b0000});" + code_style)
    file.write("// reg" + reg_format_user + code_style)
    file.write("$display(\"****reg"+reg_format_user+" ext_trigger test****\");" + code_style)
    file.write("packet_rand = new(" + str(generate_random_integer()) + ");" + code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "packet_rand.randomize();" + code_style)
    file.write(first_style + "data = packet_rand.data_packet;" + code_style)
    file.write(first_style + "ext_reg_write(usid_user,8'h"+reg_format_user+",8'h00,data);" + code_style)
    file.write(first_style + "if(i==0) begin" + code_style)
    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h"+reg_format_user+",8'h00,{1'b0,9'h000});"+code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h"+reg_format_user+",8'h00,{1'b0,data_pre});"+code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "// " + tri_mask + code_style)
    if tri_mask in ext_trigger_3_10:
        file.write(first_style + "ext_reg_write(usid_user,8'h2e,8'h00," + tri_reg[1] + ");" + code_style)
    elif tri_mask in ext_trigger_11_17:
        file.write(first_style + "ext_reg_write(usid_user,8'h2f,8'h00, " + tri_reg[1] + ");" + code_style)
    file.write(first_style + "ext_reg_read_chk(usid_user,8'h"+reg_format_user+",8'h00,data);" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
    split_line(file, " end:" + tri_mask +" ")


def write_read_chk(file, reg_tri_cnt, number):  
    cmd = first_style + "ext_reg_read_chk(usid_user,8'h{:02x},8'h00,9'h{:03x});".format(int(reg_tri_cnt, 16), number)  
    file.write(cmd + '\n' + "     ")  
  
def timed_trigger_cnt(file, reg_tri_cnt, number):  
    number = int(number)  
    if not 0 <= number <= 255:  
        print("The value entered is illegal!!")  
        return  
      
    write_cmd =first_style+ "ext_reg_write(usid_user,8'h{:02x},8'h00,8'h{:02x});".format(int(reg_tri_cnt, 16), number)  
    file.write(write_cmd + '\n' + "     ")  
      
    if number <= 11:  
        write_read_chk(file, reg_tri_cnt, 0)  
    else:  
        number -= 11  
        write_read_chk(file, reg_tri_cnt, number)  
          
        while number > 0:  
            if number <= 17:  
                write_read_chk(file, reg_tri_cnt, 0)  
                break  
            number -= 17  
            write_read_chk(file, reg_tri_cnt, number)  
              
            if number <= 16:  
                write_read_chk(file, reg_tri_cnt, 0)  
                break  
            number -= 16  
            write_read_chk(file, reg_tri_cnt, number)

def extended_timed_trigger_loop_body(file, usid_user, tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user):
    split_line(file, " start:" + tri_mask + " ") 
    file.write("// trigger_mask_" + tri_mask.split("_")[1] + code_style)
    if tri_mask in ext_trigger_3_10:
        file.write("ext_reg_write(usid_user,8'h2d,8'h00," + tri_reg[0] + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h2d,8'h00," + tri_reg[0] + ");" + code_style)
    elif tri_mask in ext_trigger_11_17:
        file.write("ext_reg_write(usid_user,8'h30,8'h00," + tri_reg[0] + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h30,8'h00," + tri_reg[0] + ");" + code_style)
    file.write("$display(\"****select reg"+reg_format_udr+" trigger is " + tri_mask + "****\");" + code_style)
    if reg_value[1] in ['3:0', '3：0']:
        file.write("ext_reg_write(usid_user,8'h"+reg_format_udr+",8'h00,{4'b0000," + ext_udr_mapped[tri_mask] + "});" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h"+reg_format_udr+",8'h00,{4'b0000," + ext_udr_mapped[tri_mask] + "});" + code_style)
    elif reg_value[1] in ['7:4', '7：4']:
        file.write("ext_reg_write(usid_user,8'h"+reg_format_udr+",8'h00,{" + ext_udr_mapped[tri_mask] + ",4'b0000});" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h"+reg_format_udr+",8'h00,{" + ext_udr_mapped[tri_mask] + ",4'b0000});" + code_style)
    file.write("// reg" + reg_format_user + code_style)
    file.write("$display(\"****reg"+reg_format_user+" ext_trigger test****\");" + code_style)
    file.write("packet_rand = new(" + str(generate_random_integer()) + ");" + code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "packet_rand.randomize();" + code_style)
    file.write(first_style + "data = packet_rand.data_packet;" + code_style)
    file.write(first_style + "ext_reg_write(usid_user,8'h"+reg_format_user+",8'h00,data);" + code_style)
    file.write(first_style + "if(i==0) begin" + code_style)
    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h"+reg_format_user+",8'h00,{1'b0,9'h000});"+code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h"+reg_format_user+",8'h00,{1'b0,data_pre});"+code_style)
    file.write(first_style + "end" + code_style) 
    display_start_fun(file, "write time cnt reg")
    for tri_name, cnt_reg in timed_tri_mapped.items():
        if tri_name == tri_mask:
            write_cnt_number = random.randint(0, 255) 
            timed_trigger_cnt(file, cnt_reg.replace("8'h", ""), write_cnt_number)
    file.write(first_style + "// read " + reg_format_user + code_style)
    file.write(first_style + "ext_reg_read_chk(usid_user,8'h"+reg_format_user+",8'h00,data);" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style) 
    split_line(file, " end:" + tri_mask +" ")
    file.write("\n" + code_style) 


def sim_reg1c_reg(file, usid_user, each_reg):
    reg_format = each_reg.split("x")[1]
    display_reg(file, each_reg)

    file.write("for(data=8'h00;data<=8'hff;data=data+1) begin" + code_style)
    file.write("    reg_write(" + usid_user + ",8'h" + reg_format + ",data&8'b1011_1111);" + code_style)
    file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data&8'b1011_1000});" + code_style)
    file.write("end" + code_style)


def sim_reg1d_reg1e_reg1f_reg(file, usid_user, each_reg):
    reg_format = each_reg.split("x")[1]
    display_reg(file, each_reg)
    result_reg_dict = write_other_reg(file, '0x1d', all_user_dicr, extended_command)
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    reg_write(" + usid_user + ",8'h" + reg_format + ",data);" + code_style)
    if each_reg.lower() == "0x1d":
        file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,product_id_user});" + code_style)
    if each_reg.lower() == "0x1e":
        file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,man_id_user[8:0]});" + code_style)
    if each_reg.lower() == "0x1f":
        file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,man_id_user[11:8], usid_user});" + code_style)
    read_other_reg(file, result_reg_dict, extended_command, "")
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)


def sim_reg20_to_reg30_reg(file, usid_user, each_reg):
    reg_format = each_reg.split("x")[1]
    display_reg(file, each_reg)
    result_reg_dict = write_other_reg(file, '0x1d', all_user_dicr, extended_command)
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    ext_reg_write(" + usid_user + ",8'h" + reg_format + ",8'h00,data);" + code_style)
    if each_reg.lower() == '0x20':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,ext_product_id_user});" + code_style)
    if each_reg.lower() == '0x21':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,revision_id_user});" + code_style)
    if each_reg.lower() == '0x22':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data});" + code_style)
    if each_reg.lower() == '0x23':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h00});" + code_style)
    if each_reg.lower() == '0x24':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h00});" + code_style)
    if each_reg.lower() == '0x2b':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data&8'h0f});" + code_style)
    if each_reg.lower() == '0x2c':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'hd2});" + code_style)
    if each_reg.lower() == '0x2d':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data});" + code_style)
    if each_reg.lower() == '0x2e':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h00});" + code_style)
    if each_reg.lower() == '0x2f':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h00});" + code_style)
    if each_reg.lower() == '0x30':
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data});" + code_style)
    if each_reg.lower() != '0x23':
        read_other_reg(file, result_reg_dict, extended_command, "")
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)

def sim_reg31_to_reg3f(file, usid_user, time_reg_list):
    for each_reg in time_reg_list:
        reg_format = each_reg.split("x")[1]
        result_reg_dict = write_other_reg(file, '0x1d', all_user_dicr, extended_command)
        display_reg(file, each_reg)
        file.write("begin"+code_style)
        file.write(first_style +"ext_reg_write(usid_user,8'h"+reg_format+",8'h00,8'ha0);"+code_style)
        file.write(first_style +"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h95});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h84});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h74});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h63});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h53});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h42});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h32});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h21});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h11});" + code_style)
        file.write(first_style+"ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h00});" + code_style)
        file.write("end" + code_style)
        read_other_reg(file, result_reg_dict, extended_command, "")



def sim_error_test():
    with open("sim_error_test.v", 'w', encoding='utf-8') as sim_err:
        sim_err.write("task sim_error_test;\n")
        display_start_fun(sim_err, "error_test(sum_err)")
        trigger_disable(sim_err, reg_dicr)
        first_data = list(all_user_dicr.items())[0]
        first_reg = first_data[0].split("x")[1]
        sim_err.write("\n")
        display_start_fun(sim_err, "command frame with parity error")
        sim_err.write("$display(\"****reg_write_cmd_parity_err****\");" + code_style)
        sim_err.write("reg_write(usid_user,8'h"+first_reg+",8'h55);" + code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h055);" + code_style)
        sim_err.write("reg_write_cmd_parity_err(usid_user,8'h"+first_reg+",8'h66);"+code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h055);" + code_style)
        sim_err.write("reg_write(usid_user,8'h"+first_reg+",8'h66);" + code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h066);" + code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00100_0000);"+code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if extended_command == 'support':
            sim_err.write("$display(\"****ext_reg_write_cmd_parity_err****\");" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write_cmd_parity_err(usid_user,8'h"+first_reg+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00100_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if len(all_mask_reg) != 0:
            foramt_mask = (all_mask_reg[0]).split("x")[1]
            sim_err.write("$display(\"****masked_write_cmd_parity_err****\");" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write_cmd_parity_err(usid_user,8'h"+foramt_mask+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00100_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        sim_err.write("\n")
        display_start_fun(sim_err, "command frame with length error")
        if '0x00' in all_user_dicr:
            sim_err.write("$display(\"****reg0_write_len_parity_err****\");" + code_style)
            sim_err.write("reg0_write(usid_user,8'h55);" + code_style)
            sim_err.write("reg_read_chk(usid_user,8'h00,9'h055);" + code_style)
            sim_err.write("reg0_write_cmd_len_err(usid_user,8'h66);"+code_style)
            sim_err.write("reg_read_chk(usid_user,8'h00,9'h055);" + code_style)
            sim_err.write("reg0_write(usid_user,8'h66);" + code_style)
            sim_err.write("reg_read_chk(usid_user,8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00010_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        sim_err.write("$display(\"****reg_write_len_parity_err****\");" + code_style)
        sim_err.write("reg_write(usid_user,8'h"+first_reg+",8'h55);" + code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h055);" + code_style)
        sim_err.write("reg_write_cmd_len_err(usid_user,8'h"+first_reg+",8'h66);"+code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h055);" + code_style)
        sim_err.write("reg_write(usid_user,8'h"+first_reg+",8'h66);" + code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h066);" + code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00010_0000);"+code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if extended_command == 'support':
            sim_err.write("$display(\"****ext_reg_write_len_parity_err****\");" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write_cmd_len_err(usid_user,8'h"+first_reg+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00010_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if len(all_mask_reg) != 0:
            foramt_mask = (all_mask_reg[0]).split("x")[1]
            sim_err.write("$display(\"****masked_write_len_parity_err****\");" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write_cmd_len_err(usid_user,8'h"+foramt_mask+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00010_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        
        sim_err.write("\n")
        display_start_fun(sim_err, "addr frame with parity error")
        if extended_command == 'support':
            sim_err.write("$display(\"****ext_reg_write_len_parity_err****\");" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write_addrl_parity_err(usid_user,8'h"+first_reg+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00001_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if len(all_mask_reg) != 0:
            foramt_mask = (all_mask_reg[0]).split("x")[1]
            sim_err.write("$display(\"****masked_write_len_parity_err****\");" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write_addrl_parity_err(usid_user,8'h"+foramt_mask+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00001_0000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        sim_err.write("\n")
        display_start_fun(sim_err, "data frame with parity error")
        sim_err.write("$display(\"****reg_write_len_parity_err****\");" + code_style)
        sim_err.write("reg_write(usid_user,8'h"+first_reg+",8'h55);" + code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h055);" + code_style)
        sim_err.write("reg_write_data_parity_err(usid_user,8'h"+first_reg+",8'h66);"+code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h055);" + code_style)
        sim_err.write("reg_write(usid_user,8'h"+first_reg+",8'h66);" + code_style)
        sim_err.write("reg_read_chk(usid_user,8'h"+first_reg+",9'h066);" + code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_1000);"+code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if extended_command == 'support':
            sim_err.write("$display(\"****ext_reg_write_len_parity_err****\");" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write_data_parity_err(usid_user,8'h"+first_reg+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h055);" + code_style)
            sim_err.write("ext_reg_write(usid_user,8'h"+first_reg+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+first_reg+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_1000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        if len(all_mask_reg) != 0:
            foramt_mask = (all_mask_reg[0]).split("x")[1]
            sim_err.write("$display(\"****masked_write_len_parity_err****\");" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h55);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write_mdata_parity_err(usid_user,8'h"+foramt_mask+",8'h00,8'h66);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h055);" + code_style)
            sim_err.write("masked_write(usid_user,8'h"+foramt_mask+",8'h00,8'h66);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,8'h"+foramt_mask+",8'h00,9'h066);" + code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_1000);"+code_style)
            sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)     
        sim_err.write("\n")
        display_start_fun(sim_err, "read using the  bsid or gsid")
        sim_err.write("$display(\"****reg_read use the bsid error****\");" + code_style)
        sim_err.write("reg_read_chk(4'h0,8'h1c,`NRF);" + code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0001);"+code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        reg_reset_command(sim_err)
        sim_err.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_error_test.v")
    shutil.move("sim_error_test.v", os.path.join("sim_case_list", "sim_error_test.v"))
        

def sim_reg_write_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_reg_write_trigger_disable.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_reg_write_trigger_disable;\n")
        display_start_fun(sim_reg, "reg_write_command_no_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_reg, value_reg in all_user_reg.items():
            reg_format = key_reg.split("x")[1]
            decimal_number = int(reg_format, 16)
            if decimal_number <= 31:
                result_reg_dict = write_other_reg(sim_reg, key_reg, all_user_reg, ext_com_support)
                display_reg(sim_reg, key_reg)
                reg_command_loop_body(sim_reg, "usid_user", key_reg, result_reg_dict, ext_com_support)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_reg_write_trigger_disable.v")
    shutil.move("sim_reg_write_trigger_disable.v", os.path.join("sim_case_list", "sim_reg_write_trigger_disable.v"))


def sim_ext_write_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_ext_write_trigger_disable.v", 'w', encoding='utf-8') as sim_ext:
        write_data_begin(sim_ext)
        sim_ext.write("task sim_ext_write_trigger_disable;\n")
        display_start_fun(sim_ext, "ext_write_command_no_trigger")
        trigger_disable(sim_ext, all_reg)
        for key_reg, value_reg in all_user_reg.items():
            reg_format = key_reg.split("x")[1]
            decimal_number = int(reg_format, 16)
            result_reg_dict = write_other_reg(sim_ext, key_reg, all_user_reg, ext_com_support)
            display_reg(sim_ext, key_reg)
            ext_command_loop_body(sim_ext, "usid_user", key_reg, result_reg_dict, ext_com_support)
        reg_reset_command(sim_ext)
        sim_ext.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_write_trigger_disable.v")
    shutil.move("sim_ext_write_trigger_disable.v", os.path.join("sim_case_list", "sim_ext_write_trigger_disable.v"))


def sim_ext_write_long_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_ext_write_long_trigger_disable.v", 'w', encoding='utf-8') as sim_long:
        write_data_begin(sim_long)
        sim_long.write("task sim_ext_write_long_trigger_disable;\n")
        display_start_fun(sim_long, "ext_long_command_no_trigger")
        trigger_disable(sim_long, all_reg)
        for key_reg, value_reg in all_user_reg.items():
            reg_format = key_reg.split("x")[1]
            decimal_number = int(reg_format, 16)
            result_reg_dict = write_other_reg(sim_long, key_reg, all_user_reg, ext_com_support)
            display_reg(sim_long, key_reg)
            ext_long_command_loop_body(sim_long, "usid_user", key_reg, result_reg_dict, ext_com_support)
        reg_reset_command(sim_long)
        sim_long.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_write_long_trigger_disable.v")
    shutil.move("sim_ext_write_long_trigger_disable.v", os.path.join(
        "sim_case_list", "sim_ext_write_long_trigger_disable.v"))


def sim_masked_write_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_masked_write_no_trigger.v", 'w', encoding='utf-8') as sim_masked:
        write_data_begin(sim_masked)
        sim_masked.write("task sim_masked_write_no_trigger;\n")
        display_start_fun(sim_masked, "masked_write_command_no_trigger")
        trigger_disable(sim_masked, all_reg)
        for key_masked, value_masked in all_user_reg.items():
            if "M" in value_masked[0][7] or "m" in value_masked[0][7]:
                result_reg_dict = write_other_reg(sim_masked, key_masked, all_user_reg, ext_com_support)
                display_reg(sim_masked, key_masked)
                masked_write_command_loop_body(sim_masked, "usid_user", key_masked, result_reg_dict, ext_com_support)
        reg_reset_command(sim_masked)
        sim_masked.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_masked_write_no_trigger.v")
    shutil.move("sim_masked_write_no_trigger.v", os.path.join(
        "sim_case_list", "sim_masked_write_no_trigger.v"))


def sim_reg0_write_sta_trigger(all_user, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_reg0_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg0:
        write_data_begin(sim_reg0)
        sim_reg0.write("task sim_reg0_write_sta_trigger;\n")
        display_start_fun(sim_reg0, "sim_reg0_write_sta_trigger")
        trigger_disable(sim_reg0, all_user)
        trigger_list = []
        for key_trigger, value_trigger in sta_trigger.items():
            if key_trigger == '0x00' and "trigger_0" in value_trigger[0][6].lower():
                trigger_list.append(trigger_0_mask)
                trigger_list.append(trigger_0_reg)
                result_reg_dict = write_other_reg(sim_reg0, '0x00', all_user_reg, ext_comm_support)
                write_spec_data(sim_reg0, "0x00", 4)
                reg0_command_trigger_loop_body(sim_reg0, "usid_user", result_reg_dict, ext_comm_support, trigger_list)
            elif key_trigger == '0x00' and "trigger_1" in value_trigger[0][6].lower():
                trigger_list.append(trigger_1_mask)
                trigger_list.append(trigger_1_reg)
                result_reg_dict = write_other_reg(sim_reg0, '0x00', all_user_reg, ext_comm_support)
                write_spec_data(sim_reg0, "0x00", 4)
                reg0_command_trigger_loop_body(sim_reg0, "usid_user", result_reg_dict, ext_comm_support, trigger_list)
            elif key_trigger == '0x00' and "trigger_2" in value_trigger[0][6].lower():
                trigger_list.append(trigger_2_mask)
                trigger_list.append(trigger_2_reg)
                result_reg_dict = write_other_reg(sim_reg0, '0x00', all_user_reg, ext_comm_support)
                write_spec_data(sim_reg0, "0x00", 4)
                reg0_command_trigger_loop_body(sim_reg0, "usid_user", result_reg_dict, ext_comm_support, trigger_list)
        reg_reset_command(sim_reg0)
        sim_reg0.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_reg0_write_sta_trigger.v")
    shutil.move("sim_reg0_write_sta_trigger.v", os.path.join("sim_case_list", "sim_reg0_write_sta_trigger.v"))


def sim_reg_write_sta_trigger(all_reg, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_reg_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_reg_write_sta_trigger;\n")
        display_start_fun(sim_reg, "sim_reg_write_sta_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_trigger, value_trigger in sta_trigger.items():
            trigger_all = ["trigger_0", "trigger_1", "trigger_2"]
            reg_format = key_trigger.split("x")[1]
            decimal_number = int(reg_format, 16)
            if decimal_number <= 31:
                if "sta_all" in str(value_trigger[0][8]).lower():
                    for each_item in trigger_all:
                        if each_item == "trigger_0":
                            trigger_list = []
                            trigger_list.append(trigger_0_mask)
                            trigger_list.append(trigger_0_reg)
                            result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                            reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
                        if each_item == "trigger_1":
                            trigger_list = []
                            trigger_list.append(trigger_1_mask)
                            trigger_list.append(trigger_1_reg)
                            result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                            reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
                        if each_item == "trigger_2":
                            trigger_list = []
                            trigger_list.append(trigger_2_mask)
                            trigger_list.append(trigger_2_reg)
                            result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                            reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
                elif "sta_all" not in str(value_trigger[0][8]).lower():
                    if "trigger_0" in value_trigger[0][6].lower():
                        trigger_list = []
                        trigger_list.append(trigger_0_mask)
                        trigger_list.append(trigger_0_reg)
                        result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                        reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
                    elif "trigger_1" in value_trigger[0][6].lower():
                        trigger_list = []
                        trigger_list.append(trigger_1_mask)
                        trigger_list.append(trigger_1_reg)
                        result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                        reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
                    elif "trigger_2" in value_trigger[0][6].lower():
                        trigger_list = []
                        trigger_list.append(trigger_2_mask)
                        trigger_list.append(trigger_2_reg)
                        result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                        reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_reg_write_sta_trigger.v")
    shutil.move("sim_reg_write_sta_trigger.v", os.path.join("sim_case_list", "sim_reg_write_sta_trigger.v"))


def sim_ext_write_sta_trigger(all_reg, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_ext_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_ext_write_sta_trigger;\n")
        display_start_fun(sim_reg, "sim_ext_write_sta_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_trigger, value_trigger in sta_trigger.items():
            trigger_list = []
            if "trigger_0" in value_trigger[0][6].lower():
                trigger_list.append(trigger_0_mask)
                trigger_list.append(trigger_0_reg)
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_list)
            elif "trigger_1" in value_trigger[0][6].lower():
                trigger_list.append(trigger_1_mask)
                trigger_list.append(trigger_1_reg)
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_list)
            elif "trigger_2" in value_trigger[0][6].lower():
                trigger_list.append(trigger_2_mask)
                trigger_list.append(trigger_2_reg)
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_write_sta_trigger.v")
    shutil.move("sim_ext_write_sta_trigger.v", os.path.join("sim_case_list", "sim_ext_write_sta_trigger.v"))


def sim_ext_long_write_sta_trigger(all_reg, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_ext_long_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_ext_long_write_sta_trigger;\n")
        display_start_fun(sim_reg, "sim_ext_long_write_sta_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_trigger, value_trigger in sta_trigger.items():
            trigger_list = []
            if "trigger_0" in value_trigger[0][6].lower():
                trigger_list.append(trigger_0_mask)
                trigger_list.append(trigger_0_reg)
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_long_list)
            elif "trigger_1" in value_trigger[0][6].lower():
                trigger_list.append(trigger_1_mask)
                trigger_list.append(trigger_1_reg)
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_long_list)
            elif "trigger_2" in value_trigger[0][6].lower():
                trigger_list.append(trigger_2_mask)
                trigger_list.append(trigger_2_reg)
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_long_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_long_write_sta_trigger.v")
    shutil.move("sim_ext_long_write_sta_trigger.v", os.path.join("sim_case_list", "sim_ext_long_write_sta_trigger.v"))


def sim_masked_write_sta_trigger(all_reg, all_user_reg, all_mask_reg, ext_comm_support):
    with open("sim_masked_write_sta_trigger.v", 'w', encoding='utf-8') as sim_masked:
        write_data_begin(sim_masked)
        sim_masked.write("task sim_masked_write_sta_trigger;\n")
        display_start_fun(sim_masked, "sim_masked_write_sta_trigger")
        trigger_disable(sim_masked, all_reg)
        for key_masked, value_masked in all_mask_reg.items():
            trigger_list = []
            if "trigger_0" in value_masked[0][6].lower():
                trigger_list.append(trigger_0_mask)
                trigger_list.append(trigger_0_reg)
                result_reg_dict = write_other_reg(sim_masked, key_masked, all_user_reg, ext_comm_support)
                masked_write_command_trigger_loop_body(sim_masked, "usid_user", key_masked, result_reg_dict, ext_comm_support, trigger_list)
            elif "trigger_1" in value_masked[0][6].lower():
                trigger_list.append(trigger_1_mask)
                trigger_list.append(trigger_1_reg)
                result_reg_dict = write_other_reg(sim_masked, key_masked, all_user_reg, ext_comm_support)
                masked_write_command_trigger_loop_body(sim_masked, "usid_user", key_masked, result_reg_dict, ext_comm_support, trigger_list)
            elif "trigger_2" in value_masked[0][6].lower():
                trigger_list.append(trigger_2_mask)
                trigger_list.append(trigger_2_reg)
                result_reg_dict = write_other_reg(sim_masked, key_masked, all_user_reg, ext_comm_support)
                masked_write_command_trigger_loop_body(sim_masked, "usid_user", key_masked, result_reg_dict, ext_comm_support, trigger_list)
        reg_reset_command(sim_masked)
        sim_masked.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_masked_write_sta_trigger.v")
    shutil.move("sim_masked_write_sta_trigger.v", os.path.join(
        "sim_case_list", "sim_masked_write_sta_trigger.v"))


def sim_ext_extended_trigger(all_reg, all_user_reg, udr_reg, ext_comm_support):
    with open("sim_ext_extended_trigger.v", 'w', encoding='utf-8') as sim_tri:
        write_data_begin(sim_tri)
        sim_tri.write("task sim_ext_extended_trigger;\n")
        display_start_fun(sim_tri, "sim_ext_extended_trigger")     
        for reg_key, reg_value in udr_reg.items():
            reg_format_user = reg_key.split("x")[1]
            reg_format_udr = reg_value[0].split("x")[1]
            if "3_10" in reg_value[3]:
                display_ext_reg(sim_tri, reg_key, reg_value[2])
                for tri_mask, tri_reg in ext_trigger_3_10.items(): 
                    extended_trigger_loop_body(sim_tri, "usid_user",tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user)  
            if "3_17" in reg_value[3]:
                display_ext_reg(sim_tri, reg_key, reg_value[2])
                for tri_mask, tri_reg in ext_trigger_3_17.items(): 
                    extended_trigger_loop_body(sim_tri, "usid_user",tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user)
        reg_reset_command(sim_tri)
        sim_tri.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_extended_trigger.v")
    shutil.move("sim_ext_extended_trigger.v", os.path.join(
        "sim_case_list", "sim_ext_extended_trigger.v"))

def sim_extended_timed_trigger():
    with open("sim_extended_timeed_trigger.v", 'w', encoding='utf-8') as sim_time:
        write_data_begin(sim_time)
        sim_time.write("task sim_extended_timeed_trigger;\n")
        display_start_fun(sim_time, "sim_extended_timeed_trigger")
        for reg_key, reg_value in udr_trigger.items():
            reg_format_user = reg_key.split("x")[1]
            reg_format_udr = reg_value[0].split("x")[1]
            if "3_10" in reg_value[3]:
                display_ext_reg(sim_time, reg_key, reg_value[2])
                for tri_mask, tri_reg in ext_trigger_3_10.items(): 
                    extended_timed_trigger_loop_body(sim_time, "usid_user",tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user)  
            if "3_17" in reg_value[3]:
                display_ext_reg(sim_time, reg_key, reg_value[2])
                for tri_mask, tri_reg in ext_trigger_3_17.items(): 
                    extended_timed_trigger_loop_body(sim_time, "usid_user",tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user)
        reg_reset_command(sim_time)
        sim_time.write("\n" + "endtask" + "\n")
    shutil.move("sim_extended_timeed_trigger.v", os.path.join(
        "sim_case_list", "sim_extended_timeed_trigger.v"))


def sim_mipi_reserved_reg(mipi_res_reg):
    time_block_b = ["0x31", "0x32", "0x33", "0x34", "0x35", "0x36", "0x37"]   # trigger11-17
    time_block_a = ["0x38", "0x39", "0x3a", "0x3b", "0x3c", "0x3d", "0x3e", "0x3f"]   # trigger3-10
    with open("sim_mipi_reserved_reg.v", 'w', encoding='utf-8') as sim_mipi:
        write_data_begin(sim_mipi)
        sim_mipi.write("task sim_mipi_reserved_reg;\n")
        display_start_fun(sim_mipi, "sim_mipi_reserved_reg")
        for key_mipi, value_mipi in mipi_reserved_reg.items():
            if key_mipi.lower() == '0x1c':
                sim_reg1c_reg(sim_mipi, "usid_user", "0x1c")
            if key_mipi.lower() == '0x1d':
                sim_reg1d_reg1e_reg1f_reg(sim_mipi, "usid_user", "0x1d")
            if key_mipi.lower() == '0x1e':
                sim_reg1d_reg1e_reg1f_reg(sim_mipi, "usid_user", "0x1e")
            if key_mipi.lower() == '0x1f':
                sim_reg1d_reg1e_reg1f_reg(sim_mipi, "usid_user", "0x1f")
            if key_mipi.lower() == '0x20':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x20")
            if key_mipi.lower() == '0x21':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x21")
            if key_mipi.lower() == '0x22':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x22")
            if key_mipi.lower() == '0x23':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x23")
            if key_mipi.lower() == '0x24':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x24")
            if key_mipi.lower() == '0x2b':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x2b")
            if key_mipi.lower() == '0x2c':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x2c")
            if key_mipi.lower() == '0x2d':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x2d")
            if key_mipi.lower() == '0x2e':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x2e")
            if key_mipi.lower() == '0x2f':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x2f")
            if key_mipi.lower() == '0x30':
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", "0x30")
            if key_mipi.lower() == '0x31':
                sim_reg31_to_reg3f(sim_mipi, "usid_user", time_block_b)
            if key_mipi.lower() == '0x38':
                sim_reg31_to_reg3f(sim_mipi, "usid_user", time_block_a)
        reg_reset_command(sim_mipi)
        sim_mipi.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_mipi_reserved_reg.v")
    shutil.move("sim_mipi_reserved_reg.v", os.path.join(
        "sim_case_list", "sim_mipi_reserved_reg.v"))


def sim_write_with_bsid():
    with open("sim_write_with_bsid.v", 'w', encoding='utf-8') as sim_bsid:
        write_data_begin(sim_bsid)
        sim_bsid.write("task sim_write_with_bsid;\n")
        display_start_fun(sim_bsid, "sim_write_with_bsid")
        trigger_disable(sim_bsid, reg_dicr)
        for key_bsid in all_bsid_reg:
            reg_format = key_bsid.split("x")[1]
            decimal_number = int(reg_format, 16)
            if decimal_number <= 31:
                result_reg_dict = write_other_reg(sim_bsid, key_bsid, all_user_dicr, extended_command)
                reg_command_loop_body(sim_bsid, "4'h0", key_bsid, result_reg_dict, extended_command)
            else:
                result_reg_dict = write_other_reg(sim_bsid, key_bsid, all_user_dicr, extended_command)
                ext_command_loop_body(sim_bsid, "4'h0", key_bsid, result_reg_dict, extended_command)
        reg_reset_command(sim_bsid)
        sim_bsid.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_write_with_bsid.v")
    shutil.move("sim_write_with_bsid.v", os.path.join(
        "sim_case_list", "sim_write_with_bsid.v"))
    

def sim_write_with_gsid():
    with open("sim_write_with_gsid.v", 'w', encoding='utf-8') as sim_gsid:
        write_data_begin(sim_gsid)
        sim_gsid.write("task sim_write_with_gsid;\n")
        display_start_fun(sim_gsid, "sim_write_with_gsid")
        trigger_disable(sim_gsid, reg_dicr)
        for key_bsid in all_bsid_reg:
            reg_format = key_bsid.split("x")[1]
            decimal_number = int(reg_format, 16)
            if decimal_number <= 31:
                result_reg_dict = write_other_reg(sim_gsid, key_bsid, all_user_dicr, extended_command)
                write_hex_number_gsid = generate_hex_random()
                sim_gsid.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
                sim_gsid.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
                gsid_list = {}
                gsid0_get = write_hex_number_gsid.replace("8'h", "")[0]
                gsid_list["gsid0"] = gsid0_get
                gsid1_get = write_hex_number_gsid.replace("8'h", "")[1]
                gsid_list["gsid1"] = gsid1_get
                for gsid_name, item_gsid in gsid_list.items():  
                    sim_gsid.write("// use " + gsid_name + " write "+ key_bsid + code_style)
                    reg_command_loop_body(sim_gsid, "4'h"+item_gsid, key_bsid, result_reg_dict, extended_command)
            else:
                result_reg_dict = write_other_reg(sim_gsid, key_bsid, all_user_dicr, extended_command)
                write_hex_number_gsid = generate_hex_random()
                sim_gsid.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
                sim_gsid.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
                gsid_list = {}
                gsid0_get = write_hex_number_gsid.replace("8'h", "")[0]
                gsid_list["gsid0"] = gsid0_get
                gsid1_get = write_hex_number_gsid.replace("8'h", "")[1]
                gsid_list["gsid1"] = gsid1_get
                for gsid_name, item_gsid in gsid_list.items(): 
                    sim_gsid.write("// use " + gsid_name + " write "+ key_bsid + code_style)
                    ext_command_loop_body(sim_gsid, "4'h"+item_gsid, key_bsid, result_reg_dict, extended_command)
        reg_reset_command(sim_gsid)
        sim_gsid.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_write_with_gsid.v")
    shutil.move("sim_write_with_gsid.v", os.path.join(
        "sim_case_list", "sim_write_with_gsid.v"))
    

def sim_trigger_with_bsid():
    with open("sim_trigger_with_bsid.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_trigger_with_bsid;\n")
        display_start_fun(sim_reg, "sim_trigger_with_bsid")
        trigger_disable(sim_reg, reg_dicr)
        for key_trigger, value_trigger in sta_trigger_reg.items():
            trigger_list = []
            reg_format = key_trigger.split("x")[1]
            decimal_number = int(reg_format, 16)
            if decimal_number <= 31:
                if "trigger_0" in value_trigger[0][6].lower():
                    trigger_list.append(trigger_0_mask)
                    trigger_list.append(trigger_0_reg)
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
                    reg_command_trigger_loop_body(sim_reg, "4'h0", key_trigger, result_reg_dict, extended_command, trigger_list)
                elif "trigger_1" in value_trigger[0][6].lower():
                    trigger_list.append(trigger_1_mask)
                    trigger_list.append(trigger_1_reg)
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
                    reg_command_trigger_loop_body(sim_reg, "4'h0", key_trigger, result_reg_dict, extended_command, trigger_list)
                elif "trigger_2" in value_trigger[0][6].lower():
                    trigger_list.append(trigger_2_mask)
                    trigger_list.append(trigger_2_reg)
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
                    reg_command_trigger_loop_body(sim_reg, "4'h0", key_trigger, result_reg_dict, extended_command, trigger_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_trigger_with_bsid.v")
    shutil.move("sim_trigger_with_bsid.v", os.path.join("sim_case_list", "sim_trigger_with_bsid.v"))

def sim_trigger_with_gsid():
    with open("sim_trigger_with_gsid.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_trigger_with_gsid;\n")
        display_start_fun(sim_reg, "sim_trigger_with_gsid")
        trigger_disable(sim_reg, reg_dicr)
        for key_trigger, value_trigger in sta_trigger_reg.items():
            trigger_list = []
            reg_format = key_trigger.split("x")[1]
            decimal_number = int(reg_format, 16)
            if decimal_number <= 31:
                if "trigger_0" in value_trigger[0][6].lower():
                    trigger_list.append(trigger_0_mask)
                    trigger_list.append(trigger_0_reg)
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
                    write_hex_number_gsid = generate_hex_random()
                    sim_reg.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
                    sim_reg.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
                    gsid_list = {}
                    gsid0_get = write_hex_number_gsid.replace("8'h", "")[0]
                    gsid_list["gsid0"] = gsid0_get
                    gsid1_get = write_hex_number_gsid.replace("8'h", "")[1]
                    gsid_list["gsid1"] = gsid1_get
                     # 随机选择一个gsid  
                    sim_reg.write("// use gsid write "+ key_trigger + code_style)
                    item_gsid = random.choice(list(gsid_list.values()))
                    reg_command_trigger_loop_body(sim_reg, "4'h" + item_gsid, key_trigger, result_reg_dict, extended_command, trigger_list)
                elif "trigger_1" in value_trigger[0][6].lower():
                    trigger_list.append(trigger_1_mask)
                    trigger_list.append(trigger_1_reg)
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
                    write_hex_number_gsid = generate_hex_random()
                    sim_reg.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
                    sim_reg.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
                    gsid_list = {}
                    gsid0_get = write_hex_number_gsid.replace("8'h", "")[0]
                    gsid_list["gsid0"] = gsid0_get
                    gsid1_get = write_hex_number_gsid.replace("8'h", "")[1]
                    gsid_list["gsid1"] = gsid1_get
                     # 随机选择一个gsid  
                    sim_reg.write("// use gsid write "+ key_trigger + code_style)
                    item_gsid = random.choice(list(gsid_list.values()))
                    reg_command_trigger_loop_body(sim_reg, "4'h" + item_gsid, key_trigger, result_reg_dict, extended_command, trigger_list)
                elif "trigger_2" in value_trigger[0][6].lower():
                    trigger_list.append(trigger_2_mask)
                    trigger_list.append(trigger_2_reg)
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
                    write_hex_number_gsid = generate_hex_random()
                    sim_reg.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
                    sim_reg.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
                    gsid_list = {}
                    gsid0_get = write_hex_number_gsid.replace("8'h", "")[0]
                    gsid_list["gsid0"] = gsid0_get
                    gsid1_get = write_hex_number_gsid.replace("8'h", "")[1]
                    gsid_list["gsid1"] = gsid1_get
                     # 随机选择一个gsid  
                    sim_reg.write("// use gsid write "+ key_trigger + code_style)
                    item_gsid = random.choice(list(gsid_list.values()))
                    reg_command_trigger_loop_body(sim_reg, "4'h"+ item_gsid, key_trigger, result_reg_dict, extended_command, trigger_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_trigger_with_gsid.v")
    shutil.move("sim_trigger_with_gsid.v", os.path.join("sim_case_list", "sim_trigger_with_gsid.v"))


def sim_ext_write_more_reg_no_tri():  
    with open("sim_ext_write_more_reg_no_tri.v", 'w', encoding='utf-8') as sim_reg: 
        write_data_begin(sim_reg) 
        sim_reg.write("task sim_ext_write_more_reg_no_tri;\n")  
        display_start_fun(sim_reg, "sim_ext_write_more_reg_no_tri")  # 确保display_start_fun已定义  
        trigger_disable(sim_reg, reg_dicr)  # 确保reg_dicr和trigger_disable已定义  
        first_data = list(all_user_dicr.items())[0]  # 确保all_user_dicr已定义  
        first_reg = first_data[0].split("x")[1]  
        int_val = int(first_reg, 16)  
    
        for i in range(1, 16):  
            list_write_reg = []  
            write_data_list = generate_random_list(i+1)
            for j in range(i+1):  
                current_int = int_val + j  
                current_hex = format(current_int, '02x')  
                result_reg = "0x" + str(current_hex)  
                list_write_reg.append(result_reg)  
            # write_data = generate_hex_random()  # 确保generate_hex_random函数已定义  
            # write_data_list = [write_data for _ in range(i + 1)]  
            write_data_str = ",".join(write_data_list)  
    
            sim_reg.write("$display(\"/// write " + str(i + 1) + " registers ///\");\n     ")  
    
            write_values = []  
            for each in list_write_reg:  
                each_split = each.split("x")[1]
                each_new = "0x"+each_split.upper()
                if each in all_user_dicr or each_new in all_user_dicr:  
                    index_reg = list_write_reg.index(each)  
                    write_values.append(write_data_list[index_reg])  
                else:  
                    write_values.append("`NRF")  
    
            write_values_str = ",".join(write_values)  
    
            sim_reg.write("ext_reg_write(usid_user,8'h" + first_reg + ",8'h0" + str(hex(i))[2:] + ",{" + write_data_str + "});" + code_style) 
            sim_reg.write("ext_reg_read_chk(usid_user,8'h" + first_reg + ",8'h0" + str(hex(i))[2:] + ",{" + write_values_str.replace("8'h", "9'h0") + "});" + code_style)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_write_more_reg_no_tri.v")
    shutil.move("sim_ext_write_more_reg_no_tri.v", os.path.join("sim_case_list", "sim_ext_write_more_reg_no_tri.v"))
        


def sim_ext_write_more_reg_with_tri():  
    with open("sim_ext_write_more_reg_with_tri.v", 'w', encoding='utf-8') as sim_reg: 
        write_data_begin(sim_reg) 
        sim_reg.write("task sim_ext_write_more_reg_with_tri;\n")  
        display_start_fun(sim_reg, "sim_ext_write_more_reg_with_tri")  # 确保display_start_fun已定义  
        trigger_enable(sim_reg, reg_dicr)
        first_data = list(all_user_dicr.items())[0]  
        first_reg = first_data[0].split("x")[1]  
        int_val = int(first_reg, 16)  
        for i in range(1, 16):  
            list_write_reg = []  
            write_data_list = generate_random_list(i+1)
            for j in range(i+1):  
                current_int = int_val + j  
                current_hex = format(current_int, '02x')  
                result_reg = "0x" + str(current_hex)  
                list_write_reg.append(result_reg)  
            write_data_str = ",".join(write_data_list)  
    
            sim_reg.write("$display(\"/// write " + str(i + 1) + " registers ///\");\n     ")  
    
            write_values = []  
            for each in list_write_reg:  
                each_split = each.split("x")[1]
                each_new = "0x"+each_split.upper()
                if each in all_user_dicr or each_new in all_user_dicr:  
                    index_reg = list_write_reg.index(each)  
                    write_values.append(write_data_list[index_reg])  
                else:  
                    write_values.append("`NRF")  
    
            write_values_str = ",".join(write_values)  
            sim_reg.write("ext_reg_write(usid_user,8'h" + first_reg + ",8'h0" + str(hex(i))[2:] + ",{" + write_data_str + "});" + code_style)
            sim_reg.write("reg_write(usid_user,8'h1c,8'h87 );" + code_style) 
            if '0x2E' in mipi_reserved_reg or '0x2e' in mipi_reserved_reg:
                sim_reg.write("ext_reg_write(usid_user,8'h2e,8'h00,8'hff );" + code_style)
            if '0x2F' in mipi_reserved_reg or '0x2f' in mipi_reserved_reg:
                sim_reg.write("ext_reg_write(usid_user,8'h2f,8'h00,8'hff );" + code_style)  
            sim_reg.write("ext_reg_read_chk(usid_user,8'h" + first_reg + ",8'h0" + str(hex(i))[2:] + ",{" + write_values_str.replace("8'h", "9'h0") + "});" + code_style)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_ext_write_more_reg_with_tri.v")
    shutil.move("sim_ext_write_more_reg_with_tri.v", os.path.join("sim_case_list", "sim_ext_write_more_reg_with_tri.v"))
        



def sim_reg1c_reg23_reset():
    with open("sim_reg1c_reg23_reset.v", 'w', encoding='utf-8') as sim_reset:
        write_data_begin(sim_reset)
        sim_reset.write("task sim_reg1c_reg23_reset;\n")
        display_start_fun(sim_reset, "sim_reg1c_reset_user_define")
        trigger_disable(sim_reset, reg_dicr)
        if '0x1c' in reg_dicr or '0x1C' in reg_dicr:
            result_reg_dicr = write_other_reg(sim_reset, "0x1c", all_user_dicr, extended_command)
            read_other_reg(sim_reset, result_reg_dicr, extended_command, "")
            reg_reset_command(sim_reset)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "default value check ")
            for each_trigger, each_value in all_user_dicr.items():
                if each_trigger.lower() not in mipi_reserver_all_reg:
                    trigger_format = each_trigger.split("x")[1]
                    value_str = ''.join([val[4] for val in each_value])
                    write_reg_chk(sim_reset, trigger_format, value_str, extended_command)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "sim_reg1c_reset_mipi_reserved")
            sim_reset.write("reg_write(usid_user,8'h1c,8'hb8);"+code_style)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'hb8);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_write(usid_user,8'h22,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'haa);"+code_style)
            if '0x2b' in reg_dicr or '0x2B' in reg_dicr:
                sim_reset.write("ext_reg_write(usid_user,8'h2b,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h0a);"+code_style)
            reg_reset_command(sim_reset)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'h80);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'h00);"+code_style)
            if '0x2b' in reg_dicr or '0x2B' in reg_dicr:
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h04);"+code_style)
        if '0x23' in reg_dicr:
            sim_reset.write("\n")
            display_start_fun(sim_reset, "sim_reg23_reset_user_define")
            trigger_disable(sim_reset, reg_dicr)
            result_reg_dicr = write_other_reg(sim_reset, "0x23", all_user_dicr, extended_command)
            read_other_reg(sim_reset, result_reg_dicr, extended_command, "")
            sim_reset.write("// reset all_user_define;\n"+code_style)
            sim_reset.write("ext_reg_write(usid_user,8'h23,8'h00,8'h80);"+code_style)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "default value check ")
            for each_trigger, each_value in all_user_dicr.items():
                if each_trigger.lower() not in mipi_reserver_all_reg:
                    trigger_format = each_trigger.split("x")[1]
                    value_str = ''.join([val[4] for val in each_value])
                    write_reg_chk(sim_reset, trigger_format, value_str, extended_command)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "sim_reg23_reset_mipi_reserved")
            sim_reset.write("reg_write(usid_user,8'h1c,8'hb8);"+code_style)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'hb8);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_write(usid_user,8'h22,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'haa);"+code_style)
            if '0x2b' in reg_dicr or '0x2B' in reg_dicr:
                sim_reset.write("ext_reg_write(usid_user,8'h2b,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h0a);"+code_style)
            sim_reset.write("// reset all_mipi_reserved;\n"+code_style)
            sim_reset.write("ext_reg_write(usid_user,8'h23,8'h00,8'h80);"+code_style)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'hb8);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'haa);"+code_style)
            if '0x2b' in reg_dicr or '0x2B' in reg_dicr:
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h0a);"+code_style)  
        reg_reset_command(sim_reset)
        sim_reset.write("\n" + "endtask" + "\n")
    remove_empty_lines("sim_reg1c_reg23_reset.v")
    shutil.move("sim_reg1c_reg23_reset.v", os.path.join("sim_case_list", "sim_reg1c_reg23_reset.v"))
            


def display_start_fun(file, name):
    max_length = 37
    # 计算需要添加的空格数量
    if name == "write time cnt reg":
        padding = (max_length - len("// " + name + "  //")) // 2
        file.write("$display(\"//===============================//\");\n")
        file.write(first_style + " $display(\"// " + " " * padding + name + " " * padding + "//\");\n")
        file.write(first_style + " $display(\"//===============================//\");\n" + " "
                                                                            "    ")
    else:
        padding = (max_length - len("// " + name + "  //")) // 2
        file.write("$display(\"//===============================//\");\n")
        file.write("$display(\"// " + " " * padding + name + " " * padding + "//\");\n")
        file.write("$display(\"//===============================//\");\n" + " "
                                                                            "    ")

def display_reg(file, test_reg):
    reg_format = test_reg.replace("0x", "reg")
    file.write("$display(\"//*******************************//\");" + code_style)
    file.write("$display(\"//               " + reg_format + "           //\");" + code_style)
    file.write("$display(\"//*******************************//\");" + code_style)


def display_ext_reg(file, mt_reg, mt_type):
    reg_format = mt_reg.replace("0x", "reg")
    file.write("$display(\"//*******************************//\");" + code_style)
    file.write("$display(\"//           " + reg_format + ":"+mt_type+"          //\");" + code_style)
    file.write("$display(\"//*******************************//\");" + code_style)

def split_line(file, str):
     if "start" in str:
        file.write("$display(\"//============="+str+"=============//\");" + code_style)  
     else:
        file.write("$display(\"//=============="+str+"==============//\");" + code_style)


def remove_empty_lines(file_path):
    """
    Remove empty lines from a given file and save it back.

    Parameters:
    file_path (str): The path to the file to be processed.
    """
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()

        # 去除空行
    non_empty_lines = [line for line in lines if line.strip()]
    with open(file_path, 'w', encoding='utf-8') as file:
        file.writelines(non_empty_lines)


# 扩展trigger处理程序
def find_matching_udr_triggers(extended_trigger_reg, udr_set_reg, extended_command):  
    udr_trigger = {}  
    if extended_trigger_reg and extended_command == "support":  
        for key, value in extended_trigger_reg.items():  
            trigger_name = value[0][6]  
            each_letter = trigger_name.split("-")[1]  
            for udr_name, udr_value in udr_set_reg.items():  
                for item in udr_value:  
                    # 查找 'T' 的位置并存储结果，避免重复查找  \
                    udr_set_index = item[1].find('T')  
                    if udr_set_index != -1:  
                        after_udr_set = item[1][udr_set_index + 1:] 
                         # 提取 '_A_3_10' 中的 '3_10' 部分  
                        underscore_index = after_udr_set.find('_')  
                        if underscore_index != -1:  
                            # 分割字符串并取最后一部分  
                            parts = after_udr_set.split('_')  
                            if len(parts) > 1:  
                                last_part = '_'.join(parts[1:])  
                            else:  
                                last_part = after_udr_set  
                        else:  
                            last_part = after_udr_set
                        # 检查 each_letter 是否在 after_udr_set 中  
                        if each_letter in after_udr_set:  
                            udr_trigger[key] = [udr_name, item[0], value[0][6], last_part]  
    return udr_trigger  

'''
    Reserved Bit Read Test Algorithm:
    example:when bits[7], [5:3] of reg00 are reserved bits, write 0xFF results in:
            0xFF&8'b0100_0111 = 8'b1011_1000
            excel data example:
            =======================================
            Reister_Address   Data bits   Function  
                                [7]       Reserved
                0x00            [6]        reg00
                               [5:3]      Reserved
                               [2:0]       reg00
            =======================================
    This menas that if some bits in an 8-bit data are reserved,These bits, 
    even if you write valid data to them, will return 0 when read.
    Algorithm Design Idea:
    (1) Retrieve from an Excel sheet which bits of the registers have reserved bits and pass these reserved bits as parameters.
    (2) Set an initial string of 8 ones: "11111111". All bits are writable.Since a string does not have indexes, convert it to a list.
    (3) If the reserved bits are not continuous, such as [6], [3], then set the corresponding positions to 0 in the converted list based on the passed-in numbers.
    (4) If the reserved bits are continuous, such as [7:4], then perform a loop from 4 to 7, setting the corresponding positions to 0.
    (5) Finally, reverse the list. This is because the list index is opposite to the bit position.
    (6) Convert the list back to a string and return it.

'''
def generate_mask_strings(bit_range_lists):  
    read_and = "11111111"
    list_data = list(read_and)
    for each_reserved in bit_range_lists:
        if ":" not in each_reserved:
            list_data[int(each_reserved)] = '0'
        elif ":" in each_reserved:
            high_bit = int(each_reserved.split(":")[0]) + 1
            low_bit = int(each_reserved.split(":")[1])
            for index_change in range(low_bit, high_bit):
                list_data[index_change] = '0' 
    # 逆序列表  
    reversed_lst = list_data[::-1]  
    
    # 将逆序后的列表转换为一个字符串  
    reversed_str = ''.join(reversed_lst)  
    return "&8'b" + reversed_str


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python script.py register_file_path")
        sys.exit(1)
    register_file_path = sys.argv[1]

    # 创建文件夹
    folder_name = "sim_case_list"
    os.makedirs(folder_name, exist_ok=True)

    # 如果文件夹已经存在，删除该文件夹下所有的.v文件  
    for filename in os.listdir(folder_name):  
        if filename.endswith(".v"):  
            os.remove(os.path.join(folder_name, filename))
            
    # 缩进
    first_style = " " * 4
    second_style = " " * 10
    loop_style = " " * 7   #双重for循环第二层循环缩进
    # 代码换行和缩进
    code_style = '\n' + "     "

    # sta_trigger_mapped
    trigger_0_mask = "8'b1011_0000"
    trigger_1_mask = "8'b1010_1000"
    trigger_2_mask = "8'b1001_1000"
    trigger_0_reg = "8'b1011_0001"
    trigger_1_reg = "8'b1010_0010"
    trigger_2_reg = "8'b1001_1100"
    '''
         ext_trigger
         key:trigger_name 
         value:trigger    
    '''
    ext_trigger_3_10 = {
        "trigger_3" : ["8'b1111_1110", "8'b0000_0001"],
        "trigger_4" : ["8'b1111_1101", "8'b0000_0010"],
        "trigger_5" : ["8'b1111_1011", "8'b0000_0100"],
        "trigger_6" : ["8'b1111_0111", "8'b0000_1000"],
        "trigger_7" : ["8'b1110_1111", "8'b0001_0000"],
        "trigger_8" : ["8'b1101_1111", "8'b0010_0000"],
        "trigger_9" : ["8'b1011_1111", "8'b0100_0000"],
        "trigger_10": ["8'b0100_1111", "8'b1000_0000"]
    }

    ext_trigger_11_17 = {
        "trigger_11": ["8'b0111_1110", "8'b0000_0001"],
        "trigger_12": ["8'b0111_1101", "8'b0000_0010"],
        "trigger_13": ["8'b0111_1011", "8'b0000_0100"],
        "trigger_14": ["8'b0111_0111", "8'b0000_1000"],
        "trigger_15": ["8'b0110_1111", "8'b0001_0000"],
        "trigger_16": ["8'b0101_1111", "8'b0010_0000"],
        "trigger_17": ["8'b0011_1111", "8'b0100_0000"],
    }

    ext_trigger_3_17 = {**ext_trigger_3_10, **ext_trigger_11_17}

    # udr_rst_mapped
    ext_udr_mapped = {  
        "trigger_3": "4'b0000",  
        "trigger_4": "4'b0001",  
        "trigger_5": "4'b0010",  
        "trigger_6": "4'b0011",  
        "trigger_7": "4'b0100",  
        "trigger_8": "4'b0101",  
        "trigger_9": "4'b0110",  
        "trigger_10": "4'b0111",  
        "trigger_11": "4'b1000",  
        "trigger_12": "4'b1001",  
        "trigger_13": "4'b1010",  
        "trigger_14": "4'b1011",  
        "trigger_15": "4'b1100",  
        "trigger_16": "4'b1101",  
        "trigger_17": "4'b1110",  
    }

    # timed_trigger_mapped
    timed_tri_mapped = {
        "trigger_3": "8'h38",  
        "trigger_4": "8'h39",  
        "trigger_5": "8'h3a",  
        "trigger_6": "8'h3b",  
        "trigger_7": "8'h3c",  
        "trigger_8": "8'h3d",  
        "trigger_9": "8'h3e",  
        "trigger_10": "8'h3f",  
        "trigger_11": "8'h31",  
        "trigger_12": "8'h32",  
        "trigger_13": "8'h33",  
        "trigger_14": "8'h34",  
        "trigger_15": "8'h35",  
        "trigger_16": "8'h36",  
        "trigger_17": "8'h37", 
    }
    # command_list
    ext_list = ["ext_reg_write", "ext_reg_read_chk"]
    ext_long_list = ["ext_reg_write_long", "ext_reg_read_long_chk"]
    bsid_reg_sta_dict = {}
    gsid_reg_sta_dict = {}
    mask_reg_sta_dict = {}
    all_bsid_reg = []
    all_gsid_reg = []
    all_mask_reg = []

    # sim_file = open("sim_case.v", 'w', encoding='utf-8')
    # 调用get_excel_data函数并传入寄存器表格
    reg_dicr, command_dicr = get_excel_data(register_file_path)
    no_trigger_reg, sta_trigger_reg, extended_trigger_reg, mipi_reserved_reg, udr_set_reg = reg_data_process(reg_dicr)
    # all_user_reg_define
    all_user_dicr = {}
    for key, value in reg_dicr.items():
        if key.lower() not in mipi_reserver_all_reg:
            all_user_dicr[key] = value
    extended_command = ""
    extended_long_command = ""
    for each_command, command_value in command_dicr.items():
        if each_command == "ext_reg_write+ext_reg_read":
            extended_command = "support" if command_value == "YES" else "no_support"
        elif each_command == "ext_reg_write_long+ext_reg_read_long":
            extended_long_command = "support" if command_value == "YES" else "no_support"

    for key, value in all_user_dicr.items():
        if 'b' in value[0][7].lower():
            all_bsid_reg.append(key)
        if 'g' in value[0][7].lower():
            all_gsid_reg.append(key)
        if 'm' in value[0][7].lower():
            all_mask_reg.append(key)

    for key, value in all_user_dicr.items():
        if 'm' in value[0][7].lower() and "trigger" in value[0][6].lower():
            mask_reg_sta_dict[key] = value
        if 'b' in value[0][7].lower() and "trigger" in value[0][6].lower():
            bsid_reg_sta_dict[key] = value
        if 'g' in value[0][7].lower() and "trigger" in value[0][6].lower():
            gsid_reg_sta_dict[key] = value
        

    # 用户寄存器保留位处理
    reg_reserved_dicr = {}  
    for key, value in all_user_dicr.items():  
        if len(value) >= 2:  
            write_no_bit = []  
            for sublist in value:  
                if sublist[2].lower() == "reserved":  
                    write_no_bit.append(sublist[1])  
            if write_no_bit:  # 检查列表是否为空  
                reg_reserved_dicr[key] = write_no_bit

    reserved_len = len(reg_reserved_dicr)
    # 默认值检查case生成
    default_value_dict = {}
    check_mipi_default_value(reg_dicr, extended_command)
    # usid编程case生成
    usid_programmable_mode(mipi_reserved_reg, extended_command)
    # reg0_write指令验证case生成
    if '0x00' in reg_dicr:
        sim_reg0_write_command(reg_dicr, all_user_dicr, extended_command)

    # reg_write指令验证user_define寄存器：trigger_disable模式
    sim_reg_write_no_trigger(reg_dicr, all_user_dicr, extended_command)

    # ext_reg_write指令验证user_define寄存器：trigger_disable模式
    if extended_command == "support":
        sim_ext_write_no_trigger(reg_dicr, all_user_dicr, extended_command)

    # ext_reg_write_long指令验证user_define寄存器：trigger_disable模式
    if extended_long_command == "support":
        sim_ext_write_long_no_trigger(reg_dicr, all_user_dicr, extended_long_command)

    # masked_write指令验证user_deine寄存器：trigger_disable模式
    if len(all_mask_reg) != 0:
        sim_masked_write_no_trigger(reg_dicr, all_user_dicr, extended_command)

    # reg0_write指令测试reg00寄存器：trigger模式
    if '0x00' in sta_trigger_reg:
        sim_reg0_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command)
    
    # reg_write指令测试user_define寄存器：trigger模式
    sta_exists = len(sta_trigger_reg)
    if sta_exists != 0 :
        sim_reg_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command)
        sim_trigger_with_bsid()
        if '0x22' in reg_dicr:
            sim_trigger_with_gsid()

    
    # ext_reg_write指令测试user_define寄存器：trigger模式
    if sta_exists != 0 and extended_command == "support":
        sim_ext_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command) 

    # ext_reg_write_long指令测试user_define寄存器：trigger模式
    if sta_exists != 0 and extended_long_command == "support":
        sim_ext_long_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command) 

    # masked_write指令测试user_define寄存器：trigger模式
    mask_exists = len(mask_reg_sta_dict)
    if mask_exists != 0 :
        sim_masked_write_sta_trigger(reg_dicr, all_user_dicr, mask_reg_sta_dict, extended_command)
    

    # extended trigger测试 
    extended_trigger_exists = len(extended_trigger_reg)
    if extended_trigger_exists != 0:
        udr_trigger = find_matching_udr_triggers(extended_trigger_reg, udr_set_reg, extended_command)
        sim_ext_extended_trigger(reg_dicr, all_user_dicr, udr_trigger, extended_command)
        #定时触发器
        sim_extended_timed_trigger()

    # mipi保留寄存器测试
    sim_mipi_reserved_reg(mipi_reserved_reg)
    
    # bsid write reg
    if len(all_bsid_reg) != 0:
        sim_write_with_bsid()
    
    # gsid_write reg
    if len(all_gsid_reg) != 0 and '0x22' in reg_dicr:
        sim_write_with_gsid()

    # 复位测试
    sim_reg1c_reg23_reset()

    if '0x24' in reg_dicr:
        sim_error_test()

    if extended_command == "support":
        sim_ext_write_more_reg_no_tri()
        sim_ext_write_more_reg_with_tri()
    # 文件抽取
    # 定义要遍历的目录  
    '''
    sim_case_list_dir = 'sim_case_list'  
    
    # 使用with语句打开文件，确保文件正确关闭  
    with open("all_sim_file.v", 'w', encoding='utf-8') as outfile:  
        outfile.write("task sim_all_function;" + '\n')
        # 遍历目录  
        for root, dirs, files in os.walk(sim_case_list_dir):  
            for file in files:  
                # 检查文件扩展名是否为.v  
                if file.endswith('.v'):  
                    # 构造完整的文件路径  
                    file_path = os.path.join(root, file)  
                    # 打开并读取文件  
                    with open(file_path, 'r') as infile:  
                        # 遍历文件的每一行  
                        for line in infile:  
                            # 检查行是否以'task'开头  
                            if line.startswith('task'):  
                                # 使用split()分割字符串，并取第二部分（任务名）  
                                task_name = line.split(' ', 1)[1].strip(';\n')  
                                # 写入到输出文件  
                                outfile.write(first_style + task_name + ';\n')  
        outfile.write("endtask")
    shutil.move("all_sim_file.v", os.path.join("sim_case_list", "all_sim_file.v"))
    '''
    print(f'所有验证case已提取并写入到 all_sim_file.v')
    print("Script generated successfully......")
    print("Script generated successfully......")
    print("Script generated successfully......")
