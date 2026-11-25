import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import gen_sim_case
import sim_flow


APP_DIR = Path(__file__).resolve().parent
DEFAULT_ENV = APP_DIR.parent / "python_sim_env"
SIM_MODES = ("sim", "sim_dc", "sim_post", "sim_post_max", "sim_post_min")

BRAND_ORANGE = "#f5a623"
BRAND_ORANGE_DARK = "#d98200"
BG_COLOR = "#f4f6fa"
SURFACE_COLOR = "#ffffff"
TEXT_COLOR = "#1f2937"
MUTED_COLOR = "#6b7280"
BORDER_COLOR = "#d7dde8"


def default_project():
    if DEFAULT_ENV.is_dir():
        return DEFAULT_ENV
    return APP_DIR


def generate_cases(env_dir, register_file):
    register_file = Path(register_file)
    if not register_file.is_file():
        raise FileNotFoundError(f"寄存器表不存在: {register_file}")
    env_dir = Path(env_dir)
    if not env_dir.is_dir():
        raise FileNotFoundError(f"工程目录不存在: {env_dir}")

    old_cwd = os.getcwd()
    try:
        os.chdir(env_dir)
        output_dir = Path(gen_sim_case.generate_sim_cases(str(register_file)))
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
        self.root.title("Lansus MIPI Verification Platform")
        self.root.geometry("1080x760")
        self.root.minsize(960, 640)

        self.project_path = tk.StringVar(value=str(default_project()))
        self.register_path = tk.StringVar()
        self.design_path = tk.StringVar()
        self.mode_var = tk.StringVar(value=SIM_MODES[0])
        self.status_var = tk.StringVar(value="就绪")
        self.active_controls = []

        self._build_ui()

    def _build_ui(self):
        self.root.configure(bg=BG_COLOR)
        self._configure_styles()

        shell = tk.Frame(self.root, bg=BG_COLOR)
        shell.pack(fill=tk.BOTH, expand=True, padx=34, pady=22)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        self._build_header(shell)
        self._build_main_panel(shell)

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "Primary.TButton",
            font=("TkDefaultFont", 10, "bold"),
            padding=(14, 8),
            foreground="#ffffff",
            background=BRAND_ORANGE,
            bordercolor=BRAND_ORANGE,
            focusthickness=0,
        )
        style.map(
            "Primary.TButton",
            background=[("active", BRAND_ORANGE_DARK), ("disabled", "#f2c979")],
            bordercolor=[("active", BRAND_ORANGE_DARK)],
        )
        style.configure(
            "Secondary.TButton",
            font=("TkDefaultFont", 10),
            padding=(12, 8),
            foreground=TEXT_COLOR,
            background="#f8fafc",
            bordercolor=BORDER_COLOR,
            focusthickness=0,
        )
        style.map("Secondary.TButton", background=[("active", "#edf2f7")])
        style.configure("Field.TEntry", padding=(10, 8), fieldbackground="#ffffff")
        style.configure("Field.TCombobox", padding=(10, 6), fieldbackground="#ffffff")

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=BG_COLOR)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(1, weight=1)

        logo = tk.Canvas(header, width=150, height=46, bg=BG_COLOR, highlightthickness=0)
        logo.grid(row=0, column=0, sticky="w")
        logo.create_oval(2, 7, 36, 41, fill=BRAND_ORANGE, outline=BRAND_ORANGE)
        logo.create_text(19, 24, text="L", fill="#ffffff", font=("TkDefaultFont", 18, "bold"))
        logo.create_text(
            86,
            23,
            text="Lansus",
            fill=BRAND_ORANGE_DARK,
            font=("TkDefaultFont", 22, "bold"),
        )

        title_box = tk.Frame(header, bg=BG_COLOR)
        title_box.grid(row=0, column=1, sticky="ew", padx=(18, 0))
        title_box.columnconfigure(0, weight=1)
        tk.Label(
            title_box,
            text="MIPI Automated Verification Platform",
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            font=("TkDefaultFont", 22, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            title_box,
            text="在软件内生成激励、DET 和仿真环境，并收集、检查日志。",
            bg=BG_COLOR,
            fg=MUTED_COLOR,
            font=("TkDefaultFont", 11),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

    def _build_main_panel(self, parent):
        panel = tk.Frame(parent, bg=SURFACE_COLOR, highlightbackground=BORDER_COLOR, highlightthickness=1)
        panel.grid(row=1, column=0, sticky="nsew")
        panel.columnconfigure(1, weight=1)

        self._add_section_title(panel, 0, "工程")
        self._add_entry_row(panel, 1, "工程目录", self.project_path, [("选择", self.select_project, "Secondary.TButton")])
        self._add_mode_row(panel, 2)

        self._add_section_title(panel, 3, "流程")
        self._add_entry_row(
            panel,
            4,
            "寄存器表",
            self.register_path,
            [
                ("选择", self.select_register_file, "Secondary.TButton"),
                ("1 生成激励", self.generate_cases, "Primary.TButton"),
            ],
        )
        self._add_entry_row(
            panel,
            5,
            "设计路径",
            self.design_path,
            [
                ("目录", self.select_design_dir, "Secondary.TButton"),
                ("文件", self.select_design_file, "Secondary.TButton"),
                ("2 生成环境", self.generate_env, "Primary.TButton"),
            ],
        )

        actions = tk.Frame(panel, bg=SURFACE_COLOR)
        actions.grid(row=6, column=0, columnspan=3, sticky="nw", padx=34, pady=(8, 0))
        for text, command in (
            ("生成 DET", self.generate_det),
            ("3 运行仿真", self.run_sim),
            ("4 收集日志", self.collect_logs),
            ("5 检查日志", self.check_logs),
        ):
            button = ttk.Button(actions, text=text, command=command, style="Primary.TButton")
            button.pack(side=tk.LEFT, padx=(0, 10))
            self.active_controls.append(button)

        self._add_result(panel, 7)
        self._add_status_row(panel, 8)

    def _add_section_title(self, parent, row, text):
        tk.Label(
            parent,
            text=text,
            bg=SURFACE_COLOR,
            fg=BRAND_ORANGE_DARK,
            font=("TkDefaultFont", 12, "bold"),
            anchor="w",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", padx=34, pady=(16 if row else 18, 4))

    def _add_label(self, parent, row, text):
        tk.Label(
            parent,
            text=text,
            bg=SURFACE_COLOR,
            fg=TEXT_COLOR,
            font=("TkDefaultFont", 11, "bold"),
            anchor="w",
        ).grid(row=row, column=0, sticky="ew", padx=(34, 18), pady=8)

    def _add_entry_row(self, parent, row, label, variable, buttons):
        self._add_label(parent, row, label)
        entry = ttk.Entry(parent, textvariable=variable, style="Field.TEntry")
        entry.grid(row=row, column=1, sticky="ew", pady=8)
        self.active_controls.append(entry)

        box = tk.Frame(parent, bg=SURFACE_COLOR)
        box.grid(row=row, column=2, sticky="e", padx=(12, 34), pady=8)
        for text, command, style_name in buttons:
            button = ttk.Button(box, text=text, command=command, style=style_name)
            button.pack(side=tk.LEFT, padx=(8, 0))
            self.active_controls.append(button)

    def _add_mode_row(self, parent, row):
        self._add_label(parent, row, "仿真模式")
        combo = ttk.Combobox(
            parent,
            textvariable=self.mode_var,
            values=SIM_MODES,
            state="readonly",
            style="Field.TCombobox",
        )
        combo.grid(row=row, column=1, sticky="ew", pady=8)
        self.active_controls.append(combo)

    def _add_result(self, parent, row):
        frame = tk.Frame(parent, bg=SURFACE_COLOR)
        frame.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=34, pady=(12, 0))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)

        self.result_text = tk.Text(
            frame,
            height=12,
            wrap=tk.WORD,
            font=("TkFixedFont", 10),
            bg="#0f172a",
            fg="#e5e7eb",
            insertbackground="#ffffff",
            relief=tk.FLAT,
            borderwidth=0,
            padx=14,
            pady=12,
        )
        self.result_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(frame, command=self.result_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.result_text.configure(yscrollcommand=scroll.set)

    def _add_status_row(self, parent, row):
        status_box = tk.Frame(parent, bg=SURFACE_COLOR)
        status_box.grid(row=row, column=0, columnspan=3, sticky="ew", padx=34, pady=(12, 18))
        self.status_dot = tk.Canvas(status_box, width=14, height=14, bg=SURFACE_COLOR, highlightthickness=0)
        self.status_dot.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.status_dot_item = self.status_dot.create_oval(2, 2, 12, 12, fill=BRAND_ORANGE, outline=BRAND_ORANGE)
        tk.Label(
            status_box,
            textvariable=self.status_var,
            bg=SURFACE_COLOR,
            fg=MUTED_COLOR,
            font=("TkDefaultFont", 10),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew")

    def select_project(self):
        path = filedialog.askdirectory(title="选择 python_sim_env 目录", initialdir=self.project_path.get() or str(APP_DIR))
        if path:
            self.project_path.set(path)

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
        path = filedialog.askopenfilename(
            title="选择设计或库文件",
            initialdir=self.project_path.get() or str(APP_DIR),
            filetypes=(("Verilog / library", "*.v *.sv *.lib"), ("All files", "*.*")),
        )
        if path:
            self.design_path.set(path)

    def generate_cases(self):
        project = self.project_path.get().strip()
        register = self.register_path.get().strip()
        if not register:
            messagebox.showerror("缺少寄存器表", "先选择寄存器 Excel。")
            return
        self._start("正在生成激励...", lambda: generate_cases(project, register))

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
        self._start("正在检查日志...", lambda: sim_flow.check_logs(project))

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
        self.result_text.insert(tk.END, text)
        self.result_text.see(tk.END)


def main():
    root = tk.Tk()
    MipiAutoVerifyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
