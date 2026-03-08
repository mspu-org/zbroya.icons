from __future__ import annotations

import queue
import subprocess
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .config import AppConfig
from .intake import build_requests_from_text, write_requests_json
from .pipeline import run_full


DEBUG_STAGES = ["gray", "mask_raw", "mask_clean", "crop", "norm"]


class DesktopApp:
    def __init__(self, root: tk.Tk, config_path: str | None, output_root: Path):
        self.root = root
        self.root.title("Icon Pack Extension Studio")
        self.root.geometry("1380x900")

        self.config_path_var = tk.StringVar(value=config_path or "config.json")
        self.reference_var = tk.StringVar(value="")
        self.output_root_var = tk.StringVar(value=str(output_root))
        self.session_var = tk.StringVar(value="")
        self.force_var = tk.BooleanVar(value=False)
        self.provider_var = tk.StringVar(value="auto")

        self.selected_session: Path | None = None
        self.selected_slug: str | None = None
        self.preview_image_ref = None
        self.queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self._build_layout()
        self._load_sessions()
        self._poll_queue()

    def _build_layout(self) -> None:
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        top = ttk.LabelFrame(container, text="Iteration Setup", padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Config").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.config_path_var, width=80).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self._choose_config).grid(row=0, column=2)

        ttk.Label(top, text="Reference PNG/SVG").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.reference_var, width=80).grid(row=1, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self._choose_reference).grid(row=1, column=2)

        ttk.Label(top, text="Output root").grid(row=2, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.output_root_var, width=80).grid(row=2, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self._choose_output_root).grid(row=2, column=2)

        ttk.Label(top, text="Session name (optional)").grid(row=3, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.session_var, width=32).grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(top, text="Provider").grid(row=3, column=1, sticky="e", padx=(0, 180))
        provider_combo = ttk.Combobox(top, textvariable=self.provider_var, values=["auto", "mock", "openai"], width=10, state="readonly")
        provider_combo.grid(row=3, column=1, sticky="e", padx=(0, 90))

        ttk.Checkbutton(top, text="Force regenerate", variable=self.force_var).grid(row=3, column=2, sticky="w")

        ttk.Label(top, text="Entities (one per line or ; separated)").grid(row=4, column=0, sticky="nw", pady=(8, 0))
        self.entities_text = tk.Text(top, height=5, width=80)
        self.entities_text.grid(row=4, column=1, columnspan=2, sticky="we", pady=(8, 0), padx=6)

        action_bar = ttk.Frame(top)
        action_bar.grid(row=5, column=1, columnspan=2, sticky="e", pady=(8, 0))
        self.run_button = ttk.Button(action_bar, text="Run Iteration", command=self._run_iteration)
        self.run_button.pack(side=tk.LEFT, padx=4)
        ttk.Button(action_bar, text="Refresh Sessions", command=self._load_sessions).pack(side=tk.LEFT, padx=4)

        for idx in range(3):
            top.columnconfigure(idx, weight=0)
        top.columnconfigure(1, weight=1)

        body = ttk.Panedwindow(container, orient=tk.HORIZONTAL)
        body.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        left = ttk.Frame(body)
        mid = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(mid, weight=2)
        body.add(right, weight=2)

        sessions_frame = ttk.LabelFrame(left, text="Iterations")
        sessions_frame.pack(fill=tk.BOTH, expand=True)
        self.sessions_list = tk.Listbox(sessions_frame, height=30)
        self.sessions_list.pack(fill=tk.BOTH, expand=True)
        self.sessions_list.bind("<<ListboxSelect>>", self._on_select_session)

        controls = ttk.Frame(left)
        controls.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(controls, text="Open Preview", command=self._open_preview).pack(fill=tk.X, pady=2)
        ttk.Button(controls, text="Open Output Folder", command=self._open_output_folder).pack(fill=tk.X, pady=2)
        ttk.Button(controls, text="Open ZIP", command=self._open_zip).pack(fill=tk.X, pady=2)

        icons_frame = ttk.LabelFrame(mid, text="Icon Quality")
        icons_frame.pack(fill=tk.BOTH, expand=True)
        cols = ("slug", "quality", "nodes", "holes")
        self.icons_tree = ttk.Treeview(icons_frame, columns=cols, show="headings", height=22)
        self.icons_tree.heading("slug", text="Slug")
        self.icons_tree.heading("quality", text="Quality")
        self.icons_tree.heading("nodes", text="Nodes")
        self.icons_tree.heading("holes", text="Small holes")
        self.icons_tree.column("slug", width=210)
        self.icons_tree.column("quality", width=100)
        self.icons_tree.column("nodes", width=80)
        self.icons_tree.column("holes", width=90)
        self.icons_tree.pack(fill=tk.BOTH, expand=True)
        self.icons_tree.bind("<<TreeviewSelect>>", self._on_select_icon)

        log_frame = ttk.LabelFrame(mid, text="Run Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.log_text = tk.Text(log_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        debug_frame = ttk.LabelFrame(right, text="Intermediate Debug")
        debug_frame.pack(fill=tk.BOTH, expand=True)

        top_debug = ttk.Frame(debug_frame)
        top_debug.pack(fill=tk.X)
        ttk.Label(top_debug, text="Stage").pack(side=tk.LEFT)
        self.stage_var = tk.StringVar(value=DEBUG_STAGES[0])
        stage_combo = ttk.Combobox(top_debug, textvariable=self.stage_var, values=DEBUG_STAGES, state="readonly", width=14)
        stage_combo.pack(side=tk.LEFT, padx=8)
        stage_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_debug_image())

        self.debug_canvas = tk.Label(debug_frame, text="Select session and icon", anchor="center")
        self.debug_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

    def _choose_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            self.config_path_var.set(path)

    def _choose_reference(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.svg"), ("All", "*.*")])
        if path:
            self.reference_var.set(path)

    def _choose_output_root(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_root_var.set(path)

    def _run_iteration(self) -> None:
        reference = self.reference_var.get().strip()
        if not reference:
            messagebox.showerror("Validation", "Select reference PNG/SVG first.")
            return

        entities = self.entities_text.get("1.0", tk.END).strip()
        if not entities:
            messagebox.showerror("Validation", "Enter at least one entity.")
            return

        self.run_button.configure(state=tk.DISABLED)
        t = threading.Thread(target=self._run_iteration_worker, args=(reference, entities), daemon=True)
        t.start()

    def _run_iteration_worker(self, reference: str, entities: str) -> None:
        try:
            cfg_path = self.config_path_var.get().strip() or None
            cfg = AppConfig.load(cfg_path)
            if self.provider_var.get() in {"mock", "openai"}:
                cfg.generation.provider = self.provider_var.get()

            out_root = Path(self.output_root_var.get().strip() or "output")
            out_root.mkdir(parents=True, exist_ok=True)

            session = self.session_var.get().strip()
            if not session:
                session = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            output_dir = out_root / session
            output_dir.mkdir(parents=True, exist_ok=True)

            requests = build_requests_from_text(entities)
            if not requests:
                raise RuntimeError("No valid entities parsed from text.")

            requests_path = output_dir / "intake" / "requests.generated.json"
            write_requests_json(requests_path, requests)

            self.queue.put(("log", f"Running iteration in {output_dir}"))
            manifest = run_full(cfg, Path(reference), requests_path, output_dir, force=self.force_var.get())
            self.queue.put(("log", f"Done. Icons: {len(manifest.icons)}"))
            self.queue.put(("done", str(output_dir)))
        except Exception as exc:  # noqa: BLE001
            self.queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break

            if kind == "log":
                self._append_log(payload)
            elif kind == "error":
                self._append_log(f"ERROR: {payload}")
                messagebox.showerror("Iteration failed", payload)
                self.run_button.configure(state=tk.NORMAL)
            elif kind == "done":
                self._append_log(f"Preview: {Path(payload) / 'preview.html'}")
                self.run_button.configure(state=tk.NORMAL)
                self._load_sessions(select_path=Path(payload))

        self.root.after(250, self._poll_queue)

    def _append_log(self, line: str) -> None:
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)

    def _load_sessions(self, select_path: Path | None = None) -> None:
        out_root = Path(self.output_root_var.get().strip() or "output")
        out_root.mkdir(parents=True, exist_ok=True)

        sessions = sorted([p for p in out_root.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
        self.sessions_list.delete(0, tk.END)
        self._session_paths: list[Path] = sessions

        selected_index = 0
        for idx, path in enumerate(sessions):
            self.sessions_list.insert(tk.END, path.name)
            if select_path and path.resolve() == select_path.resolve():
                selected_index = idx

        if sessions:
            self.sessions_list.select_set(selected_index)
            self._on_select_session(None)

    def _on_select_session(self, _event) -> None:
        sel = self.sessions_list.curselection()
        if not sel:
            return

        session = self._session_paths[sel[0]]
        self.selected_session = session
        self._append_log(f"Selected iteration: {session.name}")

        manifest_path = session / "manifest.json"
        self.icons_tree.delete(*self.icons_tree.get_children())
        if not manifest_path.exists():
            return

        import json

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        icons = data.get("icons", [])
        for icon in icons:
            metrics = icon.get("metrics", {})
            self.icons_tree.insert(
                "",
                tk.END,
                iid=icon.get("slug", ""),
                values=(
                    icon.get("slug", ""),
                    icon.get("quality", ""),
                    metrics.get("nodes", ""),
                    metrics.get("small_holes", ""),
                ),
            )

        children = self.icons_tree.get_children()
        if children:
            self.icons_tree.selection_set(children[0])
            self._on_select_icon(None)

    def _on_select_icon(self, _event) -> None:
        sel = self.icons_tree.selection()
        if not sel:
            return
        self.selected_slug = sel[0]
        self._refresh_debug_image()

    def _refresh_debug_image(self) -> None:
        if not self.selected_session or not self.selected_slug:
            return
        stage = self.stage_var.get()
        path = self.selected_session / "debug" / f"{self.selected_slug}_{stage}.png"
        if not path.exists():
            self.debug_canvas.configure(text=f"No image: {path.name}", image="")
            self.preview_image_ref = None
            return

        img = Image.open(path).convert("RGB")
        img.thumbnail((560, 560))
        tk_img = ImageTk.PhotoImage(img)
        self.preview_image_ref = tk_img
        self.debug_canvas.configure(image=tk_img, text="")

    def _open_preview(self) -> None:
        if not self.selected_session:
            return
        preview = self.selected_session / "preview.html"
        if not preview.exists():
            messagebox.showwarning("Preview", "preview.html not found for selected iteration")
            return
        webbrowser.open(preview.resolve().as_uri())

    def _open_output_folder(self) -> None:
        if not self.selected_session:
            return
        self._open_path(self.selected_session)

    def _open_zip(self) -> None:
        if not self.selected_session:
            return
        zip_path = self.selected_session / "icon_pack_bundle.zip"
        if not zip_path.exists():
            messagebox.showwarning("ZIP", "ZIP not found for selected iteration")
            return
        self._open_path(zip_path)

    @staticmethod
    def _open_path(path: Path) -> None:
        try:
            import os

            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open path", str(exc))


def launch_desktop(config_path: str | None = None, output_root: Path | None = None) -> None:
    root = tk.Tk()
    app = DesktopApp(root, config_path=config_path, output_root=output_root or Path("output"))
    app._append_log("Desktop UI ready")
    root.mainloop()

