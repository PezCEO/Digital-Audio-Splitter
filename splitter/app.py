import tkinter as tk
from tkinter import messagebox

from splitter.devices import default_output_id, list_outputs, make_source, make_target
from splitter.engine import Engine


class App:
    def __init__(self, root):
        self.root = root
        root.title("Digital Audio Splitter")
        self.engine = None
        self.default_at_start = None
        self.drops = []  # appended by the worker thread, read on the Tk thread
        self.state = {}  # device id -> (tick var, volume var), survives Refresh
        self.rows = {}  # device id -> (checkbox, status label)
        self.rows_frame = tk.Frame(root)
        self.rows_frame.pack(fill="x", padx=8, pady=8)
        buttons = tk.Frame(root)
        buttons.pack(pady=(0, 8))
        self.refresh_btn = tk.Button(buttons, text="Refresh", command=self.build_rows)
        self.refresh_btn.pack(side="left", padx=4)
        self.start_btn = tk.Button(buttons, text="Start", command=self.toggle)
        self.start_btn.pack(side="left", padx=4)
        self.build_rows()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(500, self.tick)

    def build_rows(self):
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self.rows = {}
        for i, (dev_id, name, is_default) in enumerate(list_outputs()):
            ticked, volume = self.state.setdefault(dev_id, (tk.BooleanVar(), tk.IntVar(value=100)))
            box = tk.Checkbutton(self.rows_frame, variable=ticked, anchor="w")
            box.grid(row=i, column=0)
            tk.Label(self.rows_frame, text=name + (" (default — plays normally)" if is_default else ""), anchor="w").grid(row=i, column=1, sticky="w")
            scale = tk.Scale(self.rows_frame, from_=0, to=100, orient="horizontal", variable=volume, showvalue=True,
                             command=lambda v, d=dev_id: self.engine and self.engine.set_volume(d, int(float(v))))
            scale.grid(row=i, column=2)
            status = tk.Label(self.rows_frame, text="", width=26, anchor="w")
            status.grid(row=i, column=3)
            if is_default:
                ticked.set(False)
                box.config(state="disabled")
                scale.config(state="disabled")
            self.rows[dev_id] = (box, status)

    def ticked_ids(self):
        return [d for d in self.rows if self.state[d][0].get()]

    def toggle(self):
        if self.engine:
            self.stop()
            return
        default = default_output_id()  # captured before make_source() so the watch compares like with like
        ids = [d for d in self.ticked_ids() if d != default]
        try:
            engine = Engine(make_source(), {d: make_target(d) for d in ids}, lambda d, e: self.drops.append((d, e)))
            self.drops.clear()
            engine.start()
            for d in ids:
                engine.set_volume(d, self.state[d][1].get())
        except Exception as e:
            messagebox.showerror("Digital Audio Splitter", str(e))
            return
        self.default_at_start = default
        self.engine = engine
        self.start_btn.config(text="Stop")
        self.set_idle_state("disabled")

    def stop(self):
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.start_btn.config(text="Start")
        self.refresh_btn.config(state="normal")
        self.build_rows()  # re-marks the real default row and clears statuses

    def set_idle_state(self, state):
        self.refresh_btn.config(state=state)
        for box, _ in self.rows.values():
            box.config(state=state)

    def tick(self):
        try:
            if self.engine:
                source_error = next((e for d, e in self.drops if d == "__source__"), None)
                if source_error:
                    self.stop()
                    messagebox.showerror("Digital Audio Splitter", f"Capture stopped: {source_error}")
                elif default_output_id() != self.default_at_start:
                    self.stop()
                    messagebox.showinfo("Digital Audio Splitter", "Default output device changed — press Start again.")
                else:
                    for d, (underruns, overruns, dropped) in self.engine.stats().items():
                        self.rows[d][1].config(text="dropped" if dropped else f"underruns {underruns} · overruns {overruns}")
        finally:
            self.root.after(500, self.tick)

    def close(self):
        try:
            if self.engine:
                self.engine.stop()
        finally:
            self.root.destroy()


def run():
    root = tk.Tk()
    App(root)
    root.mainloop()
