import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


MODES = ("sim", "sim_dc", "sim_post", "sim_post_max", "sim_post_min")

MAKEFILE = (
    '.PHONY: all com sim cov clean debug debug_dve \n'
    '\n'
    'OUTPUT = simv\n'
    'ALL_DEFINE = +define+DUMP_VPD\n'
    '\n'
    '# Code coverage command\n'
    'CM = -cm line+cond+fsm+branch+tgl\n'
    'CM_NAME = -cm_name $(OUTPUT)\n'
    'CN_DIR = -cm_dir ./$(OUTPUT).vdb\n'
    '\n'
    '#vpd file name\n'
    'VPD_NAME = +vpdfile+$(OUTPUT).vpd\n'
    '\n'
    '#Compile command\n'
    '#VCS = vcs +v2k -timescale=1ns/1ns\n'
    'VCS = vcs +v2k -timescale=1ns/1ns\\\n'
    '       -sverilog\\\n'
    '       -full64\\\n'
    '\t\t\t +define+{sim_define}\\\n'
    '       -fsdb\\\n'
    '       -debug_all\\\n'
    '\t\t\t +lint=TFIPC-L\\\n'
    '       +nospecify\\\n'
    '       +vcs+flush+all\\\n'
    '       $(CM)\\\n'
    '       $(CM_NAME)\\\n'
    '       $(DM_DIR)\\\n'
    '       $(ALL_DEFINE)\\\n'
    '       $(VPD_NAME)\\\n'
    '       -o $(OUTPUT)\\\n'
    '       -l compile.log \n'
    '\n'
    '#simulation command\n'
    'SIM = ./$(OUTPUT)\\\n'
    '       +ntb_ramdom_seend_automatic\\\n'
    '       $(CM)\\\n'
    '       $(CM_NAME)\\\n'
    '       $(DM_DIR)\\\n'
    '       $(ALL_DEFINE)\\\n'
    '       -l {case}.log \n'
    '\n'
    '\n'
    'VCS_MIN = vcs +v2k -timescale=1ns/1ns\\\n'
    '       -sverilog\\\n'
    '       -full64\\\n'
    '       -fsdb\\\n'
    '       -debug_all\\\n'
    '\t\t\t +lint=TFIPC-L\\\n'
    '       $(CM)\\\n'
    '       $(CM_NAME)\\\n'
    '       $(DM_DIR)\\\n'
    '       $(ALL_DEFINE)\\\n'
    '       $(VPD_NAME)\\\n'
    '       -o $(OUTPUT)\\\n'
    '       -l compile.log\\\n'
    '\t\t   +incdir\\\n'
    '\t\t   -negdelay\\\n'
    '\t\t   +neg_tchk\\\n'
    '\t\t   +mindelays\\\n'
    '\t\t   +sdfverbose+notifier\n'
    '\n'
    '\n'
    'VCS_MAX = vcs +v2k -timescale=1ns/1ns\\\n'
    '       -sverilog\\\n'
    '       -full64\\\n'
    '       -fsdb\\\n'
    '       -debug_all\\\n'
    '\t\t\t +lint=TFIPC-L\\\n'
    '       $(CM)\\\n'
    '       $(CM_NAME)\\\n'
    '       $(DM_DIR)\\\n'
    '       $(ALL_DEFINE)\\\n'
    '       $(VPD_NAME)\\\n'
    '       -o $(OUTPUT)\\\n'
    '       -l compile.log\\\n'
    '\t\t   +incdir\\\n'
    '\t\t   -negdelay\\\n'
    '\t\t   +neg_tchk\\\n'
    '\t\t   +maxdelays\\\n'
    '\t\t   +sdfverbose+notifier\n'
    '\n'
    '\n'
    '\n'
    '#clean\n'
    'CLEAN =\trm -rf ./csrc *.daidir ./csrc\\\n'
    '\t*.log *.vpd *.vdb simv* *.key\\\n'
    '\t+race.out*  *fsdb \n'
    '\n'
    '# Start clean + compile + sim\n'
    'all:\n'
    '\t$(VCS) -f filelist/filelist.f \n'
    '\t$(SIM)\n'
    '\t\n'
    '\t\n'
    'all_max:\n'
    '\t$(VCS_MAX) -f filelist/filelist.f  -j10\n'
    '\t$(SIM)\n'
    '\t\n'
    'all_min:\n'
    '\t$(VCS_MIN) -f filelist/filelist.f -j10 \n'
    '\t$(SIM)\n'
    '\t\n'
    '\n'
    '# Start compile\n'
    'com: \n'
    '\t$(VCS) -f filelist/filelist.f \n'
    '\n'
    '# Start simulation\n'
    'sim:\n'
    '\t$(SIM)\n'
    '\n'
    '#show the coverage\n'
    'cov:\n'
    '\tdve -covdir *vdb &\n'
    '\n'
    'debug:\n'
    '\tverdi -f filelist/filelist.f -ssf tb_xx.fsdb -nologo &\n'
    'debug_dve:\n'
    '\tdve -full64 -vpd tb_xx.vcd &\n'
    '\n'
    '# \n'
    '\n'
    '# Start clean\n'
    'clean:\n'
    '\t$(CLEAN)\n'
    '\n'
)

SIM_TOP = "task sim_top;\n   #1000;\n   cmd_cnt = 0;\n   {task}\nendtask\n\n"

MAIN = (
    "\n////////// Main Sim //////////\n"
    "initial begin\n"
    "  err_cnt = 0;\n"
    "  @(posedge sys_rstn);\n"
    "  sim_top;\n"
    "  if(err_cnt != 0)\n"
    "    disp_fail;\n"
    "  else\n"
    "    disp_pass;\n"
    "end\n"
    "endmodule\n"
)

SDF = {
    "sim_dc": (
        "initial begin\n"
        "`ifdef FUNCTIONAL\n"
        '\t$display("No SDF ");\n'
        "`else\n"
        '\t$sdf_annotate("../../dc/mipi_core_dc21.sdf",tb_new.mipi_slave);\n'
        "`endif\n"
        "end\n"
    ),
    "sim_post": (
        "\ninitial begin\n"
        "`ifdef FUNCTIONAL\n"
        '\t$display("No SDF ");\n'
        "`else\n"
        '\t$sdf_annotate("../../sta/STA_scernario_by_scernario/run_func_wc_cmax125/tmp/mipi_slave_max_30.sdf",tb_new.mipi_slave);\n'
        "`endif\n"
        "end\n"
    ),
    "sim_post_max": (
        "\ninitial begin\n"
        "`ifdef FUNCTIONAL\n"
        '\t$display("No SDF ");\n'
        "`else\n"
        '\t$sdf_annotate("../../sta/STA_scernario_by_scernario/run_func_wc_cmax125/tmp/mipi_slave_max_30.sdf",tb_new.mipi_slave);\n'
        "`endif\n"
        "end\n\n"
    ),
    "sim_post_min": (
        "\ninitial begin\n"
        "`ifdef FUNCTIONAL\n"
        '\t$display("No SDF ");\n'
        "`else\n"
        '\t$sdf_annotate("../../sta/STA_scernario_by_scernario/run_func_bc_cminm40/tmp/mipi_slave_min_30.sdf",tb_new.mipi_slave);\n'
        "`endif\n"
        "end\n"
    ),
}


def make_target(mode):
    if mode == "sim_post_max":
        return "all_max"
    if mode == "sim_post_min":
        return "all_min"
    return "all"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _symlink(target, directory):
    directory.mkdir(parents=True, exist_ok=True)
    dest = directory / Path(str(target).replace("\\", "/")).name
    if dest.is_symlink() or dest.exists():
        dest.unlink()
    try:
        os.symlink(target, dest)
    except OSError:
        source = Path(target)
        if not source.is_absolute():
            source = directory / target
        shutil.copy2(source, dest)


def _reset_dir(path):
    if path.exists():
        for child in list(path.iterdir()):
            if child.is_symlink() or child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
    else:
        path.mkdir(parents=True)


def _mipi_names(design):
    if design.is_file():
        name = design.name
        if name.startswith("mipi") and name.endswith(".v"):
            return [name]
        return []
    names = []

    def walk(folder):
        entries = list(os.scandir(folder))
        for entry in entries:
            if entry.is_file(follow_symlinks=False) and entry.name.startswith("mipi") and entry.name.endswith(".v"):
                names.append(entry.name)
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                walk(entry.path)

    walk(design)
    return names


def _filelist(mode, design):
    if mode == "sim":
        text = (
            "\n\n//SIM TOP        \n"
            "./sim_top/tb_mipi_master.v \n"
            "\n//RTL file list\n"
            "\n//-------------MIPI SLAVE---\n"
        )
        for name in _mipi_names(design):
            text += "\n../../src/slave/" + name
        return text + "\n"
    if mode == "sim_dc":
        return (
            "\n//SIM TOP        \n"
            "./sim_top/tb_mipi_master.v \n"
            "//-------------MIPI SLAVE---\n"
            f"../../src/slave/{design.name}\n"
            "../../dc/output_data/mipi_core.mapped.v\n\n"
        )
    return (
        "\n//SIM TOP        \n"
        "./sim_top/tb_mipi_master.v \n"
        "//-------------MIPI SLAVE---\n"
        f"../../src/slave/{design.name}\n"
        "../../innovus_pnr/work/mipi_core_pr.v\n"
    )


def _testbench(stamp, includes, mode):
    return (
        "`timescale 1ns/1ps\n"
        "//==================================================================\n"
        "// Created by           :Dong Tao\n"
        "// Filename             :tb_mipi_master.v\n"
        "// Author               :Dong Tao\n"
        f"// Created On           :{stamp}\n"
        f"// Last Modified        :{stamp}\n"
        "// Update Count         :1\n"
        "// Description          :sim_env\n"
        "//==================================================================\n"
        "`define FSDB\n"
        "///////////////////////////\n"
        "//  instance file path   //\n"
        "///////////////////////////\n"
        "module tb_new();\n"
        '`include "sim_top/sim_config.v"\n'
        '`include "sim_top/rffe_base.v"\n'
        f"{includes}\n"
        '`include "sim_top/sim_top.v"\n'
        f"{SDF.get(mode, '')}{MAIN}\n"
    )


def generate_env(env_dir, mode, design):
    env_dir = Path(env_dir)
    if mode not in MODES:
        raise ValueError(f"未知模式: {mode}")
    if not env_dir.is_dir():
        raise FileNotFoundError(f"工程目录不存在: {env_dir}")
    design = Path(design).resolve()
    if not design.exists():
        raise FileNotFoundError(f"设计路径不存在: {design}")
    cases = sorted((env_dir / "sim_case_list").glob("*.v"))
    if not cases:
        raise FileNotFoundError(f"没有用例: {env_dir / 'sim_case_list'}")

    sim_dir = env_dir.parent / mode
    _reset_dir(sim_dir)
    if (env_dir / "sim_case_list" / "all_sim_file.v").is_file():
        folder = sim_dir / "all_sim_file" / "sim_top"
        for case in cases:
            _symlink(str(case.resolve()), folder)

    for case in cases:
        if case.name == "all_sim_file.v":
            continue
        folder = sim_dir / case.stem / "sim_top"
        folder.mkdir(parents=True, exist_ok=True)
        _symlink(f"../../../python_sim_env/sim_case_list/{case.name}", folder)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    filelist = _filelist(mode, design)
    includes = "".join(f'`include "sim_top/{case.stem}.v"\n' for case in cases)
    for folder in [path for path in sim_dir.iterdir() if path.is_dir()]:
        if folder.name == "all_sim_file":
            specific = includes
            task = "sim_all_function;"
        else:
            specific = f'`include "sim_top/{folder.name}.v"'
            task = f"{folder.name};"
        top = folder / "sim_top"
        _write(top / "tb_mipi_master.v", _testbench(stamp, specific, mode))
        _write(top / "sim_top.v", SIM_TOP.format(task=task))
        sim_define = "PRE_SIM" if mode == "sim" else "POST_SIM"
        _write(folder / "makefile", "".join(MAKEFILE).format(case=folder.name, sim_define=sim_define))
        _write(folder / "filelist" / "filelist.f", filelist)
        _symlink("../../../python_sim_env/sim_top/sim_config.v", top)
        _symlink("../../../python_sim_env/sim_top/rffe_base.v", top)

    names = sorted(path.name for path in sim_dir.iterdir() if path.is_dir())
    return "\n".join([f"仿真目录: {sim_dir}", f"用例数量: {len(names)}", *names])


def collect_logs(env_dir, mode):
    env_dir = Path(env_dir)
    if mode not in MODES:
        mode = "sim"
    mode_dir = env_dir.parent / mode
    if not mode_dir.is_dir():
        raise FileNotFoundError(f"仿真目录不存在: {mode_dir}")
    dest = env_dir / "all_sim_log"
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.is_dir():
        shutil.rmtree(dest)
    dest.mkdir()
    lines = []
    for case in sorted(path for path in mode_dir.iterdir() if path.is_dir()):
        log_file = case / f"{case.name}.log"
        if log_file.is_file():
            _symlink(str(log_file.resolve()), dest)
            lines.append(f"linked {case.name}.log")
        else:
            lines.append(f"no file {case.name}.log")
    lines.append("finished!!!")
    return "\n".join(lines)


def check_logs(env_dir):
    env_dir = Path(env_dir)
    lines = []
    total = 0
    log_dir = env_dir / "all_sim_log"
    if log_dir.is_dir():
        for log_file in sorted(log_dir.glob("*.log")):
            if not log_file.is_file():
                continue
            count = sum(
                1
                for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines()
                if "ERROR!!!" in line
            )
            if count:
                total += count
                lines.append(f"ERROR found in: all_sim_log/{log_file.name} (count:{count})")
    part = ""
    for path in sorted(env_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in {".xls", ".xlsx"}:
            part = path.name.split("_", 1)[0]
    lines.extend([
        "*************************************",
        f"VER_PROJECT: {part}",
        "VER_AUTHOR: DongTao",
        f"VER_DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"ALL_ERR_CNT: {total}",
        "*************************************",
    ])
    return "\n".join(lines)


def run_sim(env_dir, mode):
    if mode not in MODES:
        mode = "sim"
    sim_dir = Path(env_dir).resolve().parent / mode
    if not sim_dir.is_dir():
        raise FileNotFoundError(f"仿真目录不存在: {sim_dir}")
    folders = [path for path in sim_dir.iterdir() if path.is_dir()]
    if not folders:
        raise FileNotFoundError(f"没有仿真用例目录: {sim_dir}")
    target = make_target(mode)
    gnome = shutil.which("gnome-terminal")
    lines = []
    for folder in folders:
        lines.append(f"Launching: {folder.name} ({target})")
        if gnome:
            subprocess.Popen(
                [gnome, f"--working-directory={folder}", "--", "/bin/bash", "-c", f"make {target}"],
            )
            continue
        try:
            subprocess.run(["make", target], cwd=folder, check=True)
        except FileNotFoundError as exc:
            raise RuntimeError("当前系统没有 make。仿真需要在 Linux 上运行。") from exc
    lines.extend(["------------------------------------------------------", "All terminals launched."])
    return "\n".join(lines)


def generate_det(env_dir):
    env_dir = Path(env_dir)
    script = env_dir / "gen_sim_det.py"
    if not script.is_file():
        raise FileNotFoundError(f"找不到脚本: {script}")
    spec = importlib.util.spec_from_file_location("gen_sim_det_flow", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = io.StringIO()
    old_cwd = os.getcwd()
    try:
        os.chdir(env_dir)
        with contextlib.redirect_stdout(output):
            code = module.main()
    finally:
        os.chdir(old_cwd)
    if code:
        detail = output.getvalue().strip() or "生成 DET 失败"
        raise RuntimeError(detail)
    return output.getvalue().strip() or "已生成 sim_det_function.v"
