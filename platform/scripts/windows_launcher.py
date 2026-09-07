"""Native desktop control panel. No packages, web server or GPU needed to open it."""

import json
import os
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from windows_support import ROOT, check_package, locate_archive, stop_process
from windows_train import ARCHIVES

TASKS = {
    "Grounding DINO - Furniture detection": "dino",
    "SAM 2.1 - Furniture masks": "sam2",
    "SigLIP 2 - Image and text matching": "siglip",
    "Layout Transformer - Research only": "layout",
}


class Launcher:
    def __init__(self, window):
        self.window, self.process, self.busy = window, None, False
        self.events = queue.Queue(maxsize=4096)
        self.cancel_requested = threading.Event()
        window.title("Furniture AI | Windows Studio")
        window.geometry("920x780")
        window.minsize(780, 680)
        window.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("TButton", padding=8)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Furniture AI", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(frame, text="تشغيل المشروع والتدريب على جهازك | Windows control panel").pack(
            anchor="w", pady=(0, 12)
        )
        self.task = tk.StringVar(value=next(iter(TASKS)))
        self.archive, self.data_root = tk.StringVar(), tk.StringVar(value=str(ROOT / "data"))
        self.epochs, self.research = tk.StringVar(value="5"), tk.BooleanVar(value=False)
        self.username, self.password = tk.StringVar(value="fahad"), tk.StringVar()
        self.status = tk.StringVar(value="Ready. Start with Check GPU / ابدأ بفحص الجهاز")
        notebook = ttk.Notebook(frame)
        notebook.pack(fill="x")
        training, studio = ttk.Frame(notebook, padding=12), ttk.Frame(notebook, padding=12)
        notebook.add(studio, text="Design studio | المشروع")
        notebook.add(training, text="Training | التدريب")
        for panel in (training, studio):
            panel.columnconfigure(1, weight=1)
        ttk.Label(studio, text="Username / المستخدم").grid(row=0, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(studio, textvariable=self.username).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Label(studio, text="Password / كلمة المرور").grid(row=1, column=0, sticky="w", padx=4, pady=6)
        ttk.Entry(studio, textvariable=self.password, show="*").grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Label(studio, text="First use: choose 12+ characters. Later: use the same password.").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=6
        )
        ttk.Label(studio, text="أولاً جهّز البيئة، ثم نزّل نماذج التصميم، ثم افتح المشروع.").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=6
        )
        self.actions = []
        studio_buttons = ttk.Frame(studio)
        studio_buttons.grid(row=4, column=0, columnspan=2, sticky="w")
        self.button(studio_buttons, "Download models | تنزيل النماذج", "models")
        self.button(studio_buttons, "Open studio | فتح المشروع", "studio")
        ttk.Label(training, text="Model / النموذج").grid(row=0, column=0, sticky="w", padx=4, pady=6)
        task_box = ttk.Combobox(training, textvariable=self.task, values=list(TASKS), state="readonly")
        task_box.grid(row=0, column=1, columnspan=2, sticky="ew")
        task_box.bind("<<ComboboxSelected>>", lambda event: self.discover_archive())
        ttk.Label(training, text="Dataset ZIP / ملف البيانات").grid(
            row=1, column=0, sticky="w", padx=4, pady=6
        )
        ttk.Entry(training, textvariable=self.archive).grid(row=1, column=1, sticky="ew")
        ttk.Button(training, text="Browse / اختر", command=self.browse_archive).grid(row=1, column=2, padx=4)
        ttk.Label(training, text="Data folder / مجلد البيانات").grid(
            row=2, column=0, sticky="w", padx=4, pady=6
        )
        ttk.Entry(training, textvariable=self.data_root).grid(row=2, column=1, sticky="ew")
        ttk.Button(training, text="Browse / اختر", command=self.browse_data).grid(row=2, column=2, padx=4)
        ttk.Label(training, text="Epochs / دورات التدريب").grid(row=3, column=0, sticky="w", padx=4, pady=6)
        ttk.Spinbox(training, from_=1, to=10000, textvariable=self.epochs, width=10).grid(
            row=3, column=1, sticky="w"
        )
        ttk.Checkbutton(
            training, text="Research data (noncommercial) / بيانات بحثية غير تجارية", variable=self.research
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=6)
        training_buttons = ttk.Frame(training)
        training_buttons.grid(row=5, column=0, columnspan=3, sticky="w")
        self.button(training_buttons, "Check data | فحص البيانات", "plan")
        self.button(training_buttons, "Train | تدريب", "train")
        self.button(training_buttons, "Resume | استئناف", "resume")
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=12)
        self.button(controls, "Check GPU | فحص الجهاز", "doctor")
        self.button(controls, "Setup | تجهيز البيئة", "setup")
        self.cancel = ttk.Button(controls, text="Stop | إيقاف", command=self.stop, state="disabled")
        self.cancel.pack(side="left", padx=3)
        ttk.Button(controls, text="Logs | السجلات", command=self.open_logs).pack(side="left", padx=3)
        ttk.Label(frame, textvariable=self.status, wraplength=850).pack(anchor="w", pady=4)
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0, 8))
        self.output = scrolledtext.ScrolledText(frame, height=17, wrap="word", font=("Consolas", 10))
        self.output.pack(fill="both", expand=True)
        self.output.configure(state="disabled")
        self.discover_archive()
        window.after(100, self.poll)

    def button(self, parent, label, action):
        button = ttk.Button(parent, text=label, command=lambda: self.start(action))
        button.pack(side="left", padx=3)
        self.actions.append(button)

    def discover_archive(self):
        _, filename = ARCHIVES[TASKS[self.task.get()]]
        try:
            self.archive.set(str(locate_archive(None, filename, ROOT / "data")))
        except ValueError:
            self.archive.set("")

    def browse_archive(self):
        chosen = filedialog.askopenfilename(title="Select dataset ZIP", filetypes=[("ZIP archive", "*.zip")])
        if chosen:
            self.archive.set(chosen)

    def browse_data(self):
        chosen = filedialog.askdirectory(title="Data folder")
        if chosen:
            self.data_root.set(chosen)

    def start(self, action):
        if self.busy:
            return
        payload = None
        command = [sys.executable, str(ROOT / "scripts/windows_train.py")]
        if action in {"models", "studio"}:
            command = [sys.executable, str(ROOT / "scripts/windows_studio.py"), "--" + action]
            if action == "studio":
                if (
                    not 3 <= len(self.username.get().strip()) <= 120
                    or not 12 <= len(self.password.get()) <= 256
                ):
                    messagebox.showerror("Account", "Username: 3+ characters. Password: 12-256 characters.")
                    return
                payload = json.dumps({"username": self.username.get(), "password": self.password.get()})
        else:
            command += ["--data-root", self.data_root.get()]
            if action in {"doctor", "setup"}:
                command += ["--doctor-only" if action == "doctor" else "--setup-only"]
            else:
                task = TASKS[self.task.get()]
                command += ["--task", task, "--epochs", self.epochs.get()]
                if self.archive.get():
                    key, _ = ARCHIVES[task]
                    command += ["--" + key.replace("_", "-"), self.archive.get()]
                if self.research.get():
                    command.append("--research")
                if action == "plan":
                    command.append("--plan")
                if action == "resume":
                    checkpoint = filedialog.askdirectory(
                        title="Select epoch checkpoint (contains training-state.json)"
                    )
                    if not checkpoint:
                        return
                    command += ["--resume", checkpoint]
        self.busy = True
        self.cancel_requested.clear()
        for button in self.actions:
            button.configure(state="disabled")
        self.cancel.configure(state="normal")
        self.status.set("Running / جارٍ التنفيذ — " + action)
        self.progress.start()
        threading.Thread(target=self.execute, args=(command, payload), daemon=True).start()

    def execute(self, command, payload):
        code = 1
        try:
            flags = (
                {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                if sys.platform == "win32"
                else {"start_new_session": True}
            )
            self.process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"},
                **flags,
            )
            if payload:
                self.process.stdin.write(payload)
            self.process.stdin.close()
            if self.cancel_requested.is_set():
                self.stop()
            for line in self.process.stdout:
                self.events.put(("text", line))
            code = self.process.wait()
            self.process.stdout.close()
        except (OSError, subprocess.SubprocessError) as error:
            self.events.put(("text", str(error) + "\n"))
        finally:
            self.process = None
            self.events.put(("done", code))

    def poll(self):
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "text":
                self.output.configure(state="normal")
                self.output.insert("end", value)
                if int(self.output.index("end-1c").split(".")[0]) > 2500:
                    self.output.delete("1.0", "501.0")
                self.output.see("end")
                self.output.configure(state="disabled")
            else:
                self.busy = False
                self.progress.stop()
                for button in self.actions:
                    button.configure(state="normal")
                self.cancel.configure(state="disabled")
                self.status.set(
                    {
                        0: "Completed / اكتمل",
                        2: "Setup needed — read report / راجع تقرير الفحص",
                        130: "Stopped / تم الإيقاف",
                    }.get(value, "Stopped with an error — see output / راجع الخطأ أدناه")
                )
        self.window.after(100, self.poll)

    def stop(self):
        self.cancel_requested.set()
        process = self.process
        if process is None or process.poll() is not None:
            return

        def cancel_child():
            try:
                if sys.platform == "win32":
                    process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    stop_process(process)
            except (OSError, subprocess.SubprocessError):
                pass

        threading.Thread(target=cancel_child, daemon=True).start()

    def open_logs(self):
        (ROOT / "logs").mkdir(exist_ok=True)
        if sys.platform == "win32":
            os.startfile(ROOT / "logs")

    def close(self):
        if self.busy:
            messagebox.showinfo(
                "Operation running", "Press Stop and wait for the operation to finish before closing."
            )
            return
        self.window.destroy()


if __name__ == "__main__":
    try:
        check_package()
        window = tk.Tk()
        Launcher(window)
        window.mainloop()
    except (ValueError, OSError, tk.TclError) as error:
        print(f"Cannot open Furniture AI: {error}", file=sys.stderr)
        sys.exit(1)
