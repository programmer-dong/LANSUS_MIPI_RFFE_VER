import os
import random
import shutil
import pandas as pd
import sys
import xlrd

SIM_CASE_DIR = "sim_case_list"
STANDARD_TRIGGERS = ("trigger_0", "trigger_1", "trigger_2")
STANDARD_TRIGGER_CFG = {
    "trigger_0": ("8'b1011_0000", "8'b1011_0001"),
    "trigger_1": ("8'b1010_1000", "8'b1010_1010"),
    "trigger_2": ("8'b1001_1000", "8'b1001_1100"),
}

mipi_reserver_all_reg = [
    "0x1c", "0x1d", "0x1e", "0x1f", "0x20", "0x21", "0x22", "0x23", "0x24",
    "0x2a", "0x2b", "0x2c", "0x2d", "0x2e", "0x2f", "0x30",
    "0x31", "0x32", "0x33", "0x34", "0x35", "0x36", "0x37",
    "0x38", "0x39", "0x3a", "0x3b", "0x3c", "0x3d", "0x3e", "0x3f",
]
MIPI_RESERVED_SET = {addr.lower() for addr in mipi_reserver_all_reg}

# 运行时由 main() 注入的全局配置（保持与历史脚本兼容）
first_style = second_style = loop_style = code_style = ""
trigger_0_mask = trigger_1_mask = trigger_2_mask = ""
trigger_0_reg = trigger_1_reg = trigger_2_reg = ""
ext_trigger_3_10 = ext_trigger_11_17 = ext_trigger_3_17 = {}
ext_udr_mapped = timed_tri_mapped = {}
ext_list = []
bsid_reg_sta_dict = gsid_reg_sta_dict = mask_reg_sta_dict = {}
all_bsid_reg = all_gsid_reg = all_mask_reg = []
reg_dicr = command_dicr = {}
no_trigger_reg = sta_trigger_reg = extended_trigger_reg = {}
mipi_reserved_reg = udr_set_reg = {}
all_user_dicr = reg_reserved_dicr = default_value_dict = {}
extended_command = ""
reserved_len = 0


def normalize_reg(reg_address):
    if reg_address is None:
        return ""
    return str(reg_address).strip().lower()



def has_reg(reg_map, reg_address):
    normalized_reg = normalize_reg(reg_address)
    return any(normalize_reg(key) == normalized_reg for key in reg_map)


def is_mipi_reserved(reg_address):
    return normalize_reg(reg_address) in MIPI_RESERVED_SET


def reg_hex(reg_address):
    return normalize_reg(reg_address).split("x", 1)[1]


def reg_decimal(reg_address):
    return int(reg_hex(reg_address), 16)


def reserved_mask_for(reg_key):
    if not reserved_len:
        return ""
    normalized_key = normalize_reg(reg_key)
    for reserved_key, reserved_bits in reg_reserved_dicr.items():
        if normalize_reg(reserved_key) == normalized_key:
            return generate_mask_strings(reserved_bits)
    return ""


def has_reserved_bits(reg_key):
    normalized_key = normalize_reg(reg_key)
    return any(normalize_reg(reserved_key) == normalized_key for reserved_key in reg_reserved_dicr)


def is_udr_rst_register(reg_key, reg_map=None):
    source = reg_map if isinstance(reg_map, dict) else all_user_dicr
    normalized_key = normalize_reg(reg_key)
    for key, rows in source.items():
        if normalize_reg(key) != normalized_key:
            continue
        return any("udr_rst" in str(cell).strip().lower() for row in rows for cell in row)
    return False


def emit_read_chk(file, chk_type, addr_hex, data_expr, reg_key):
    suffix = reserved_mask_for(reg_key)
    if chk_type == "ext":
        line = f"ext_reg_read_chk(usid_user,8'h{addr_hex},8'h00,{data_expr}{suffix});"
    else:
        line = f"reg_read_chk(usid_user,8'h{addr_hex},{data_expr}{suffix});"
    file.write(line + code_style)


def read_expected_with_reserved(reg_key, write_data):
    mask = reserved_mask_for(reg_key)
    if mask:
        return f"{{1'b0,{write_data}{mask}}}"
    if str(write_data).startswith("8'h"):
        return str(write_data).replace("8'h", "9'h0", 1)
    return f"{{1'b0,{write_data}}}"


def mipi_reg_exists(reg_key):
    return has_reg(mipi_reserved_reg, reg_key)


def is_extended_trigger_register(reg_key, reg_map=None):
    if has_reg(extended_trigger_reg, reg_key):
        return True

    source = reg_map if isinstance(reg_map, dict) else all_user_dicr
    normalized_key = normalize_reg(reg_key)
    for key, value in source.items():
        if normalize_reg(key) != normalized_key or not value:
            continue
        trigger_type = str(value[0][6]).strip().lower()
        return "mt" in trigger_type
    return False


def standard_trigger_pairs():
    return {
        "trigger_0": [trigger_0_mask, trigger_0_reg],
        "trigger_1": [trigger_1_mask, trigger_1_reg],
        "trigger_2": [trigger_2_mask, trigger_2_reg],
    }


def trigger_pair(trigger_str):
    """根据 trigger 字符串返回标准触发器 [mask, reg]，无匹配返回 None。"""
    s = trigger_str.lower()
    for name, pair in standard_trigger_pairs().items():
        if name in s:
            return list(pair)
    return None


def emit_trigger_comment(file, trigger_val):
    for reg_val, name in (
        (trigger_0_reg, "trigger_0"),
        (trigger_1_reg, "trigger_1"),
        (trigger_2_reg, "trigger_2"),
    ):
        if trigger_val == reg_val:
            file.write(first_style + "// " + name + code_style)
            return


def reset_reg1c(file):
    file.write("// reset reg1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'hb8);" + code_style)
    if has_reg(mipi_reserved_reg, "0x2d"):
        file.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + code_style)
    if has_reg(mipi_reserved_reg, "0x30"):
        file.write("ext_reg_write(usid_user,8'h30,8'h00,8'hff);" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h30,8'h00,9'h07f);" + code_style)


def finalize_sim_task(filename, strip_empty=True):
    """去空行（可选）并把生成的 .v 文件移动到 sim_case_list 目录。"""
    if strip_empty:
        remove_empty_lines(filename)
    target = os.path.join(SIM_CASE_DIR, filename)
    if os.path.exists(target):
        os.remove(target)
    shutil.move(filename, target)


def get_excel_data(register_file):
    try:
        excel_file = xlrd.open_workbook(register_file)
        mipi_sheet = excel_file.sheet_by_name("MIPI")
        command_dict = {
            str(mipi_sheet.cell_value(0, 4)).strip(): str(mipi_sheet.cell_value(0, 5)).strip(),
            str(mipi_sheet.cell_value(1, 4)).strip(): str(mipi_sheet.cell_value(1, 5)).strip(),
        }
        df = pd.read_excel(register_file, sheet_name="MIPI", skiprows=3)
        reg_dict = {}
        prev_reg_address = None
        reg_values = []
        data_columns = list(df.columns[1:])
        reserved_skip_col = 4

        for _, row in df.iterrows():
            reg_address = row[df.columns[0]]
            if pd.isnull(reg_address):
                reg_address = prev_reg_address
            if prev_reg_address is not None and reg_address != prev_reg_address:
                reg_dict[prev_reg_address] = reg_values
                reg_values = []

            if is_mipi_reserved(reg_address):
                reg_other = [
                    row[col] for col in data_columns
                    if df.columns.get_loc(col) != reserved_skip_col
                ]
            else:
                reg_other = [row[col] for col in data_columns]

            reg_values.append(reg_other)
            prev_reg_address = reg_address

        if prev_reg_address is not None:
            reg_dict[prev_reg_address] = reg_values

        return reg_dict, command_dict
    except Exception as e:
        print(f"Error reading the Excel file: {e}")
        sys.exit(1)


def _is_udr_set_register(reg_values):
    if not reg_values:
        return False
    if reg_values[0][0].lower() == "udr_set":
        return True
    return any("udr_set" in row[2].lower() for row in reg_values[:2] if len(row) > 2)


def reg_data_process(reg_data_all):
    no_trigger_dict = {}
    standard_trigger_dict = {}
    extended_trigger_dict = {}
    mipi_reserved_dict = {}
    udr_set_dict = {}

    for reg_address, reg_value in reg_data_all.items():
        if is_mipi_reserved(reg_address):
            mipi_reserved_dict[reg_address] = reg_value
            continue

        trigger_type = reg_value[0][6].lower()
        if trigger_type == "no":
            no_trigger_dict[reg_address] = reg_value
        elif trigger_type in STANDARD_TRIGGERS:
            standard_trigger_dict[reg_address] = reg_value
        elif "mt" in trigger_type:
            extended_trigger_dict[reg_address] = reg_value

        if _is_udr_set_register(reg_value):
            udr_set_dict[reg_address] = [[row[1], row[2]] for row in reg_value]

    return no_trigger_dict, standard_trigger_dict, extended_trigger_dict, mipi_reserved_dict, udr_set_dict

def generate_random_integer():  
    return random.randint(1, 1000) 


def generate_hex_random(width=8):
    """生成 Verilog 字面量，默认 8'hXX。"""
    hex_byte = format(random.randint(0, 0xFF), "02X")
    if width == 8:
        return f"8'h{hex_byte}"
    return f"9'h0{hex_byte}"


def generate_hex_random_two():
    return generate_hex_random(width=9)


def generate_random_list(length):
    return [generate_hex_random() for _ in range(length)]

def write_other_reg(file, test_reg, all_reg, ext_com_support, skip_extended_trigger=False):
    result_reg_data = {}
    file.write("$display(\"//******************************************//\");" + code_style)
    file.write("$display(\"//*****write other reg except test reg******//\");" + code_style)
    file.write("$display(\"//******************************************//\");" + code_style)
    file.write("begin"+code_style)
    for each_reg in all_reg:
        if skip_extended_trigger and is_extended_trigger_register(each_reg, all_reg):
            continue
        if each_reg != test_reg:
            reg_format = reg_hex(each_reg)
            decimal_number = reg_decimal(each_reg)
            write_data = generate_hex_random()
            if decimal_number <= 31:
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
    file.write(first_indent + "begin" + code_style)
    for key_result, value_result in result_write_reg.items():
        if "x" not in key_result:
            continue
        reg_format = reg_hex(key_result)
        decimal_number = int(reg_format, 16)
        reserved_write = reserved_mask_for(key_result)
        if decimal_number <= 31:
            file.write(
                loop_style + f"reg_read_chk(usid_user,8'h{reg_format},{value_result}{reserved_write});"
                + code_style
            )
        elif decimal_number > 31 and ext_com_support == "support":
            file.write(
                loop_style
                + f"ext_reg_read_chk(usid_user,8'h{reg_format},8'h00,{value_result}{reserved_write});"
                + code_style
            )
    file.write(first_indent + "end" + code_style)



def check_mipi_default_value(all_trigger_dict, command_support):
    with open("sim_default_value.v", 'w', encoding='utf-8') as sim_defult_file:
        sim_defult_file.write("task sim_default_value;\n")
        display_start_fun(sim_defult_file, "default value check ")
        for each_trigger, each_value in all_trigger_dict.items():
            if each_trigger.lower() not in mipi_reserver_all_reg:
                trigger_format = reg_hex(each_trigger)
                value_str = ''.join([val[4] for val in each_value])
                default_value_dict[each_trigger] = value_str
                write_reg_chk(sim_defult_file, trigger_format, value_str, command_support)
        fixed_reads = (
            "reg_read_chk(usid_user,8'h1c,9'h080);",
            "reg_read_chk(usid_user,8'h1d,{1'b0,product_id_user[7:0]});",
            "reg_read_chk(usid_user,8'h1e,{1'b0,man_id_user[7:0]});",
            "reg_read_chk(usid_user,8'h1f,{1'b0,man_id_user[11:8],usid_user});",
        )
        optional_reads = (
            ("0x20", "ext_reg_read_chk(usid_user,8'h20,8'h00,{1'b0,ext_product_id_user[7:0]});"),
            ("0x21", "ext_reg_read_chk(usid_user,8'h21,8'h00,{1'b0,revision_id_user[7:0]});"),
            ("0x22", "ext_reg_read_chk(usid_user,8'h22,8'h00,{1'b0,8'h00});"),
            ("0x23", "ext_reg_read_chk(usid_user,8'h23,8'h00,{1'b0,8'h00});"),
            ("0x24", "ext_reg_read_chk(usid_user,8'h24,8'h00,{1'b0,8'h00});"),
            ("0x2b", "ext_reg_read_chk(usid_user,8'h2b,8'h00,{1'b0,busld_user[7:0]});"),
            ("0x2c", "ext_reg_read_chk(usid_user,8'h2c,8'h00,{1'b0,8'hd2});"),
            ("0x2d", "ext_reg_read_chk(usid_user,8'h2d,8'h00,{1'b0,8'h00});"),
            ("0x2e", "ext_reg_read_chk(usid_user,8'h2e,8'h00,{1'b0,8'h00});"),
            ("0x2f", "ext_reg_read_chk(usid_user,8'h2f,8'h00,{1'b0,8'h00});"),
            ("0x30", "ext_reg_read_chk(usid_user,8'h30,8'h00,{1'b0,8'h00});"),
        )
        for line in fixed_reads:
            sim_defult_file.write(line + code_style)
        for reg_key, line in optional_reads:
            if has_reg(mipi_reserved_reg, reg_key):
                sim_defult_file.write(line + code_style)
        sim_defult_file.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_default_value.v")


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
    tag=4:reg0_write trigger
'''


def _write_trigger_command(file, command, reg_format, write_data):
    if command == "reg0_write":
        file.write(f"reg0_write(usid_user,{write_data});{code_style}")
    elif command == "reg_write":
        file.write(f"reg_write(usid_user,8'h{reg_format},{write_data});{code_style}")
    elif command == "ext_reg_write":
        file.write(f"ext_reg_write(usid_user,8'h{reg_format},8'h00,{write_data});{code_style}")


def reg_trigger_test(file, reg_single, trigger, command, write_data, trigger_before):
    if command not in ("reg0_write", "reg_write", "ext_reg_write"):
        return

    trigger_key = next((name for name in STANDARD_TRIGGERS if name in trigger.lower()), None)
    if trigger_key is None:
        return

    mask_val, trigger_val = STANDARD_TRIGGER_CFG[trigger_key]
    reg_format = reg_hex(reg_single)
    read_addr = "00" if command == "reg0_write" else reg_format
    chk_type = "ext" if command == "ext_reg_write" else "reg"
    reg0_mask = "&8'h7f" if command == "reg0_write" else ""

    file.write(f"//write data {write_data} by trigger{code_style}")
    file.write(f"reg_write(usid_user,8'h1c,{mask_val});{code_style}")
    _write_trigger_command(file, command, reg_format, write_data)
    emit_read_chk(file, chk_type, read_addr, f"{trigger_before}{reg0_mask}", reg_single)
    file.write(f"reg_write(usid_user,8'h1c,{trigger_val});{code_style}")
    emit_read_chk(file, chk_type, read_addr, f"{write_data}{reg0_mask}", reg_single)

def write_spec_data(file, reg_single, tag):
    if has_reserved_bits(reg_single):
        return

    reg_format = reg_hex(reg_single)
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
    decimal_number = reg_decimal(reg_single)
    for write_data, check_data in zip(masked_write_data, masked_check):
        if tag == 7 :
            file.write(first_style + "masked_write(usid_user,8'h"+reg_format+","+write_data+");"+code_style)     
            mask = reserved_mask_for(reg_single)
            if decimal_number <= 31:
                file.write(first_style+"reg_read_chk(usid_user,8'h"+reg_format+","+"{1'b0,"+check_data+mask+"});"+code_style)
            else:
                file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + "," + "8'h00,{1'b0,"+check_data + mask+"});"+code_style)
    for write_data, check_data in zip(write_data_list, read_check_list):
        if tag == 0:
            file.write(first_style + "reg0_write(usid_user," + write_data + ");\n" + "     ")
            file.write(first_style + "reg_read_chk(usid_user,8'h00," + "{1'b0,"+write_data + "&8'h7f"+reserved_mask_for(reg_single)+"});\n" + "     ")
        elif tag == 1:
            file.write(first_style + "reg_write(usid_user,8'h" + reg_format + "," + write_data + ");\n" + "     ")
            file.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + "," + "{1'b0,"+write_data + reserved_mask_for(reg_single)+"});\n" + "     ")
        elif tag == 2:
            file.write(first_style + "ext_reg_write(usid_user,8'h" + reg_format + ",8'h00," + write_data + ");\n" + "     ")
            file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + "," + "8'h00,{1'b0,"+write_data + reserved_mask_for(reg_single)+"});\n" + "     ")
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

    finalize_sim_task("sim_usid_programmable.v")


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
    finalize_sim_task("sim_reg0_write_no_trigger.v")


def _set_extended_trigger(file, all_reg_trigger, reg_addr, trigger_range, enable):
    reg_key = f"0x{reg_addr}"
    if not has_reg(all_reg_trigger, reg_key):
        return
    mode = "enable" if enable else "disable"
    write_val = "8'h00" if enable else "8'hff"
    if enable:
        read_val = "9'h000"
    elif normalize_reg(reg_key) == "0x30":
        read_val = "9'h07f"
    else:
        read_val = "9'h0ff"
    file.write(f"$display(\"****extended trigger {mode}****\");{code_style}")
    file.write(f"//============= trigger {trigger_range} ==============|0x{reg_addr.upper()}{code_style}")
    file.write(f"ext_reg_write(usid_user,8'h{reg_addr},8'h00,{write_val});\n     ")
    file.write(f"ext_reg_read_chk(usid_user,8'h{reg_addr},8'h00,{read_val});\n     ")


def trigger_disable(file, all_reg_trigger):
    file.write("$display(\"****standard trigger disable****\");" + code_style)
    file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'hb8);\n     ")
    file.write("reg_read_chk(usid_user,8'h1c,9'h0b8);\n     ")
    _set_extended_trigger(file, all_reg_trigger, "2d", "3-10", enable=False)
    _set_extended_trigger(file, all_reg_trigger, "30", "11-17", enable=False)


def trigger_enable(file, all_reg_trigger):
    file.write("$display(\"****standard trigger enable****\");" + code_style)
    file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h80);\n     ")
    file.write("reg_read_chk(usid_user,8'h1c,9'h080);\n     ")
    _set_extended_trigger(file, all_reg_trigger, "2d", "3-10", enable=True)
    _set_extended_trigger(file, all_reg_trigger, "30", "11-17", enable=True)

def reg0_command_loop_body(file, usid_user, result_reg_dict, ext_com_support):
    file.write("packet_rand = new(" + str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    reg0_write(usid_user,data);" + code_style)
    file.write(first_style + "reg_read_chk(usid_user,8'h00,{1'b0,data&8'b0111_1111"+reserved_mask_for("0x00")+"});" + code_style)
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
    file.write(loop_style + "reg_read_chk(usid_user,8'h00,{1'b0,(data_pre)&(8'b0111_1111)"+reserved_mask_for("0x00")+"});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "$display(\"****trigger data to reg00_direct****\");" + code_style)
    emit_trigger_comment(file, trigger_list[1])
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[1] + ");" + code_style)
    file.write(first_style + "reg_read_chk(usid_user,8'h00,{1'b0,data&8'b0111_1111"+reserved_mask_for("0x00")+"});" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;")

 
def reg_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support):
    reg_format = reg_hex(each_reg)
    decimal_number = reg_decimal(each_reg)
    write_spec_data(file, each_reg, 1)
    if decimal_number <= 31:
        file.write("packet_rand = new(" +str(generate_random_integer())+ ");" + code_style)
        file.write("for(i=0; i<=255; i++) begin" + code_style)
        file.write("    packet_rand.randomize();" + code_style)
        file.write("    data = packet_rand.data_packet;" + code_style)
        file.write("    reg_write(" + usid_user + ",8'h" + reg_format + ",data);" + code_style)
        file.write("    reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data"+reserved_mask_for(each_reg)+"});" + code_style)
        read_other_reg(file, result_reg_dict, ext_com_support, first_style)
        file.write("end" + code_style)
        file.write("packet_rand = null;"+code_style)

def reg_command_trigger_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, trigger_list):
    reg_format = reg_hex(each_reg)
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
    file.write(loop_style + "reg_read_chk(usid_user,8'h"+reg_format+",{1'b0,data_pre"+reserved_mask_for(each_reg)+"});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "$display(\"****trigger data to reg"+reg_format+"_direct****\");" + code_style)
    emit_trigger_comment(file, trigger_list[1])
    file.write(first_style + "reg_write("+ usid_user + ",8'h1c," + trigger_list[1] + ");" + code_style)
    file.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data"+reserved_mask_for(each_reg)+"});" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)
    reset_reg1c(file)

def ext_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support):
    reg_format = reg_hex(each_reg)
    write_spec_data(file, each_reg, 2)
    file.write("packet_rand = new("+str(generate_random_integer())+");" + code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    ext_reg_write(" + usid_user + ",8'h" + reg_format + ",8'h00,data);" + code_style)
    file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data"+reserved_mask_for(each_reg)+"});" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)


def ext_command_trigger_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, trigger_list, write_command):
    reg_format = reg_hex(each_reg)
    write_spec_data(file, each_reg, 6)
    file.write("// reg" + reg_format + code_style)
    file.write("$display(\"****reg"+reg_format+" trigger test****\");" + code_style)
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "packet_rand.randomize();" + code_style)
    file.write(first_style + "data = packet_rand.data_packet;" + code_style)
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[0] + ");" + code_style)
    file.write(first_style + "$display(\"****write data to reg"+reg_format+"_shadow****\");" + code_style)
    file.write(first_style + write_command[0] +"(usid_user,8'h" + reg_format + ",8'h00,data);" + code_style)
    file.write(first_style + "if(i==0)begin" + code_style)
    file.write(loop_style + write_command[1] +"(usid_user,8'h"+reg_format+",8'h00,{1'b0,8'h00});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    file.write(loop_style +  write_command[1] + "(usid_user,8'h"+reg_format+",8'h00,{1'b0,(data_pre)"+reserved_mask_for(each_reg)+"});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "$display(\"****trigger data to reg"+reg_format+"_direct****\");" + code_style)
    emit_trigger_comment(file, trigger_list[1])
    file.write(first_style + "reg_write(usid_user,8'h1c," + trigger_list[1] + ");" + code_style)
    file.write(first_style +  write_command[1] + "(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data"+reserved_mask_for(each_reg)+"});" + code_style)
    file.write(first_style + "data_pre = data;" + code_style)
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)
    reset_reg1c(file)

def _masked_read_line(reg_format, each_reg, extended):
    payload = "{1'b0,masked_result" + reserved_mask_for(each_reg) + "}"
    if extended:
        return "    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00," + payload + ");"
    return "    reg_read_chk(usid_user,8'h" + reg_format + "," + payload + ");"


def _write_masked_loop(file, each_reg, reg_format, extended, result_reg_dict, ext_com_support, before_read=None):
    file.write("data_pre = 8'b" + default_value_dict[each_reg] + ";" + code_style)
    file.write("packet_rand = new(" + str(generate_random_integer()) + ");" + code_style)
    file.write("packet_rand_two = new(" + str(generate_random_integer()) + ");" + code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    bit [7:0] masked_result;" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    packet_rand_two.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    data_two = packet_rand_two.data_two_packet;" + code_style)
    file.write("    masked_result = (data_pre&data)|((~data)&data_two);" + code_style)
    file.write("    masked_write(usid_user,8'h" + reg_format + ",data[7:0],data_two[7:0]);" + code_style)
    if before_read:
        before_read()
    file.write(_masked_read_line(reg_format, each_reg, extended) + code_style)
    file.write("    data_pre = masked_result;" + code_style)
    if before_read:
        file.write("\n     ")
    read_other_reg(file, result_reg_dict, ext_com_support, first_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;" + code_style)
    file.write("packet_rand_two = null;" + code_style)


def masked_write_command_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, skip_special_values=False):
    if "x" not in normalize_reg(each_reg):
        return
    reg_format = reg_hex(each_reg)
    extended = reg_decimal(each_reg) > 31
    if extended and ext_com_support != "support":
        return
    if not skip_special_values:
        write_spec_data(file, each_reg, 7)
    _write_masked_loop(file, each_reg, reg_format, extended, result_reg_dict, ext_com_support)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'hb8);" + code_style)


def masked_write_command_trigger_loop_body(file, usid_user, each_reg, result_reg_dict, ext_com_support, trigger_list):
    if "x" not in normalize_reg(each_reg):
        return
    reg_format = reg_hex(each_reg)
    extended = reg_decimal(each_reg) > 31
    if extended and ext_com_support != "support":
        return
    write_spec_data(file, each_reg, 7)
    file.write("$display(\"*****standard trigger enble*****\");" + code_style)
    file.write("//============= trigger 0-2 ===============|0x1c" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h80);" + code_style)
    file.write("reg_read_chk(usid_user,8'h1c,9'h080);" + code_style)
    file.write("// reg" + reg_format + code_style)
    file.write("$display(\"****reg" + reg_format + " trigger test****\");" + code_style)

    def before_read():
        emit_trigger_comment(file, trigger_list[1])
        file.write("    reg_write(usid_user,8'h1c," + trigger_list[1] + ");" + code_style)

    _write_masked_loop(
        file, each_reg, reg_format, extended, result_reg_dict, ext_com_support, before_read
    )
    reset_reg1c(file)

def _emit_ext_trigger_arm(file, tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user):
    split_line(file, " start:" + tri_mask + " ")
    file.write("// trigger_mask_" + tri_mask.split("_")[1] + code_style)
    if tri_mask in ext_trigger_3_10:
        file.write("ext_reg_write(usid_user,8'h2d,8'h00," + tri_reg[0] + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h2d,8'h00," + tri_reg[0] + ");" + code_style)
    elif tri_mask in ext_trigger_11_17:
        file.write("ext_reg_write(usid_user,8'h30,8'h00," + tri_reg[0] + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h30,8'h00," + tri_reg[0] + ");" + code_style)
    file.write("$display(\"****select reg" + reg_format_udr + " trigger is " + tri_mask + "****\");" + code_style)
    udr_bits = ext_udr_mapped[tri_mask]
    if reg_value[1] in ("3:0", "3：0"):
        field = "{4'b0000," + udr_bits + "}"
    elif reg_value[1] in ("7:4", "7：4"):
        field = "{" + udr_bits + ",4'b0000}"
    else:
        field = ""
    if field:
        file.write("ext_reg_write(usid_user,8'h" + reg_format_udr + ",8'h00," + field + ");" + code_style)
        file.write("ext_reg_read_chk(usid_user,8'h" + reg_format_udr + ",8'h00," + field + ");" + code_style)
    file.write("// reg" + reg_format_user + code_style)
    file.write("$display(\"****reg" + reg_format_user + " ext_trigger test****\");" + code_style)
    file.write("packet_rand = new(" + str(generate_random_integer()) + ");" + code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write(first_style + "packet_rand.randomize();" + code_style)
    file.write(first_style + "data = packet_rand.data_packet;" + code_style)
    file.write(first_style + "ext_reg_write(usid_user,8'h" + reg_format_user + ",8'h00,data);" + code_style)
    file.write(first_style + "if(i==0) begin" + code_style)
    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h" + reg_format_user + ",8'h00,{1'b0,9'h000});" + code_style)
    file.write(first_style + "end" + code_style)
    file.write(first_style + "else begin" + code_style)
    file.write(loop_style + "ext_reg_read_chk(usid_user,8'h" + reg_format_user + ",8'h00,{1'b0,data_pre});" + code_style)
    file.write(first_style + "end" + code_style)


def _emit_ext_trigger_tail(file, tri_mask):
    file.write(first_style + "data_pre = data;" + code_style)
    file.write("end" + code_style)
    file.write("packet_rand = null;" + code_style)
    file.write("reg_write(usid_user,8'h1c,8'h40);" + code_style)
    split_line(file, " end:" + tri_mask + " ")


def extended_trigger_loop_body(file, usid_user, tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user):
    _emit_ext_trigger_arm(file, tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user)
    file.write(first_style + "// " + tri_mask + code_style)
    if tri_mask in ext_trigger_3_10:
        file.write(first_style + "ext_reg_write(usid_user,8'h2e,8'h00," + tri_reg[1] + ");" + code_style)
    elif tri_mask in ext_trigger_11_17:
        file.write(first_style + "ext_reg_write(usid_user,8'h2f,8'h00, " + tri_reg[1] + ");" + code_style)
    file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format_user + ",8'h00,data);" + code_style)
    _emit_ext_trigger_tail(file, tri_mask)

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
    _emit_ext_trigger_arm(file, tri_reg, tri_mask, reg_format_udr, reg_value, reg_format_user)
    display_start_fun(file, "write time cnt reg")
    cnt_reg = timed_tri_mapped.get(tri_mask)
    if cnt_reg:
        timed_trigger_cnt(file, cnt_reg.replace("8'h", ""), random.randint(0, 255))
    file.write(first_style + "// read " + reg_format_user + code_style)
    file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format_user + ",8'h00,data);" + code_style)
    _emit_ext_trigger_tail(file, tri_mask)
    file.write("\n" + code_style)

def sim_reg1c_reg(file, usid_user, each_reg):
    reg_format = reg_hex(each_reg)
    display_reg(file, each_reg)

    file.write("begin" + code_style)
    file.write("    reg_write(" + usid_user + ",8'h" + reg_format + ",8'hb8);" + code_style)
    if has_reg(mipi_reserved_reg, "0x2d"):
        file.write("    ext_reg_write(" + usid_user + ",8'h2d,8'h00,8'hff);" + code_style)
    file.write("end" + code_style)


def sim_reg1d_reg1e_reg1f_reg(file, usid_user, each_reg):
    reg_format = reg_hex(each_reg)
    display_reg(file, each_reg)
    result_reg_dict = write_other_reg(
        file, '0x1d', all_user_dicr, extended_command, skip_extended_trigger=True
    )
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    reg_write(" + usid_user + ",8'h" + reg_format + ",data);" + code_style)
    readback = {
        "0x1d": "{1'b0,product_id_user}",
        "0x1e": "{1'b0,man_id_user[7:0]}",
        "0x1f": "{1'b0,man_id_user[11:8], usid_user}",
    }.get(each_reg.lower())
    if readback:
        file.write("    reg_read_chk(usid_user,8'h" + reg_format + "," + readback + ");" + code_style)
    read_other_reg(file, result_reg_dict, extended_command, "")
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)


def sim_reg20_to_reg30_reg(file, usid_user, each_reg):
    reg_format = reg_hex(each_reg)
    display_reg(file, each_reg)
    result_reg_dict = write_other_reg(
        file, '0x1d', all_user_dicr, extended_command, skip_extended_trigger=True
    )
    file.write("packet_rand = new("+str(generate_random_integer())+");"+code_style)
    file.write("for(i=0; i<=255; i++) begin" + code_style)
    file.write("    packet_rand.randomize();" + code_style)
    file.write("    data = packet_rand.data_packet;" + code_style)
    file.write("    ext_reg_write(" + usid_user + ",8'h" + reg_format + ",8'h00,data);" + code_style)
    readback = {
        "0x20": "{1'b0,ext_product_id_user}",
        "0x21": "{1'b0,revision_id_user}",
        "0x22": "{1'b0,data}",
        "0x23": "{1'b0,8'h00}",
        "0x24": "{1'b0,8'h00}",
        "0x2b": "{1'b0,data&8'h0f}",
        "0x2c": "{1'b0,8'hd2}",
        "0x2d": "{1'b0,data}",
        "0x2f": "{1'b0,8'h00}",
        "0x30": "{1'b0,data}",
    }.get(each_reg.lower())
    if readback:
        file.write("    ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00," + readback + ");" + code_style)
    if each_reg.lower() != '0x23':
        read_other_reg(file, result_reg_dict, extended_command, "")
    file.write("end" + code_style)
    file.write("packet_rand = null;"+code_style)

def sim_reg31_to_reg3f(file, usid_user, time_reg_list):
    for each_reg in time_reg_list:
        reg_format = reg_hex(each_reg)
        display_reg(file, each_reg)
        file.write("begin"+code_style)
        file.write(first_style +"ext_reg_write(usid_user,8'h"+reg_format+",8'h00,8'ha0);"+code_style)
        for count in ("95", "84", "74", "63", "53", "42", "32", "21", "11", "00"):
            file.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,8'h" + count + "});" + code_style)
        file.write("end" + code_style)



def _emit_err_seq(file, label, write_fn, err_fn, read_fn, write_addr, read_addr, reg_key, sum_bits):
    """生成一组错误注入序列：写入 -> 校验 -> 注错 -> 校验 -> 重写 -> 校验 -> sum_err 校验。"""
    read_55 = read_expected_with_reserved(reg_key, "8'h55")
    read_66 = read_expected_with_reserved(reg_key, "8'h66")
    file.write(f"$display(\"****{label}****\");" + code_style)
    file.write(f"{write_fn}(usid_user,{write_addr}8'h55);" + code_style)
    file.write(f"{read_fn}(usid_user,{read_addr}{read_55});" + code_style)
    file.write(f"{err_fn}(usid_user,{write_addr}8'h66);" + code_style)
    file.write(f"{read_fn}(usid_user,{read_addr}{read_55});" + code_style)
    file.write(f"{write_fn}(usid_user,{write_addr}8'h66);" + code_style)
    file.write(f"{read_fn}(usid_user,{read_addr}{read_66});" + code_style)
    file.write(f"ext_reg_read_chk(usid_user,sum_err_addr,8'h00,{sum_bits});" + code_style)
    file.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);" + code_style)


def _emit_err_reg(file, first_reg, key, err_fn, label, sum_bits):
    addr = f"8'h{first_reg},"
    _emit_err_seq(file, label, "reg_write", err_fn, "reg_read_chk", addr, addr, key, sum_bits)


def _emit_err_ext(file, first_reg, key, err_fn, label, sum_bits):
    addr = f"8'h{first_reg},8'h00,"
    _emit_err_seq(file, label, "ext_reg_write", err_fn, "ext_reg_read_chk", addr, addr, key, sum_bits)


def _emit_err_masked(file, err_fn, label, sum_bits):
    foramt_mask = reg_hex(all_mask_reg[0])
    addr = f"8'h{foramt_mask},8'h00,"
    _emit_err_seq(file, label, "masked_write", err_fn, "ext_reg_read_chk", addr, addr,
                  all_mask_reg[0], sum_bits)


def sim_error_test():
    with open("sim_error_test.v", 'w', encoding='utf-8') as sim_err:
        sim_err.write("task sim_error_test;\n")
        display_start_fun(sim_err, "error_test(sum_err)")
        trigger_disable(sim_err, reg_dicr)
        first_data = list(all_user_dicr.items())[0]
        first_key = first_data[0]
        first_reg = reg_hex(first_key)

        sim_err.write("\n")
        display_start_fun(sim_err, "command frame with parity error")
        _emit_err_reg(sim_err, first_reg, first_key, "reg_write_cmd_parity_err",
                      "reg_write_cmd_parity_err", "9'b00100_0000")
        if extended_command == 'support':
            _emit_err_ext(sim_err, first_reg, first_key, "ext_reg_write_cmd_parity_err",
                          "ext_reg_write_cmd_parity_err", "9'b00100_0000")
        if len(all_mask_reg) != 0:
            _emit_err_masked(sim_err, "masked_write_cmd_parity_err",
                             "masked_write_cmd_parity_err", "9'b00100_0000")

        sim_err.write("\n")
        display_start_fun(sim_err, "command frame with length error")
        if '0x00' in all_user_dicr:
            _emit_err_seq(sim_err, "reg0_write_len_parity_err", "reg0_write",
                          "reg0_write_cmd_len_err", "reg_read_chk", "", "8'h00,",
                          "0x00", "9'b00010_0000")
        _emit_err_reg(sim_err, first_reg, first_key, "reg_write_cmd_len_err",
                      "reg_write_len_parity_err", "9'b00010_0000")
        if extended_command == 'support':
            _emit_err_ext(sim_err, first_reg, first_key, "ext_reg_write_cmd_len_err",
                          "ext_reg_write_len_parity_err", "9'b00010_0000")
        if len(all_mask_reg) != 0:
            _emit_err_masked(sim_err, "masked_write_cmd_len_err",
                             "masked_write_len_parity_err", "9'b00010_0000")

        sim_err.write("\n")
        display_start_fun(sim_err, "addr frame with parity error")
        if extended_command == 'support':
            _emit_err_ext(sim_err, first_reg, first_key, "ext_reg_write_addrl_parity_err",
                          "ext_reg_write_len_parity_err", "9'b00001_0000")
        if len(all_mask_reg) != 0:
            _emit_err_masked(sim_err, "masked_write_addrl_parity_err",
                             "masked_write_len_parity_err", "9'b00001_0000")

        sim_err.write("\n")
        display_start_fun(sim_err, "data frame with parity error")
        _emit_err_reg(sim_err, first_reg, first_key, "reg_write_data_parity_err",
                      "reg_write_len_parity_err", "9'b00000_1000")
        if extended_command == 'support':
            _emit_err_ext(sim_err, first_reg, first_key, "ext_reg_write_data_parity_err",
                          "ext_reg_write_len_parity_err", "9'b00000_1000")
        if len(all_mask_reg) != 0:
            _emit_err_masked(sim_err, "masked_write_mdata_parity_err",
                             "masked_write_len_parity_err", "9'b00000_1000")

        sim_err.write("\n")
        display_start_fun(sim_err, "read using the  bsid or gsid")
        sim_err.write("$display(\"****reg_read use the bsid error****\");" + code_style)
        sim_err.write("reg_read_chk(4'h0,8'h1c,`NRF);" + code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0001);"+code_style)
        sim_err.write("ext_reg_read_chk(usid_user,sum_err_addr,8'h00,9'b00000_0000);"+code_style)
        reg_reset_command(sim_err)
        sim_err.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_error_test.v")
        

def sim_reg_write_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_reg_write_trigger_disable.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_reg_write_trigger_disable;\n")
        display_start_fun(sim_reg, "reg_write_command_no_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_reg, value_reg in all_user_reg.items():
            decimal_number = reg_decimal(key_reg)
            if decimal_number <= 31:
                result_reg_dict = write_other_reg(sim_reg, key_reg, all_user_reg, ext_com_support)
                display_reg(sim_reg, key_reg)
                reg_command_loop_body(sim_reg, "usid_user", key_reg, result_reg_dict, ext_com_support)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_reg_write_trigger_disable.v")


def sim_ext_write_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_ext_write_trigger_disable.v", 'w', encoding='utf-8') as sim_ext:
        write_data_begin(sim_ext)
        sim_ext.write("task sim_ext_write_trigger_disable;\n")
        display_start_fun(sim_ext, "ext_write_command_no_trigger")
        trigger_disable(sim_ext, all_reg)
        for key_reg, value_reg in all_user_reg.items():
            result_reg_dict = write_other_reg(sim_ext, key_reg, all_user_reg, ext_com_support)
            display_reg(sim_ext, key_reg)
            ext_command_loop_body(sim_ext, "usid_user", key_reg, result_reg_dict, ext_com_support)
        reg_reset_command(sim_ext)
        sim_ext.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_ext_write_trigger_disable.v")


def sim_masked_write_no_trigger(all_reg, all_user_reg, ext_com_support):
    with open("sim_masked_write_no_trigger.v", 'w', encoding='utf-8') as sim_masked:
        write_data_begin(sim_masked)
        sim_masked.write("task sim_masked_write_no_trigger;\n")
        display_start_fun(sim_masked, "masked_write_command_no_trigger")
        trigger_disable(sim_masked, all_reg)
        for key_masked, value_masked in all_user_reg.items():
            if "M" in value_masked[0][7] or "m" in value_masked[0][7]:
                if mipi_reg_exists("0x2d"):
                    sim_masked.write("ext_reg_write(usid_user,8'h2d,8'h00,8'hff);" + code_style)
                result_reg_dict = write_other_reg(sim_masked, key_masked, all_user_reg, ext_com_support)
                display_reg(sim_masked, key_masked)
                masked_write_command_loop_body(
                    sim_masked,
                    "usid_user",
                    key_masked,
                    result_reg_dict,
                    ext_com_support,
                    skip_special_values=is_udr_rst_register(key_masked, all_user_reg),
                )
        reg_reset_command(sim_masked)
        sim_masked.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_masked_write_no_trigger.v")


def sim_reg0_write_sta_trigger(all_user, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_reg0_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg0:
        write_data_begin(sim_reg0)
        sim_reg0.write("task sim_reg0_write_sta_trigger;\n")
        display_start_fun(sim_reg0, "sim_reg0_write_sta_trigger")
        trigger_disable(sim_reg0, all_user)
        for key_trigger, value_trigger in sta_trigger.items():
            if key_trigger != '0x00':
                continue
            trigger_list = trigger_pair(value_trigger[0][6])
            if trigger_list is None:
                continue
            result_reg_dict = write_other_reg(sim_reg0, '0x00', all_user_reg, ext_comm_support)
            write_spec_data(sim_reg0, "0x00", 4)
            reg0_command_trigger_loop_body(sim_reg0, "usid_user", result_reg_dict, ext_comm_support, trigger_list)
        reg_reset_command(sim_reg0)
        sim_reg0.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_reg0_write_sta_trigger.v")


def sim_reg_write_sta_trigger(all_reg, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_reg_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_reg_write_sta_trigger;\n")
        display_start_fun(sim_reg, "sim_reg_write_sta_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_trigger, value_trigger in sta_trigger.items():
            decimal_number = reg_decimal(key_trigger)
            if decimal_number > 31:
                continue
            if "sta_all" in str(value_trigger[0][8]).lower():
                for trigger_list in standard_trigger_pairs().values():
                    result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                    reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, list(trigger_list))
            else:
                trigger_list = trigger_pair(value_trigger[0][6])
                if trigger_list is None:
                    continue
                result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
                reg_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_reg_write_sta_trigger.v")


def sim_ext_write_sta_trigger(all_reg, sta_trigger, all_user_reg, ext_comm_support):
    with open("sim_ext_write_sta_trigger.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_ext_write_sta_trigger;\n")
        display_start_fun(sim_reg, "sim_ext_write_sta_trigger")
        trigger_disable(sim_reg, all_reg)
        for key_trigger, value_trigger in sta_trigger.items():
            trigger_list = trigger_pair(value_trigger[0][6])
            if trigger_list is None:
                continue
            result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_reg, ext_comm_support)
            ext_command_trigger_loop_body(sim_reg, "usid_user", key_trigger, result_reg_dict, ext_comm_support, trigger_list, ext_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_ext_write_sta_trigger.v")


def sim_masked_write_sta_trigger(all_reg, all_user_reg, all_mask_reg, ext_comm_support):
    with open("sim_masked_write_sta_trigger.v", 'w', encoding='utf-8') as sim_masked:
        write_data_begin(sim_masked)
        sim_masked.write("task sim_masked_write_sta_trigger;\n")
        display_start_fun(sim_masked, "sim_masked_write_sta_trigger")
        trigger_disable(sim_masked, all_reg)
        for key_masked, value_masked in all_mask_reg.items():
            trigger_list = trigger_pair(value_masked[0][6])
            if trigger_list is None:
                continue
            result_reg_dict = write_other_reg(sim_masked, key_masked, all_user_reg, ext_comm_support)
            masked_write_command_trigger_loop_body(sim_masked, "usid_user", key_masked, result_reg_dict, ext_comm_support, trigger_list)
        reg_reset_command(sim_masked)
        sim_masked.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_masked_write_sta_trigger.v")


def sim_ext_extended_trigger(all_reg, all_user_reg, udr_reg, ext_comm_support):
    with open("sim_ext_extended_trigger.v", 'w', encoding='utf-8') as sim_tri:
        write_data_begin(sim_tri)
        sim_tri.write("task sim_ext_extended_trigger;\n")
        display_start_fun(sim_tri, "sim_ext_extended_trigger")     
        for reg_key, reg_value in udr_reg.items():
            reg_format_user = reg_hex(reg_key)
            reg_format_udr = reg_hex(reg_value[0])
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
    finalize_sim_task("sim_ext_extended_trigger.v")

def sim_extended_timed_trigger(udr_trigger):
    with open("sim_extended_timeed_trigger.v", 'w', encoding='utf-8') as sim_time:
        write_data_begin(sim_time)
        sim_time.write("task sim_extended_timeed_trigger;\n")
        display_start_fun(sim_time, "sim_extended_timeed_trigger")
        for reg_key, reg_value in udr_trigger.items():
            reg_format_user = reg_hex(reg_key)
            reg_format_udr = reg_hex(reg_value[0])
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
    finalize_sim_task("sim_extended_timeed_trigger.v", strip_empty=False)


def sim_mipi_reserved_reg(mipi_res_reg):
    time_block_b = ["0x31", "0x32", "0x33", "0x34", "0x35", "0x36", "0x37"]   # trigger11-17
    time_block_a = ["0x38", "0x39", "0x3a", "0x3b", "0x3c", "0x3d", "0x3e", "0x3f"]   # trigger3-10
    ext_reserved_regs = {
        "0x20", "0x21", "0x22", "0x23", "0x24", "0x2b", "0x2c", "0x2d", "0x2e", "0x2f", "0x30"
    }
    with open("sim_mipi_reserved_reg.v", 'w', encoding='utf-8') as sim_mipi:
        write_data_begin(sim_mipi)
        sim_mipi.write("task sim_mipi_reserved_reg;\n")
        display_start_fun(sim_mipi, "sim_mipi_reserved_reg")
        for key_mipi, value_mipi in mipi_reserved_reg.items():
            reg_key = normalize_reg(key_mipi)
            if reg_key == '0x1c':
                sim_reg1c_reg(sim_mipi, "usid_user", "0x1c")
            elif reg_key in {"0x1d", "0x1e", "0x1f"}:
                sim_reg1d_reg1e_reg1f_reg(sim_mipi, "usid_user", reg_key)
            elif reg_key in ext_reserved_regs:
                sim_reg20_to_reg30_reg(sim_mipi, "usid_user", reg_key)
            elif reg_key == '0x31':
                sim_reg31_to_reg3f(sim_mipi, "usid_user", time_block_b)
            elif reg_key == '0x38':
                sim_reg31_to_reg3f(sim_mipi, "usid_user", time_block_a)
        reg_reset_command(sim_mipi)
        sim_mipi.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_mipi_reserved_reg.v")


def sim_write_with_bsid():
    with open("sim_write_with_bsid.v", 'w', encoding='utf-8') as sim_bsid:
        write_data_begin(sim_bsid)
        sim_bsid.write("task sim_write_with_bsid;\n")
        display_start_fun(sim_bsid, "sim_write_with_bsid")
        trigger_disable(sim_bsid, reg_dicr)
        for key_bsid in all_bsid_reg:
            decimal_number = reg_decimal(key_bsid)
            loop_body = reg_command_loop_body if decimal_number <= 31 else ext_command_loop_body
            result_reg_dict = write_other_reg(sim_bsid, key_bsid, all_user_dicr, extended_command)
            loop_body(sim_bsid, "4'h0", key_bsid, result_reg_dict, extended_command)
        reg_reset_command(sim_bsid)
        sim_bsid.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_write_with_bsid.v")
    

def sim_write_with_gsid():
    with open("sim_write_with_gsid.v", 'w', encoding='utf-8') as sim_gsid:
        write_data_begin(sim_gsid)
        sim_gsid.write("task sim_write_with_gsid;\n")
        display_start_fun(sim_gsid, "sim_write_with_gsid")
        trigger_disable(sim_gsid, reg_dicr)
        for key_gsid in all_gsid_reg:
            decimal_number = reg_decimal(key_gsid)
            loop_body = reg_command_loop_body if decimal_number <= 31 else ext_command_loop_body
            result_reg_dict = write_other_reg(sim_gsid, key_gsid, all_user_dicr, extended_command)
            write_hex_number_gsid = generate_hex_random()
            sim_gsid.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
            sim_gsid.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
            gsid_hex = write_hex_number_gsid.replace("8'h", "")
            gsid_list = {"gsid0": gsid_hex[0], "gsid1": gsid_hex[1]}
            for gsid_name, item_gsid in gsid_list.items():
                sim_gsid.write("// use " + gsid_name + " write "+ key_gsid + code_style)
                loop_body(sim_gsid, "4'h"+item_gsid, key_gsid, result_reg_dict, extended_command)
        reg_reset_command(sim_gsid)
        sim_gsid.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_write_with_gsid.v")
    

def sim_trigger_with_bsid():
    with open("sim_trigger_with_bsid.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_trigger_with_bsid;\n")
        display_start_fun(sim_reg, "sim_trigger_with_bsid")
        trigger_disable(sim_reg, reg_dicr)
        for key_trigger, value_trigger in sta_trigger_reg.items():
            decimal_number = reg_decimal(key_trigger)
            if decimal_number > 31:
                continue
            trigger_list = trigger_pair(value_trigger[0][6])
            if trigger_list is None:
                continue
            result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
            reg_command_trigger_loop_body(sim_reg, "4'h0", key_trigger, result_reg_dict, extended_command, trigger_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_trigger_with_bsid.v")

def sim_trigger_with_gsid():
    with open("sim_trigger_with_gsid.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_trigger_with_gsid;\n")
        display_start_fun(sim_reg, "sim_trigger_with_gsid")
        trigger_disable(sim_reg, reg_dicr)
        for key_trigger, value_trigger in sta_trigger_reg.items():
            decimal_number = reg_decimal(key_trigger)
            if decimal_number > 31:
                continue
            trigger_list = trigger_pair(value_trigger[0][6])
            if trigger_list is None:
                continue
            result_reg_dict = write_other_reg(sim_reg, key_trigger, all_user_dicr, extended_command)
            write_hex_number_gsid = generate_hex_random()
            sim_reg.write("$display(\"//***** change reg22 to update gsid *****//\");"+code_style)
            sim_reg.write("ext_reg_write(usid_user,8'h22,8'h00,"+write_hex_number_gsid+");"+code_style)
            gsid_list = {}
            gsid_list["gsid0"] = write_hex_number_gsid.replace("8'h", "")[0]
            gsid_list["gsid1"] = write_hex_number_gsid.replace("8'h", "")[1]
            # 随机选择一个gsid
            sim_reg.write("// use gsid write "+ key_trigger + code_style)
            item_gsid = random.choice(list(gsid_list.values()))
            reg_command_trigger_loop_body(sim_reg, "4'h" + item_gsid, key_trigger, result_reg_dict, extended_command, trigger_list)
        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_trigger_with_gsid.v")


def sim_ext_write_more_reg_no_tri():
    def read_expected_literal(reg_key, write_data):
        return read_expected_with_reserved(reg_key, write_data)

    def build_unused_windows(user_reg_addrs):
        user_reg_set = set(user_reg_addrs)
        windows = []
        seen = set()

        def add_window(kind, addr_list):
            if 0x1c in addr_list:
                return
            key = tuple(addr_list)
            if key in seen:
                return
            seen.add(key)
            windows.append((kind, addr_list))

        for addr in user_reg_addrs:
            unused_addr = addr - 1
            if unused_addr >= 0 and unused_addr not in user_reg_set:
                add_window("unused_head", [unused_addr, addr])

        for left_addr, right_addr in zip(user_reg_addrs, user_reg_addrs[1:]):
            if right_addr - left_addr > 1:
                add_window("unused_middle", list(range(left_addr, right_addr + 1)))

        for addr in user_reg_addrs:
            unused_addr = addr + 1
            if unused_addr <= 0x7f and unused_addr not in user_reg_set:
                add_window("unused_tail", [addr, unused_addr])

        return windows

    with open("sim_ext_write_more_reg_no_tri.v", 'w', encoding='utf-8') as sim_reg:
        write_data_begin(sim_reg)
        sim_reg.write("task sim_ext_write_more_reg_no_tri;\n")
        display_start_fun(sim_reg, "sim_ext_write_more_reg_no_tri")
        trigger_disable(sim_reg, reg_dicr)

        user_reg_addrs = sorted(reg_decimal(reg) for reg in all_user_dicr)
        user_reg_set = set(user_reg_addrs)
        sim_reg.write("$display(\"/// incremental length coverage: 1 to 16 registers ///\");" + code_style)
        for start_addr in user_reg_addrs:
            start_reg = f"{start_addr:02x}"
            sim_reg.write("$display(\"/// start reg 0x" + start_reg + " ///\");" + code_style)

            for length in range(1, 17):
                end_addr = start_addr + length - 1
                if end_addr == 0x1c:
                    break

                reg_range = [f"0x{addr:02x}" for addr in range(start_addr, end_addr + 1)]
                write_data_list = generate_random_list(length)
                expected_data = []
                for reg_key, write_data in zip(reg_range, write_data_list):
                    if reg_decimal(reg_key) in user_reg_set:
                        expected_data.append(read_expected_literal(reg_key, write_data))
                    else:
                        expected_data.append("`NRF")

                write_data_str = ",".join(write_data_list)
                expected_data_str = ",".join(expected_data)
                len_field = f"{length - 1:02x}"

                sim_reg.write("$display(\"/// write " + str(length) + " registers from 0x" + start_reg + " ///\");" + code_style)
                sim_reg.write("ext_reg_write(usid_user,8'h" + start_reg + ",8'h" + len_field + ",{" + write_data_str + "});" + code_style)
                sim_reg.write("ext_reg_read_chk(usid_user,8'h" + start_reg + ",8'h" + len_field + ",{" + expected_data_str + "});" + code_style)

        sim_reg.write("$display(\"/// unused position coverage: head / middle / tail ///\");" + code_style)
        for window_kind, addr_list in build_unused_windows(user_reg_addrs):
            start_addr = addr_list[0]
            start_reg = f"{start_addr:02x}"
            len_field = f"{len(addr_list) - 1:02x}"
            reg_range = [f"0x{addr:02x}" for addr in addr_list]
            write_data_list = generate_random_list(len(addr_list))
            expected_data = []

            for reg_key, write_data in zip(reg_range, write_data_list):
                if reg_decimal(reg_key) in user_reg_set:
                    expected_data.append(read_expected_literal(reg_key, write_data))
                else:
                    expected_data.append("`NRF")

            write_data_str = ",".join(write_data_list)
            expected_data_str = ",".join(expected_data)
            window_desc = " -> ".join(f"0x{addr:02x}" for addr in addr_list)

            sim_reg.write("$display(\"/// " + window_kind + ": " + window_desc + " ///\");" + code_style)
            sim_reg.write("ext_reg_write(usid_user,8'h" + start_reg + ",8'h" + len_field + ",{" + write_data_str + "});" + code_style)
            sim_reg.write("ext_reg_read_chk(usid_user,8'h" + start_reg + ",8'h" + len_field + ",{" + expected_data_str + "});" + code_style)

        reg_reset_command(sim_reg)
        sim_reg.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_ext_write_more_reg_no_tri.v")
        


def sim_write_unused_reg():
    existing_regs = sorted(reg_decimal(reg) for reg in all_user_dicr)
    if not existing_regs:
        return

    candidate_addrs = [addr for addr in range(0, 28) if addr not in existing_regs]
    if extended_command == "support":
        candidate_addrs.extend(addr for addr in range(64, 128) if addr not in existing_regs)
    if not candidate_addrs:
        return

    with open("sim_write_unused_reg.v", 'w', encoding='utf-8') as sim_unused:
        write_data_begin(sim_unused)
        sim_unused.write("task sim_write_unused_reg;"+code_style)
        trigger_disable(sim_unused, reg_dicr)
        for key_reg in sorted(all_user_dicr, key=reg_decimal):
            reg_format = reg_hex(key_reg)
            decimal_number = reg_decimal(key_reg)
            unused_addr = random.choice(candidate_addrs)
            unused_format = f"{unused_addr:02x}"

            if decimal_number <= 31:
                display_reg(sim_unused, key_reg)
                sim_unused.write("packet_rand = new(" + str(generate_random_integer()) + ");" + code_style)
                sim_unused.write("for(i=0;i<=255;i++) begin" + code_style)
                sim_unused.write(first_style + "packet_rand.randomize();" + code_style)
                sim_unused.write(first_style + "data = packet_rand.data_packet;" + code_style)
                sim_unused.write(first_style + "reg_write(usid_user,8'h" + reg_format + ",data);" + code_style)
                sim_unused.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data" + reserved_mask_for(key_reg) + "});" + code_style)
                if unused_addr < 28:
                    sim_unused.write(first_style + "reg_write(usid_user,8'h" + unused_format + ",data);" + code_style)
                    sim_unused.write(first_style + "reg_read_chk(usid_user,8'h" + unused_format + ",{1'b1,8'h00});" + code_style)
                elif extended_command == "support":
                    sim_unused.write(first_style + "ext_reg_write(usid_user,8'h" + unused_format + ",8'h00,data);" + code_style)
                    sim_unused.write(first_style + "ext_reg_read_chk(usid_user,8'h" + unused_format + ",8'h00,{1'b1,8'h00});" + code_style)
                sim_unused.write(first_style + "reg_read_chk(usid_user,8'h" + reg_format + ",{1'b0,data" + reserved_mask_for(key_reg) + "});" + code_style)
                sim_unused.write("end" + code_style)
                sim_unused.write("packet_rand = null;" + code_style)
            elif extended_command == "support":
                display_reg(sim_unused, key_reg)
                sim_unused.write("packet_rand = new(" + str(generate_random_integer()) + ");" + code_style)
                sim_unused.write("for(i=0;i<=255;i++) begin" + code_style)
                sim_unused.write(first_style + "packet_rand.randomize();" + code_style)
                sim_unused.write(first_style + "data = packet_rand.data_packet;" + code_style)
                sim_unused.write(first_style + "ext_reg_write(usid_user,8'h" + reg_format + ",8'h00,data);" + code_style)
                sim_unused.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data" + reserved_mask_for(key_reg) + "});" + code_style)
                if unused_addr < 28:
                    sim_unused.write(first_style + "reg_write(usid_user,8'h" + unused_format + ",data);" + code_style)
                    sim_unused.write(first_style + "reg_read_chk(usid_user,8'h" + unused_format + ",{1'b1,8'h00});" + code_style)
                else:
                    sim_unused.write(first_style + "ext_reg_write(usid_user,8'h" + unused_format + ",8'h00,data);" + code_style)
                    sim_unused.write(first_style + "ext_reg_read_chk(usid_user,8'h" + unused_format + ",8'h00,{1'b1,8'h00});" + code_style)
                sim_unused.write(first_style + "ext_reg_read_chk(usid_user,8'h" + reg_format + ",8'h00,{1'b0,data" + reserved_mask_for(key_reg) + "});" + code_style)
                sim_unused.write("end" + code_style)
                sim_unused.write("packet_rand = null;" + code_style)
        reg_reset_command(sim_unused)
        sim_unused.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_write_unused_reg.v", strip_empty=False)


def sim_special_case():
    with open("sim_special_case.v", 'w', encoding='utf-8') as sim:
        write_data_begin(sim)
        sim.write("`define UNUSED 8'h00"+"\n")
        sim.write("$display(\"***************************************************\");\n")
        sim.write("$display(\"*** You can write some targeted test cases here ***\");\n")
        sim.write("$display(\"***************************************************\");\n")
        sim.write("task sim_special_case;"+code_style)
        sim.write("reg_write(usid_user,8'h1c,8'hb8);"+code_style)
        sim.write("reg_read_chk(usid_user,8'h1c,9'h0b8);"+code_style)
        sim.write("packet_rand = new(" + str(generate_random_integer())+");"+code_style)
        sim.write("for(i=0;i<=255;i++) begin"+code_style)
        sim.write(first_style+"packet_rand.randomize();"+code_style)
        sim.write(first_style+"data = packet_rand.data_packet;"+code_style)
        sim.write("end"+code_style)
        sim.write("packet_rand = null;"+code_style)
        reg_reset_command(sim)
        sim.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_special_case.v", strip_empty=False)


def sim_reg1c_reg23_reset():
    with open("sim_reg1c_reg23_reset.v", 'w', encoding='utf-8') as sim_reset:
        write_data_begin(sim_reset)
        sim_reset.write("task sim_reg1c_reg23_reset;\n")
        display_start_fun(sim_reset, "sim_reg1c_reset_user_define")
        trigger_disable(sim_reset, reg_dicr)
        if has_reg(reg_dicr, "0x1c"):
            result_reg_dicr = write_other_reg(sim_reset, "0x1c", all_user_dicr, extended_command)
            read_other_reg(sim_reset, result_reg_dicr, extended_command, "")
            reg_reset_command(sim_reset)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "default value check ")
            for each_trigger, each_value in all_user_dicr.items():
                if each_trigger.lower() not in mipi_reserver_all_reg:
                    trigger_format = reg_hex(each_trigger)
                    value_str = ''.join([val[4] for val in each_value])
                    write_reg_chk(sim_reset, trigger_format, value_str, extended_command)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "sim_reg1c_reset_mipi_reserved")
            sim_reset.write("reg_write(usid_user,8'h1c,8'hb8);"+code_style)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'hb8);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_write(usid_user,8'h22,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'haa);"+code_style)
            if has_reg(reg_dicr, "0x2b"):
                sim_reset.write("ext_reg_write(usid_user,8'h2b,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h0a);"+code_style)
            reg_reset_command(sim_reset)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'h80);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'h00);"+code_style)
            if has_reg(reg_dicr, "0x2b"):
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h00);"+code_style)
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
                    trigger_format = reg_hex(each_trigger)
                    value_str = ''.join([val[4] for val in each_value])
                    write_reg_chk(sim_reset, trigger_format, value_str, extended_command)
            sim_reset.write("\n")
            display_start_fun(sim_reset, "sim_reg23_reset_mipi_reserved")
            sim_reset.write("reg_write(usid_user,8'h1c,8'hb8);"+code_style)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'hb8);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_write(usid_user,8'h22,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'haa);"+code_style)
            if has_reg(reg_dicr, "0x2b"):
                sim_reset.write("ext_reg_write(usid_user,8'h2b,8'h00,8'haa);"+code_style)
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h0a);"+code_style)
            sim_reset.write("// reset all_mipi_reserved;\n"+code_style)
            sim_reset.write("ext_reg_write(usid_user,8'h23,8'h00,8'h80);"+code_style)
            sim_reset.write("reg_read_chk(usid_user,8'h1c,8'hb8);"+code_style)
            if '0x22' in reg_dicr:
                sim_reset.write("ext_reg_read_chk(usid_user,8'h22,8'h00,8'haa);"+code_style)
            if has_reg(reg_dicr, "0x2b"):
                sim_reset.write("ext_reg_read_chk(usid_user,8'h2b,8'h00,8'h0a);"+code_style)  
        reg_reset_command(sim_reset)
        sim_reset.write("\n" + "endtask" + "\n")
    finalize_sim_task("sim_reg1c_reg23_reset.v")
            


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
    list_data = list("11111111")
    for each_reserved in bit_range_lists:
        if ":" not in each_reserved:
            list_data[int(each_reserved)] = "0"
        else:
            high_bit, low_bit = each_reserved.split(":")
            for index_change in range(int(low_bit), int(high_bit) + 1):
                list_data[index_change] = "0"
    return "&8'b" + "".join(reversed(list_data))


def configure_output_styles():
    global first_style, second_style, loop_style, code_style
    global trigger_0_mask, trigger_1_mask, trigger_2_mask
    global trigger_0_reg, trigger_1_reg, trigger_2_reg
    global ext_trigger_3_10, ext_trigger_11_17, ext_trigger_3_17
    global ext_udr_mapped, timed_tri_mapped, ext_list

    first_style = " " * 4
    second_style = " " * 10
    loop_style = " " * 7
    code_style = "\n     "
    trigger_0_mask = "8'b1011_0000"
    trigger_1_mask = "8'b1010_1000"
    trigger_2_mask = "8'b1001_1000"
    trigger_0_reg = "8'b1011_0001"
    trigger_1_reg = "8'b1010_0010"
    trigger_2_reg = "8'b1001_1100"
    ext_trigger_3_10 = {
        "trigger_3": ["8'b1111_1110", "8'b0000_0001"],
        "trigger_4": ["8'b1111_1101", "8'b0000_0010"],
        "trigger_5": ["8'b1111_1011", "8'b0000_0100"],
        "trigger_6": ["8'b1111_0111", "8'b0000_1000"],
        "trigger_7": ["8'b1110_1111", "8'b0001_0000"],
        "trigger_8": ["8'b1101_1111", "8'b0010_0000"],
        "trigger_9": ["8'b1011_1111", "8'b0100_0000"],
        "trigger_10": ["8'b0100_1111", "8'b1000_0000"],
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
    ext_udr_mapped = {
        f"trigger_{idx}": f"4'b{idx - 3:04b}" for idx in range(3, 18)
    }
    timed_tri_mapped = {
        f"trigger_{idx}": f"8'h{hex_val}"
        for idx, hex_val in zip(
            range(3, 18),
            ["38", "39", "3a", "3b", "3c", "3d", "3e", "3f", "31", "32", "33", "34", "35", "36", "37"],
        )
    }
    ext_list = ["ext_reg_write", "ext_reg_read_chk"]


def load_register_context(register_file_path):
    global reg_dicr, command_dicr, no_trigger_reg, sta_trigger_reg, extended_trigger_reg
    global mipi_reserved_reg, udr_set_reg, all_user_dicr, extended_command
    global all_bsid_reg, all_gsid_reg, all_mask_reg, bsid_reg_sta_dict, gsid_reg_sta_dict
    global mask_reg_sta_dict, reg_reserved_dicr, reserved_len, default_value_dict

    reg_dicr, command_dicr = get_excel_data(register_file_path)
    no_trigger_reg, sta_trigger_reg, extended_trigger_reg, mipi_reserved_reg, udr_set_reg = reg_data_process(
        reg_dicr
    )
    all_user_dicr = {
        key: value for key, value in reg_dicr.items() if not is_mipi_reserved(key)
    }
    extended_command = ""
    for each_command, command_value in command_dicr.items():
        command_enabled = str(command_value).strip().upper() == "YES"
        if each_command == "ext_reg_write+ext_reg_read":
            extended_command = "support" if command_enabled else "no_support"

    all_bsid_reg, all_gsid_reg, all_mask_reg = [], [], []
    bsid_reg_sta_dict, gsid_reg_sta_dict, mask_reg_sta_dict = {}, {}, {}
    for key, value in all_user_dicr.items():
        attr = value[0][7].lower()
        trigger_mode = value[0][6].lower()
        if "b" in attr:
            all_bsid_reg.append(key)
        if "g" in attr:
            all_gsid_reg.append(key)
        if "m" in attr:
            all_mask_reg.append(key)
        if "trigger" in trigger_mode:
            if "m" in attr:
                mask_reg_sta_dict[key] = value
            if "b" in attr:
                bsid_reg_sta_dict[key] = value
            if "g" in attr:
                gsid_reg_sta_dict[key] = value

    reg_reserved_dicr = {}
    for key, value in all_user_dicr.items():
        if len(value) < 2:
            continue
        write_no_bit = [sublist[1] for sublist in value if sublist[2].lower() == "reserved"]
        if write_no_bit:
            reg_reserved_dicr[key] = write_no_bit
    reserved_len = len(reg_reserved_dicr)
    default_value_dict = {}


def prepare_sim_case_dir():
    os.makedirs(SIM_CASE_DIR, exist_ok=True)
    for filename in os.listdir(SIM_CASE_DIR):
        if filename.endswith(".v"):
            os.remove(os.path.join(SIM_CASE_DIR, filename))


def run_all_generators():
    check_mipi_default_value(reg_dicr, extended_command)
    usid_programmable_mode(mipi_reserved_reg, extended_command)
    if "0x00" in reg_dicr:
        sim_reg0_write_command(reg_dicr, all_user_dicr, extended_command)

    sim_reg_write_no_trigger(reg_dicr, all_user_dicr, extended_command)
    if extended_command == "support":
        sim_ext_write_no_trigger(reg_dicr, all_user_dicr, extended_command)
    if all_mask_reg:
        sim_masked_write_no_trigger(reg_dicr, all_user_dicr, extended_command)

    if "0x00" in sta_trigger_reg:
        sim_reg0_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command)

    sta_exists = bool(sta_trigger_reg)
    if sta_exists:
        sim_reg_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command)
        sim_trigger_with_bsid()
        if "0x22" in reg_dicr:
            sim_trigger_with_gsid()

    if sta_exists and extended_command == "support":
        sim_ext_write_sta_trigger(reg_dicr, sta_trigger_reg, all_user_dicr, extended_command)
    if mask_reg_sta_dict:
        sim_masked_write_sta_trigger(reg_dicr, all_user_dicr, mask_reg_sta_dict, extended_command)

    if extended_trigger_reg:
        udr_trigger = find_matching_udr_triggers(extended_trigger_reg, udr_set_reg, extended_command)
        sim_ext_extended_trigger(reg_dicr, all_user_dicr, udr_trigger, extended_command)
        sim_extended_timed_trigger(udr_trigger)

    sim_mipi_reserved_reg(mipi_reserved_reg)
    sim_write_unused_reg()
    sim_special_case()
    if all_bsid_reg:
        sim_write_with_bsid()
    if all_gsid_reg and "0x22" in reg_dicr:
        sim_write_with_gsid()
    sim_reg1c_reg23_reset()
    if "0x24" in reg_dicr:
        sim_error_test()
    if extended_command == "support":
        sim_ext_write_more_reg_no_tri()


def generate_sim_cases(register_file_path):
    configure_output_styles()
    prepare_sim_case_dir()
    load_register_context(register_file_path)
    run_all_generators()
    return os.path.abspath(SIM_CASE_DIR)


def main():
    if len(sys.argv) < 2:
        print("Usage: python gen_sim_case.py register_file_path")
        sys.exit(1)

    generate_sim_cases(sys.argv[1])
    print("所有验证case已提取并写入到 all_sim_file.v")
    print("Script generated successfully.")


if __name__ == "__main__":
    main()
