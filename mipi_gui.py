import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

import gen_sim_case
import sim_flow
import sim_top_gen


APP_DIR = Path(__file__).resolve().parent
DEFAULT_ENV = APP_DIR.parent / "python_sim_env"
SIM_MODES = ("sim", "sim_dc", "sim_post", "sim_post_max", "sim_post_min")

BRAND_ORANGE = "#e8890c"
BRAND_ORANGE_DARK = "#c56f08"
BG_COLOR = "#eef1f6"
SURFACE_COLOR = "#ffffff"
TEXT_COLOR = "#1c2430"
MUTED_COLOR = "#667085"
BORDER_COLOR = "#e4e7ec"
INK = "#111827"
LOG_BG = "#12161d"
LOG_FG = "#d7dde7"


def ui_family(root):
    families = set(tkfont.families(root))
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Micro Hei", "PingFang SC"):
        if name in families:
            return name
    return "TkDefaultFont"


def mono_family(root):
    families = set(tkfont.families(root))
    for name in ("Cascadia Mono", "Consolas", "Sarasa Mono SC", "Noto Sans Mono CJK SC", "DejaVu Sans Mono"):
        if name in families:
            return name
    return "TkFixedFont"


def default_project():
    if DEFAULT_ENV.is_dir():
        return DEFAULT_ENV
    return APP_DIR


_MARK = re.compile(r"单测 \S+|/[^\s]+|[A-Za-z]:[\\/][^\s]+")


def sim_folder_for_log(project, relative, mode):
    project = Path(project)
    log_file = project / relative
    if log_file.is_symlink() or log_file.is_file():
        resolved = log_file.resolve()
        if resolved.parent != (project / "all_sim_log").resolve() and resolved.parent.is_dir():
            return resolved.parent
    stem = Path(relative).stem
    order = (mode, *(item for item in SIM_MODES if item != mode))
    for item in order:
        folder = project.parent / item / stem
        if folder.is_dir():
            return folder
    return None


def open_folder(folder):
    folder = os.fspath(folder)
    if os.name == "nt":
        os.startfile(folder)
        return
    command = ["open", folder] if sys.platform == "darwin" else ["xdg-open", folder]
    subprocess.Popen(command)


def project_read_support(project):
    path = Path(project) / "read_support.txt"
    if path.is_file() and path.read_text(encoding="utf-8", errors="replace").strip().upper() == "NO":
        return "否"
    return "是"


def store_read_support(project, value):
    folder = Path(project)
    if not folder.is_dir():
        return
    text = "NO\n" if value == "否" else "YES\n"
    (folder / "read_support.txt").write_bytes(text.encode("utf-8"))


def ensure_project_dir(raw):
    text = str(raw).strip()
    if not text:
        raise ValueError("先填写要创建的工程目录。")
    folder = Path(text)
    if folder.is_file():
        raise FileExistsError(f"已有同名文件: {folder}")
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def clear_directory(folder):
    folder = Path(folder)
    for child in list(folder.iterdir()):
        if child.is_symlink() or not child.is_dir():
            child.unlink()
        else:
            shutil.rmtree(child)


def generate_cases(env_dir, register_file, read_supported=True, design=None):
    register_file = Path(register_file)
    if not register_file.is_file():
        raise FileNotFoundError(f"寄存器表不存在: {register_file}")
    env_dir = Path(env_dir)
    if not env_dir.is_dir():
        raise FileNotFoundError(f"工程目录不存在: {env_dir}")

    old_cwd = os.getcwd()
    try:
        os.chdir(env_dir)
        ports = []
        if not read_supported:
            core = sim_top_gen.find_mipi_core(design)
            parsed = sim_top_gen.parse_mipi_ports(core.read_text(encoding="utf-8", errors="replace"))
            ports = sim_top_gen.output_reg_addrs(parsed)
        output_dir = Path(gen_sim_case.generate_sim_cases(str(register_file), read_supported, ports))
    finally:
        os.chdir(old_cwd)

    names = [path.name for path in sorted(output_dir.glob("*.v"))]
    lines = [
        "激励已生成。",
        f"输出目录: {output_dir}",
        f"文件数量: {len(names)}",
    ]
    if names:
        lines.append("")
        lines.extend(names)
    return "\n".join(lines)


class MipiAutoVerifyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Lansus MIPI")
        self.root.geometry("1080x760")
        self.root.minsize(980, 680)
        self.root.configure(bg=BG_COLOR)
        self.font_name = ui_family(self.root)
        self.mono_name = mono_family(self.root)

        self.project_path = tk.StringVar(value=str(default_project()))
        self.register_path = tk.StringVar()
        self.design_path = tk.StringVar()
        self.mode_var = tk.StringVar(value=SIM_MODES[0])
        self.read_support = tk.StringVar(value=project_read_support(self.project_path.get()))
        self.status_var = tk.StringVar(value="就绪")
        self.active_controls = []

        self._build_ui()

    def _font(self, size=10, bold=False):
        return (self.font_name, size, "bold") if bold else (self.font_name, size)

    def _build_ui(self):
        self._configure_styles()
        shell = tk.Frame(self.root, bg=BG_COLOR)
        shell.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(2, weight=1)

        self._build_header(shell)
        card = tk.Frame(shell, bg=SURFACE_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.grid(row=1, column=0, sticky="ew")
        card.columnconfigure(1, weight=1)
        self._build_form(card)
        self._build_log(shell)

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Primary.TButton",
            font=self._font(10, True),
            padding=(14, 7),
            foreground="#ffffff",
            background=BRAND_ORANGE,
            bordercolor=BRAND_ORANGE,
            focusthickness=0,
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[("active", BRAND_ORANGE_DARK), ("disabled", "#f3c98a")],
            bordercolor=[("active", BRAND_ORANGE_DARK), ("disabled", "#f3c98a")],
            foreground=[("disabled", "#fff7eb")],
        )
        style.configure(
            "Secondary.TButton",
            font=self._font(10),
            padding=(12, 7),
            foreground=TEXT_COLOR,
            background="#f8fafc",
            bordercolor=BORDER_COLOR,
            focusthickness=0,
            relief="flat",
        )
        style.map("Secondary.TButton", background=[("active", "#eef2f6"), ("disabled", "#f8fafc")])
        style.configure(
            "Field.TEntry",
            padding=(8, 7),
            fieldbackground="#fbfcfe",
            bordercolor=BORDER_COLOR,
            lightcolor=BORDER_COLOR,
            darkcolor=BORDER_COLOR,
        )
        style.configure(
            "Field.TCombobox",
            padding=(8, 6),
            fieldbackground="#fbfcfe",
            bordercolor=BORDER_COLOR,
            arrowsize=14,
        )
        style.map("Field.TCombobox", fieldbackground=[("readonly", "#fbfcfe")])

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=INK)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)
        mark = tk.Canvas(header, width=36, height=36, bg=INK, highlightthickness=0)
        mark.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=14)
        mark.create_oval(2, 2, 34, 34, fill=BRAND_ORANGE, outline=BRAND_ORANGE)
        mark.create_text(18, 18, text="L", fill="#ffffff", font=self._font(14, True))
        tk.Label(header, text="Lansus MIPI", bg=INK, fg="#ffffff", font=self._font(18, True), anchor="w").grid(
            row=0, column=1, sticky="sw"
        )
        tk.Label(
            header,
            text="生成激励、仿真环境和日志检查",
            bg=INK,
            fg="#9aa3b2",
            font=self._font(10),
            anchor="w",
        ).grid(row=1, column=1, sticky="nw", pady=(0, 12))

    def _build_form(self, parent):
        self._section(parent, 0, "工程")
        self._field(
            parent,
            1,
            "工程目录",
            self.project_path,
            [("选择", self.select_project, "Secondary.TButton"), ("创建", self.create_project_dir, "Secondary.TButton")],
        )
        self._pair_row(parent, 2)
        self._section(parent, 3, "输入")
        self._field(
            parent,
            4,
            "寄存器表",
            self.register_path,
            [("选择", self.select_register_file, "Secondary.TButton"), ("生成激励", self.generate_cases, "Primary.TButton")],
        )
        self._field(
            parent,
            5,
            "设计路径",
            self.design_path,
            [
                ("目录", self.select_design_dir, "Secondary.TButton"),
                ("文件", self.select_design_file, "Secondary.TButton"),
                ("生成环境", self.generate_env, "Primary.TButton"),
            ],
        )
        actions = tk.Frame(parent, bg=SURFACE_COLOR)
        actions.grid(row=6, column=0, columnspan=3, sticky="ew", padx=22, pady=(4, 16))
        for text, command, style_name in (
            ("生成连接", self.generate_connections, "Secondary.TButton"),
            ("仿真配置", self.edit_sim_config, "Secondary.TButton"),
            ("生成 DET", self.generate_det, "Secondary.TButton"),
            ("运行仿真", self.run_sim, "Primary.TButton"),
            ("收集日志", self.collect_logs, "Primary.TButton"),
            ("检查日志", self.check_logs, "Primary.TButton"),
        ):
            button = ttk.Button(actions, text=text, command=command, style=style_name)
            button.pack(side=tk.LEFT, padx=(0, 8))
            self.active_controls.append(button)

    def _section(self, parent, row, text):
        tk.Label(
            parent,
            text=text,
            bg=SURFACE_COLOR,
            fg=MUTED_COLOR,
            font=self._font(9, True),
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", padx=22, pady=(14 if row else 16, 0))

    def _field(self, parent, row, label, variable, buttons):
        tk.Label(parent, text=label, bg=SURFACE_COLOR, fg=TEXT_COLOR, font=self._font(10), anchor="w", width=8).grid(
            row=row, column=0, sticky="w", padx=(22, 10), pady=6
        )
        entry = ttk.Entry(parent, textvariable=variable, style="Field.TEntry")
        entry.grid(row=row, column=1, sticky="ew", pady=6)
        self.active_controls.append(entry)
        box = tk.Frame(parent, bg=SURFACE_COLOR)
        box.grid(row=row, column=2, sticky="e", padx=(10, 22), pady=6)
        for text, command, style_name in buttons:
            button = ttk.Button(box, text=text, command=command, style=style_name)
            button.pack(side=tk.LEFT, padx=(6, 0))
            self.active_controls.append(button)

    def _pair_row(self, parent, row):
        wrap = tk.Frame(parent, bg=SURFACE_COLOR)
        wrap.grid(row=row, column=0, columnspan=3, sticky="ew", padx=22, pady=6)
        tk.Label(wrap, text="仿真模式", bg=SURFACE_COLOR, fg=TEXT_COLOR, font=self._font(10)).pack(side=tk.LEFT)
        mode = ttk.Combobox(wrap, textvariable=self.mode_var, values=SIM_MODES, state="readonly", width=16, style="Field.TCombobox")
        mode.pack(side=tk.LEFT, padx=(10, 28))
        tk.Label(wrap, text="支持读", bg=SURFACE_COLOR, fg=TEXT_COLOR, font=self._font(10)).pack(side=tk.LEFT)
        read = ttk.Combobox(wrap, textvariable=self.read_support, values=("是", "否"), state="readonly", width=8, style="Field.TCombobox")
        read.pack(side=tk.LEFT, padx=(10, 0))
        read.bind("<<ComboboxSelected>>", self._store_read_choice)
        self.active_controls.extend((mode, read))

    def _build_log(self, parent):
        frame = tk.Frame(parent, bg=SURFACE_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
        frame.grid(row=2, column=0, sticky="nsew", pady=(14, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        bar = tk.Frame(frame, bg=SURFACE_COLOR)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        tk.Label(bar, text="输出", bg=SURFACE_COLOR, fg=TEXT_COLOR, font=self._font(10, True)).pack(side=tk.LEFT, padx=16, pady=8)
        self.status_dot = tk.Canvas(bar, width=12, height=12, bg=SURFACE_COLOR, highlightthickness=0)
        self.status_dot.pack(side=tk.RIGHT, padx=(0, 8))
        self.status_dot_item = self.status_dot.create_oval(1, 1, 11, 11, fill=BRAND_ORANGE, outline=BRAND_ORANGE)
        tk.Label(bar, textvariable=self.status_var, bg=SURFACE_COLOR, fg=MUTED_COLOR, font=self._font(10)).pack(side=tk.RIGHT)
        self.result_text = tk.Text(
            frame,
            height=12,
            wrap=tk.WORD,
            font=(self.mono_name, 10),
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground="#ffffff",
            relief=tk.FLAT,
            borderwidth=0,
            padx=16,
            pady=12,
        )
        self.result_text.tag_configure("loglink", foreground="#7dd3fc", underline=True)
        self.result_text.tag_configure("retest", foreground="#f5c16c", underline=True)
        for tag, handler in (("loglink", self._open_log_link), ("retest", self._rerun_case)):
            self.result_text.tag_bind(tag, "<Button-1>", handler)
            self.result_text.tag_bind(tag, "<Enter>", lambda event: self.result_text.configure(cursor="hand2"))
            self.result_text.tag_bind(tag, "<Leave>", lambda event: self.result_text.configure(cursor=""))
        self.result_text.grid(row=1, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=self.result_text.yview)
        scroll.grid(row=1, column=1, sticky="ns")
        self.result_text.configure(yscrollcommand=scroll.set)

    def _store_read_choice(self, _event=None):
        store_read_support(self.project_path.get(), self.read_support.get())

    def _reload_read_choice(self, folder):
        self.read_support.set(project_read_support(folder))

    def select_project(self):
        current = self.project_path.get().strip()
        initial = current if Path(current).is_dir() else str(APP_DIR)
        path = filedialog.askdirectory(title="选择 python_sim_env 目录", initialdir=initial)
        if not path:
            return
        folder = Path(path)
        if any(folder.iterdir()):
            if not messagebox.askokcancel("工程目录", f"将清空目录中的全部内容:\n{folder}"):
                return
            try:
                clear_directory(folder)
            except OSError as exc:
                messagebox.showerror("工程目录", str(exc))
                return
            self._set_status(f"已清空工程目录: {folder}", "#22c55e")
        self.project_path.set(str(folder))
        if (folder / "read_support.txt").is_file():
            self._reload_read_choice(folder)
        else:
            store_read_support(folder, self.read_support.get())

    def create_project_dir(self):
        try:
            folder = ensure_project_dir(self.project_path.get())
        except (ValueError, FileExistsError, OSError) as exc:
            messagebox.showerror("工程目录", str(exc))
            return
        self.project_path.set(str(folder))
        store_read_support(folder, self.read_support.get())
        self._set_status(f"工程目录已就绪: {folder}", "#22c55e")

    def select_register_file(self):
        path = filedialog.askopenfilename(
            title="选择寄存器表",
            initialdir=self.project_path.get() or str(APP_DIR),
            filetypes=(("Excel files", "*.xls *.xlsx"), ("All files", "*.*")),
        )
        if path:
            self.register_path.set(path)

    def select_design_dir(self):
        path = filedialog.askdirectory(title="选择设计目录", initialdir=self.project_path.get() or str(APP_DIR))
        if path:
            self.design_path.set(path)

    def select_design_file(self):
        current = self.design_path.get().strip()
        initial = self.project_path.get() or str(APP_DIR)
        if current:
            parent = Path(current.split(os.pathsep)[0]).parent
            if parent.is_dir():
                initial = str(parent)
        paths = filedialog.askopenfilenames(
            title="选择设计或库文件，可多选",
            initialdir=initial,
            filetypes=(("Verilog / library", "*.v *.sv *.lib"), ("All files", "*.*")),
        )
        if paths:
            self.design_path.set(os.pathsep.join(paths))

    def generate_cases(self):
        project = self.project_path.get().strip()
        register = self.register_path.get().strip()
        if not register:
            messagebox.showerror("缺少寄存器表", "先选择寄存器 Excel。")
            return
        read_yes = self.read_support.get() != "否"
        design = self.design_path.get().strip()
        if not read_yes and not design:
            messagebox.showerror("缺少设计路径", "不支持读时先填写设计路径，用来确定 regXX 输出。")
            return
        self._store_read_choice()
        self._start("正在生成激励...", lambda: generate_cases(project, register, read_yes, design))

    def generate_env(self):
        project = self.project_path.get().strip()
        mode = self.mode_var.get().strip()
        design = self.design_path.get().strip()
        if not design:
            messagebox.showerror("缺少设计路径", "先选择设计目录或后仿真文件。")
            return
        if not messagebox.askokcancel("生成环境", f"将清空上一级目录中的 {mode}，然后重新生成用例。"):
            return
        self._start("正在生成环境...", lambda: sim_flow.generate_env(project, mode, design))

    def generate_connections(self):
        project = self.project_path.get().strip()
        design = self.design_path.get().strip()
        if not project or not design:
            messagebox.showerror("生成连接", "先填写工程目录和设计路径。")
            return
        self._start("正在生成连接...", lambda: self._write_connections(project, design))

    def _write_connections(self, project, design):
        self._store_read_choice()
        if self.read_support.get() == "否":
            core, rffe, ports = sim_top_gen.write_rffe_base_no_read(project, design)
        else:
            core, rffe, ports = sim_top_gen.update_rffe_instance(project, design)
        config = Path(project) / "sim_top" / "sim_config.v"
        if not config.is_file():
            sim_top_gen.write_sim_config(project, sim_top_gen.default_sim_config())
        lines = [
            f"已更新 {rffe}",
            f"设计文件: {core}",
            f"端口数量: {len(ports)}",
        ]
        lines.extend(f"{name} ({direction})" for name, direction, _width in ports)
        return "\n".join(lines)

    def edit_sim_config(self):
        project = self.project_path.get().strip()
        if not project:
            messagebox.showerror("仿真配置", "先填写工程目录。")
            return
        folder = Path(project)
        if not folder.is_dir():
            messagebox.showerror("仿真配置", f"工程目录不存在: {folder}")
            return
        current = sim_top_gen.load_sim_config(folder / "sim_top" / "sim_config.v")
        edited = self._ask_sim_config(current)
        if edited is None:
            return
        path = sim_top_gen.write_sim_config(folder, edited)
        self._append_result(f"已写入 {path}\n")
        self._set_status("仿真配置已保存", "#22c55e")

    def _ask_sim_config(self, values):
        dialog = tk.Toplevel(self.root)
        dialog.title("仿真配置")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=BG_COLOR)
        body = tk.Frame(dialog, bg=SURFACE_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        fields = {}
        for index, (name, _default) in enumerate(sim_top_gen.SIM_CONFIG_FIELDS):
            row, column = divmod(index, 2)
            tk.Label(body, text=name, bg=SURFACE_COLOR, fg=MUTED_COLOR, anchor="w", font=self._font(9)).grid(
                row=row, column=column * 2, sticky="w", padx=(16, 8), pady=(10, 0)
            )
            variable = tk.StringVar(value=values.get(name, _default))
            entry = ttk.Entry(body, textvariable=variable, width=22, style="Field.TEntry")
            entry.grid(row=row, column=column * 2 + 1, sticky="ew", padx=(0, 16), pady=(10, 0))
            fields[name] = variable
        for column in (1, 3):
            body.columnconfigure(column, weight=1)
        chosen = {"values": None}

        def save():
            result = {}
            for name, variable in fields.items():
                text = variable.get().strip()
                if not text:
                    messagebox.showerror("仿真配置", f"{name} 不能为空。", parent=dialog)
                    return
                result[name] = text
            chosen["values"] = result
            dialog.destroy()

        buttons = tk.Frame(body, bg=SURFACE_COLOR)
        buttons.grid(row=8, column=0, columnspan=4, sticky="e", padx=16, pady=16)
        ttk.Button(buttons, text="取消", command=dialog.destroy, style="Secondary.TButton").pack(side=tk.RIGHT)
        ttk.Button(buttons, text="保存", command=save, style="Primary.TButton").pack(side=tk.RIGHT, padx=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.wait_window()
        return chosen["values"]

    def generate_det(self):
        project = self.project_path.get().strip()
        self._start("正在生成 DET...", lambda: sim_flow.generate_det(project))

    def run_sim(self):
        project = self.project_path.get().strip()
        mode = self.mode_var.get().strip()
        self._start("正在启动仿真...", lambda: sim_flow.run_sim(project, mode))

    def collect_logs(self):
        project = self.project_path.get().strip()
        mode = self.mode_var.get().strip()
        self._start("正在收集日志...", lambda: sim_flow.collect_logs(project, mode))

    def check_logs(self):
        project = self.project_path.get().strip()
        mode = self.mode_var.get().strip()
        self._start("正在检查日志...", lambda: sim_flow.check_logs(project, mode))

    def _start(self, status, work):
        self._set_busy(True)
        self._clear_result()
        self._set_status(status, BRAND_ORANGE)
        threading.Thread(target=self._guard, args=(work,), daemon=True).start()

    def _guard(self, work):
        try:
            message = work()
        except Exception as exc:
            self.root.after(0, self._finish_error, str(exc))
            return
        self.root.after(0, self._finish_success, message)

    def _finish_success(self, message):
        self._append_result(message + "\n")
        self._set_busy(False)
        self._set_status("完成", "#22c55e")

    def _finish_error(self, error):
        self._append_result(error + "\n")
        self._set_busy(False)
        self._set_status("失败", "#ef4444")
        messagebox.showerror("失败", error)

    def _set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for widget in self.active_controls:
            if isinstance(widget, ttk.Combobox) and not busy:
                widget.configure(state="readonly")
            else:
                widget.configure(state=state)

    def _set_status(self, text, color):
        self.status_var.set(text)
        self.status_dot.itemconfigure(self.status_dot_item, fill=color, outline=color)

    def _clear_result(self):
        self.result_text.delete("1.0", tk.END)

    def _append_result(self, text):
        for line in text.splitlines(keepends=True):
            cursor = 0
            for match in _MARK.finditer(line):
                self.result_text.insert(tk.END, line[cursor:match.start()])
                tag = "retest" if match.group(0).startswith("单测") else "loglink"
                self.result_text.insert(tk.END, match.group(0), tag)
                cursor = match.end()
            self.result_text.insert(tk.END, line[cursor:])
        self.result_text.see(tk.END)

    def _mark_at(self, event, tag):
        index = self.result_text.index(f"@{event.x},{event.y}")
        ranges = self.result_text.tag_ranges(tag)
        for start, end in zip(ranges[0::2], ranges[1::2]):
            if self.result_text.compare(start, "<=", index) and self.result_text.compare(index, "<", end):
                return self.result_text.get(start, end)
        return None

    def _open_log_link(self, event):
        text = self._mark_at(event, "loglink")
        if text is None:
            return
        path = Path(text)
        if not path.is_absolute():
            folder = sim_folder_for_log(
                self.project_path.get().strip(),
                text,
                self.mode_var.get().strip(),
            )
            path = folder if folder is not None else path
        if path.is_file():
            path = path.parent
        try:
            open_folder(path)
        except OSError as exc:
            messagebox.showerror("仿真目录", f"无法打开: {path}\n{exc}")
        return "break"

    def _rerun_case(self, event):
        text = self._mark_at(event, "retest")
        if text is None:
            return "break"
        name = text.split()[-1]
        project = self.project_path.get().strip()
        mode = self.mode_var.get().strip()
        self._start(f"正在单测 {name}...", lambda: sim_flow.run_sim(project, mode, name))
        return "break"


def main():
    root = tk.Tk()
    MipiAutoVerifyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
