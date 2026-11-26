import os
import re
import sys
from pathlib import Path


SIM_CONFIG_FIELDS = (
    ("usid_user", "8'h01"),
    ("usid_user3", "8'h03"),
    ("gusid0_user", "8'h00"),
    ("gusid1_user", "8'h00"),
    ("busld_user", "8'h00"),
    ("busld_user_3", "8'h00"),
    ("man_id_user", "12'h34e"),
    ("man_id_user_3", "12'hbaa"),
    ("product_id_user", "8'h00"),
    ("product_id_user_3", "8'h01"),
    ("ext_product_id_user", "8'h5a"),
    ("ext_product_id_user_3", "8'h5a"),
    ("revision_id_user", "8'h00"),
    ("pm_default_user", "1'b1"),
    ("test_patt", "8'hD2"),
    ("sum_err_addr", "8'h24"),
)

# 测试平台里已经有的信号。键是 mipi_core 端口名。
_KNOWN = {
    "usid_in": "usid_user[3:0]",
    "product_id_in": "product_id_user[7:0]",
    "man_id_lsb_in": "man_id_user[7:0]",
    "man_id_msb_in": "man_id_user[11:8]",
    "ext_product_id_in": "ext_product_id_user[7:0]",
    "gsid0_din": "gusid0_user[3:0]",
    "gsid1_din": "gusid1_user[3:0]",
    "revision_id_in": "revision_id_user[7:0]",
    "pm_default_in": "pm_default_user",
    "busld_default_in": "busld_user[3:0]",
    "sdata_in": "sdata_test",
    "sdata_in1": "sdata_test",
    "rst_n": "sys_rstn",
    "sclk": "sclk_test",
    "sdata_out": "sdata_out",
    "sdata_oe": "sdata_oe",
}
_DECLARED = {"sdata_out", "sdata_oe"}
_DECL = re.compile(
    r"\b(input|output|inout)\b\s*(?:wire|reg|logic|tri0?|tri1)?\s*(\[[^\]]+\])?\s*([^;]+);",
    re.I,
)
_ASSIGN = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*;", re.M)


def default_sim_config():
    return {name: value for name, value in SIM_CONFIG_FIELDS}


def load_sim_config(path):
    values = default_sim_config()
    file_path = Path(path)
    if not file_path.is_file():
        return values
    text = file_path.read_text(encoding="utf-8", errors="replace")
    for name, value in _ASSIGN.findall(text):
        if name in values:
            values[name] = value.strip()
    return values


def render_sim_config(values):
    current = default_sim_config()
    current.update(values)
    lines = ["//User define"]
    widths = {
        "usid_user": "[3:0] ",
        "usid_user3": "[3:0] ",
        "gusid0_user": "[3:0] ",
        "gusid1_user": "[3:0] ",
        "busld_user": "[3:0] ",
        "busld_user_3": "[3:0] ",
        "product_id_user": "[7:0] ",
        "product_id_user_3": "[7:0] ",
        "man_id_user": "[11:0]",
        "man_id_user_3": "[11:0]",
        "ext_product_id_user": "[7:0] ",
        "ext_product_id_user_3": "[7:0] ",
        "revision_id_user": "[7:0] ",
        "pm_default_user": "      ",
        "test_patt": "[7:0] ",
        "sum_err_addr": "[7:0] ",
    }
    for name, _value in SIM_CONFIG_FIELDS:
        if name == "test_patt":
            lines.append("reg [7:0]  test_patt;")
            lines.append("reg [7:0]  sum_err_addr;")
            lines.append("")
            lines.append("initial begin")
            break
        lines.append(f"reg {widths[name]:<7} {name};")
    body = [name for name, _value in SIM_CONFIG_FIELDS if name != "sum_err_addr"]
    for name in body:
        lines.append(f"\t{name:<22}=  {current[name]}  ;")
    lines.extend([
        "end",
        "",
        "initial begin",
        f"\tsum_err_addr        = {current['sum_err_addr']};",
        "end",
        "",
    ])
    return "\n".join(lines)


def write_sim_config(project, values):
    path = Path(project) / "sim_top" / "sim_config.v"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_lf(path, render_sim_config(values))
    return path


def find_mipi_core(design):
    path = Path(design)
    if not str(path).strip():
        raise FileNotFoundError("先选择设计路径。")
    if path.is_file() and path.name == "mipi_core.v":
        return path
    root = path if path.is_dir() else path.parent
    if not root.is_dir():
        raise FileNotFoundError(f"设计路径不存在: {path}")
    direct = (
        root / "mipi_core.v",
        root / "src" / "slave" / "mipi_core.v",
        path.parent / "mipi_core.v",
    )
    for item in direct:
        if item.is_file():
            return item
    for current, dirnames, filenames in os.walk(root):
        depth = len(Path(current).relative_to(root).parts)
        if depth > 6:
            dirnames.clear()
            continue
        dirnames[:] = [name for name in dirnames if name not in {".git", "sim_case_list"}]
        if "mipi_core.v" in filenames:
            return Path(current) / "mipi_core.v"
    raise FileNotFoundError(f"在设计路径下没有找到 mipi_core.v: {root}")


def parse_mipi_ports(text):
    match = re.search(r"\bmodule\s+mipi_core\b", text)
    if not match:
        raise ValueError("mipi_core.v 里没有 module mipi_core")
    open_at = text.find("(", match.end())
    if open_at < 0:
        raise ValueError("mipi_core 没有端口列表")
    blob, close_at = _scan_paren(text, open_at)
    body_end = text.find("endmodule", close_at)
    body = text[close_at:body_end if body_end >= 0 else len(text)]
    stripped = _strip_comments(blob)
    if re.search(r"\b(input|output|inout)\b", stripped, re.I):
        return _parse_ansi(stripped)
    names = _port_names(blob)
    decls = _parse_decls(body)
    hints = _direction_hints(blob)
    ports = []
    for name in names:
        direction, width = decls.get(name, (hints.get(name, "input"), None))
        ports.append((name, direction, width))
    if not ports:
        raise ValueError("没有解析到 mipi_core 的端口")
    return ports


def render_instance(ports):
    wires = []
    connected = []
    commented = []
    for name, direction, width in ports:
        expr, comment = _connect(name, direction, width)
        if comment:
            commented.append((name, expr))
            continue
        if direction in {"output", "inout"} and name not in _DECLARED and expr == name:
            wires.append(_wire(name, width))
        connected.append((name, direction, expr))
    lines = [
        "//===========================================",
        "// Module Instance",
        "//===========================================",
    ]
    lines.extend(wires)
    if wires:
        lines.append("")
    lines.append(" mipi_core mipi_slave(/*autoinst*/")
    items = []
    for direction, title in (("input", "        //Inputs"), ("output", "        //Outputs")):
        rows = [
            (name, expr)
            for name, item_dir, expr in connected
            if item_dir == direction or (direction == "output" and item_dir == "inout")
        ]
        if not rows:
            continue
        items.append(("note", title))
        if direction == "input" and commented:
            items.extend(("note", f"        //.{name:<18} ( {expr} ),") for name, expr in commented)
        items.extend(("port", f"        .{name:<18} ( {expr} )") for name, expr in rows)
    if commented and not any(item_dir in {"output", "inout"} for _name, item_dir, _expr in connected):
        items.extend(("note", f"        //.{name:<18} ( {expr} )") for name, expr in commented)
    port_indexes = [index for index, (kind, _line) in enumerate(items) if kind == "port"]
    last_port = port_indexes[-1] if port_indexes else None
    for index, (kind, line) in enumerate(items):
        if kind == "port" and index != last_port:
            line += ","
        elif kind == "port":
            line += ");"
        lines.append(line)
    if last_port is None:
        lines.append(");")
    return "\n".join(lines) + "\n"


def _task_library():
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parent
    path = base / "templates" / "rffe_base.v"
    if not path.is_file():
        raise FileNotFoundError(f"找不到任务库模板: {path}")
    return path


def update_rffe_instance(project, design):
    core = find_mipi_core(design)
    rffe = Path(project) / "sim_top" / "rffe_base.v"
    if not rffe.is_file():
        rffe.parent.mkdir(parents=True, exist_ok=True)
        rffe.write_bytes(_task_library().read_bytes())
    ports = parse_mipi_ports(core.read_text(encoding="utf-8", errors="replace"))
    block = render_instance(ports)
    original = rffe.read_bytes()
    text = original.decode("utf-8", errors="replace")
    updated = _splice_instance(text, block)
    _write_rffe(rffe, updated, original)
    return core, rffe, ports


_REG_PORT = re.compile(r"^reg([0-9a-fA-F]{2})$")
_PORT_BEGIN = "//==== reg_port_chk begin ===="
_PORT_END = "//==== reg_port_chk end ===="


def output_reg_ports(ports):
    found = []
    for name, direction, width in ports:
        if direction not in {"output", "inout"}:
            continue
        match = _REG_PORT.fullmatch(name)
        if not match:
            continue
        found.append((int(match.group(1), 16), name, width))
    found.sort()
    return found


def output_reg_addrs(ports):
    return [addr for addr, _name, _width in output_reg_ports(ports)]


def render_port_tasks(ports):
    items = output_reg_ports(ports)
    body = "\n".join(_render_port_task(name, items) for name in ("reg_port_chk", "ext_reg_port_chk"))
    return f"{_PORT_BEGIN}\n{body}{_PORT_END}\n"


def write_rffe_base_no_read(project, design):
    core = find_mipi_core(design)
    rffe = Path(project) / "sim_top" / "rffe_base.v"
    rffe.parent.mkdir(parents=True, exist_ok=True)
    if not rffe.is_file():
        rffe.write_bytes(_task_library().read_bytes())
    ports = parse_mipi_ports(core.read_text(encoding="utf-8", errors="replace"))
    original = rffe.read_bytes()
    text = original.decode("utf-8", errors="replace")
    text = _splice_instance(text, render_instance(ports))
    text = _splice_port_tasks(text, render_port_tasks(ports))
    _write_rffe(rffe, text, original)
    return core, rffe, ports


def _write_rffe(path, text, original):
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    data = text.replace("\r\n", "\n").encode("utf-8")
    if newline == b"\r\n":
        data = data.replace(b"\n", b"\r\n")
    path.write_bytes(data)


def _port_value_expr(name, width):
    bits = _width_bits(width) if width else 8
    if bits > 8:
        return f"{name}[7:0]"
    if bits < 8:
        return f"{{{(8 - bits)}'b0,{name}}}"
    return name


def _render_port_task(task_name, items):
    lines = [
        "//===========================================",
        f"// {task_name}",
        "//===========================================",
        f"task {task_name};",
        "input [7:0] sa;",
        "input [7:0] reg_addr;",
        "input [7:0] write_data;",
        "input [8:0] expect_data;",
        "reg [7:0] port_data;",
        "bit hit;",
        "    hit = 1'b0;",
        "    port_data = 8'h00;",
        "    case (reg_addr)",
    ]
    for addr, name, width in items:
        expr = _port_value_expr(name, width)
        lines.append(f"        8'h{addr:02x}: begin port_data = {expr}; hit = 1'b1; end")
    lines.extend([
        "        default: hit = 1'b0;",
        "    endcase",
        "    if (hit == 1'b0) begin",
        '        $display("************************************************");',
        '        $display("**   REG_ADDR        : \'h%2H", reg_addr);',
        '        $display("**   ERROR!!!  no output port                 ");',
        '        $display("************************************************");',
        "        err_cnt = err_cnt + 1;",
        "    end",
        "    else if (port_data !== expect_data[7:0]) begin",
        '        $display("************************************************");',
        '        $display("**   REG_ADDR        : \'h%2H", reg_addr);',
        '        $display("**   WRITE_DATA      : \'h%2H", write_data);',
        '        $display("**   IDEAL_DATA      : \'h%2H", expect_data[7:0]);',
        '        $display("**   PORT_DATA       : \'h%2H", port_data);',
        '        $display("**   ERROR!!!                                   ");',
        '        $display("************************************************");',
        "        err_cnt = err_cnt + 1;",
        "    end",
        "    else begin",
        '        $display("////////////////////////////////");',
        '        $display("//   REG_ADDR    : \'h%2H         ", reg_addr);',
        '        $display("//   WRITE_DATA  : \'h%2H         ", write_data);',
        '        $display("//   IDEAL_DATA  : \'h%2H         ", expect_data[7:0]);',
        '        $display("//   PORT_DATA   : \'h%2H         ", port_data);',
        '        $display("////////////////////////////////");',
        "    end",
        "endtask",
        "",
    ])
    return "\n".join(lines)


def _splice_port_tasks(text, block):
    start = text.find(_PORT_BEGIN)
    if start >= 0:
        end = text.find(_PORT_END, start)
        if end < 0:
            raise ValueError("rffe_base.v 里的 reg_port_chk 标记不完整")
        end = text.find("\n", end)
        end = len(text) if end < 0 else end + 1
        return text[:start] + block + text[end:]
    marker = text.find("mipi_core mipi_slave")
    if marker < 0:
        raise ValueError("rffe_base.v 里没有 mipi_core mipi_slave 实例")
    end = text.find(");", marker)
    if end < 0:
        raise ValueError("mipi_slave 实例没有结束")
    insert_at = end + 2
    if insert_at < len(text) and text[insert_at] == "\n":
        insert_at += 1
    return text[:insert_at] + block + text[insert_at:]


def _connect(name, direction, width):
    key = name.lower()
    if key in _KNOWN:
        return _KNOWN[key], False
    if key in {"vdd", "vcc", "vdda", "vdd_io"} or key.startswith("vdd"):
        return "1'b1", True
    if key in {"vss", "gnd", "vssa"} or key.startswith("vss"):
        return "1'b0", True
    if key.startswith("sclk"):
        return "sclk_test", False
    if "rst" in key:
        return "sys_rstn", False
    if key.startswith("sdata_in"):
        return "sdata_test", False
    if direction in {"output", "inout"}:
        return name, False
    return _tie_off(width), False


def _tie_off(width):
    bits = _width_bits(width)
    if bits <= 1:
        return "1'b0"
    return f"{bits}'b0"


def _wire(name, width):
    if width:
        return f"wire {width} {name};"
    return f"wire {name};"


def _width_bits(width):
    if not width:
        return 1
    match = re.fullmatch(r"\[(\d+)\s*:\s*(\d+)\]", width.strip())
    if not match:
        return 1
    return abs(int(match.group(1)) - int(match.group(2))) + 1


def _splice_instance(text, block):
    start = text.find("// Module Instance")
    if start < 0:
        raise ValueError("rffe_base.v 里没有 Module Instance 标记")
    banner = text.rfind("//====", 0, start)
    if banner < 0:
        banner = start
    inst = re.search(r"\bmipi_core\s+mipi_slave\b", text[start:])
    if not inst:
        raise ValueError("rffe_base.v 里没有 mipi_core mipi_slave 实例")
    inst_at = start + inst.start()
    end = text.find(");", inst_at)
    if end < 0:
        raise ValueError("mipi_slave 实例没有结束")
    return text[:banner] + block + text[end + 2:]


def _scan_paren(text, open_at):
    depth = 0
    index = open_at
    limit = len(text)
    while index < limit:
        if text.startswith("//", index):
            newline = text.find("\n", index)
            index = limit if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            close = text.find("*/", index + 2)
            index = limit if close < 0 else close + 2
            continue
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[open_at + 1:index], index + 1
        index += 1
    raise ValueError("模块端口列表没有结束")


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*?$", "", text, flags=re.M)


def _port_names(blob):
    names = []
    for part in _strip_comments(blob).replace("\n", " ").split(","):
        name = part.strip()
        if re.fullmatch(r"[A-Za-z_]\w*", name):
            names.append(name)
    return names


def _direction_hints(blob):
    hints = {}
    direction = "input"
    for raw in blob.splitlines():
        line = _strip_comments(raw)
        lower = raw.lower()
        if "output" in lower:
            direction = "output"
        elif "input" in lower:
            direction = "input"
        for part in line.split(","):
            name = part.strip()
            if re.fullmatch(r"[A-Za-z_]\w*", name):
                hints[name] = direction
    return hints


def _parse_decls(body):
    found = {}
    for match in _DECL.finditer(body):
        direction = match.group(1).lower()
        width = match.group(2)
        for part in _strip_comments(match.group(3)).split(","):
            name = part.split("=")[0].strip()
            if re.fullmatch(r"[A-Za-z_]\w*", name):
                found[name] = (direction, width)
    return found


def _parse_ansi(text):
    ports = []
    for chunk in text.split(","):
        piece = _strip_comments(chunk).strip()
        match = re.search(
            r"\b(input|output|inout)\b\s*(?:wire|reg|logic)?\s*(\[[^\]]+\])?\s*([A-Za-z_]\w*)",
            piece,
            re.I,
        )
        if not match:
            continue
        ports.append((match.group(3), match.group(1).lower(), match.group(2)))
    if not ports:
        raise ValueError("没有解析到 mipi_core 的端口")
    return ports


def _write_lf(path, text):
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))
