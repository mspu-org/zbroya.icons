from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import threading
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

from .config import AppConfig
from .intake import build_requests_from_text, write_requests_json
from .pipeline import run_full, run_package, run_preview

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:
    HAS_DND = False
    DND_FILES = "DND_Files"
    TkinterDnD = None


DEBUG_STAGES = ["gray", "mask_raw", "mask_clean", "crop", "norm"]


def _parse_svg_polygons(svg_path: Path) -> tuple[list[list[tuple[float, float]]], tuple[float, float]]:
    tree = ET.parse(svg_path)
    root = tree.getroot()

    viewbox = root.attrib.get("viewBox", "0 0 512 512").split()
    vb_w = 512.0
    vb_h = 512.0
    if len(viewbox) == 4:
        try:
            vb_w = float(viewbox[2])
            vb_h = float(viewbox[3])
        except Exception:
            vb_w, vb_h = 512.0, 512.0

    path_el = None
    for elem in root.iter():
        if elem.tag.endswith("path"):
            path_el = elem
            break
    if path_el is None:
        return [], (vb_w, vb_h)

    d = path_el.attrib.get("d", "")
    tokens = re.findall(r"[MLZmlz]|-?\d+(?:\.\d+)?", d)
    polygons: list[list[tuple[float, float]]] = []

    i = 0
    cmd = None
    current: list[tuple[float, float]] = []
    while i < len(tokens):
        token = tokens[i]
        if token in {"M", "L", "m", "l", "Z", "z"}:
            cmd = token
            i += 1
            if cmd in {"Z", "z"}:
                if len(current) >= 3:
                    polygons.append(current)
                current = []
            continue

        if cmd in {"M", "L", "m", "l"}:
            if i + 1 >= len(tokens):
                break
            x = float(tokens[i])
            y = float(tokens[i + 1])
            current.append((x, y))
            i += 2
            continue

        i += 1

    if len(current) >= 3:
        polygons.append(current)

    return polygons, (vb_w, vb_h)


def render_svg_preview(svg_path: Path, max_size: tuple[int, int] = (360, 360)) -> Image.Image:
    polys, (vb_w, vb_h) = _parse_svg_polygons(svg_path)
    w, h = 512, 512
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)

    sx = w / max(vb_w, 1.0)
    sy = h / max(vb_h, 1.0)

    for poly in polys:
        pts = [(p[0] * sx, p[1] * sy) for p in poly]
        draw.polygon(pts, fill="#1A1A1A")

    img.thumbnail(max_size)
    return img


class DesktopApp:
    def __init__(self, root: tk.Tk, config_path: str | None, output_root: Path):
        self.root = root
        self.root.title("Icon Pack Extension Studio")
        self.root.geometry("1450x940")

        self.config_path_var = tk.StringVar(value=config_path or "config.json")
        self.reference_var = tk.StringVar(value="")
        self.output_root_var = tk.StringVar(value=str(output_root))
        self.session_var = tk.StringVar(value="")
        self.force_var = tk.BooleanVar(value=False)

        self.provider_var = tk.StringVar(value="openai")
        self.openai_model_var = tk.StringVar(value="gpt-image-1")
        self.openai_key_var = tk.StringVar(value="")

        self.selected_session: Path | None = None
        self.selected_slug: str | None = None
        self._manifest_by_slug: dict[str, dict] = {}
        self._session_paths: list[Path] = []

        self.debug_image_ref = None
        self.source_image_ref = None
        self.svg_image_ref = None

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
        ttk.Entry(top, textvariable=self.config_path_var, width=84).grid(row=0, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self._choose_config).grid(row=0, column=2)

        ttk.Label(top, text="Reference PNG/SVG").grid(row=1, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.reference_var, width=84).grid(row=1, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self._choose_reference).grid(row=1, column=2)

        ttk.Label(top, text="Output root").grid(row=2, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.output_root_var, width=84).grid(row=2, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Browse", command=self._choose_output_root).grid(row=2, column=2)

        ttk.Label(top, text="Session name").grid(row=3, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.session_var, width=24).grid(row=3, column=1, sticky="w", padx=6)

        ttk.Label(top, text="Provider").grid(row=3, column=1, sticky="e", padx=(0, 310))
        provider_combo = ttk.Combobox(top, textvariable=self.provider_var, values=["openai", "mock"], width=10, state="readonly")
        provider_combo.grid(row=3, column=1, sticky="e", padx=(0, 220))

        ttk.Label(top, text="Model").grid(row=3, column=1, sticky="e", padx=(0, 170))
        ttk.Entry(top, textvariable=self.openai_model_var, width=16).grid(row=3, column=1, sticky="e", padx=(0, 40))

        ttk.Checkbutton(top, text="Force regenerate", variable=self.force_var).grid(row=3, column=2, sticky="w")

        ttk.Label(top, text="OpenAI API key").grid(row=4, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.openai_key_var, show="*", width=84).grid(row=4, column=1, sticky="we", padx=6)

        ttk.Label(top, text="Entities (one per line or ; separated)").grid(row=5, column=0, sticky="nw", pady=(8, 0))
        self.entities_text = tk.Text(top, height=5, width=84)
        self.entities_text.grid(row=5, column=1, columnspan=2, sticky="we", pady=(8, 0), padx=6)

        action_bar = ttk.Frame(top)
        action_bar.grid(row=6, column=1, columnspan=2, sticky="e", pady=(8, 0))
        self.run_button = ttk.Button(action_bar, text="Run Iteration", command=self._run_iteration)
        self.run_button.pack(side=tk.LEFT, padx=4)
        self.rebuild_button = ttk.Button(action_bar, text="Rebuild Preview", command=self._rebuild_preview)
        self.rebuild_button.pack(side=tk.LEFT, padx=4)
        ttk.Button(action_bar, text="Refresh Sessions", command=self._load_sessions).pack(side=tk.LEFT, padx=4)

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
        ttk.Button(controls, text="Replace SVG...", command=self._choose_override_svg).pack(fill=tk.X, pady=2)

        icons_frame = ttk.LabelFrame(mid, text="Icon Quality")
        icons_frame.pack(fill=tk.BOTH, expand=True)

        self.icon_notebook = ttk.Notebook(icons_frame)
        self.icon_notebook.pack(fill=tk.BOTH, expand=True)

        all_tab = ttk.Frame(self.icon_notebook)
        weak_tab = ttk.Frame(self.icon_notebook)
        self.icon_notebook.add(all_tab, text="All")
        self.icon_notebook.add(weak_tab, text="Needs cleanup")

        self.icons_all_tree = self._build_icons_tree(all_tab)
        self.icons_weak_tree = self._build_icons_tree(weak_tab)

        log_frame = ttk.LabelFrame(mid, text="Run Log")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        self.log_text = tk.Text(log_frame, height=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        right_top = ttk.LabelFrame(right, text="Manual Override")
        right_top.pack(fill=tk.X)
        self.drop_label = ttk.Label(right_top, text="Drop SVG here for selected slug (or use Replace SVG button)")
        self.drop_label.pack(fill=tk.X, padx=8, pady=8)
        if HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop_override)
        else:
            self.drop_label.configure(text="Drag-and-drop unavailable (install tkinterdnd2). Use Replace SVG button.")

        debug_frame = ttk.LabelFrame(right, text="Debug + Compare")
        debug_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        top_debug = ttk.Frame(debug_frame)
        top_debug.pack(fill=tk.X)
        ttk.Label(top_debug, text="Stage").pack(side=tk.LEFT)
        self.stage_var = tk.StringVar(value=DEBUG_STAGES[0])
        stage_combo = ttk.Combobox(top_debug, textvariable=self.stage_var, values=DEBUG_STAGES, state="readonly", width=14)
        stage_combo.pack(side=tk.LEFT, padx=8)
        stage_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh_debug_image())

        self.debug_canvas = tk.Label(debug_frame, text="Select session and icon", anchor="center")
        self.debug_canvas.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        compare = ttk.Frame(debug_frame)
        compare.pack(fill=tk.BOTH, expand=True)
        src_box = ttk.LabelFrame(compare, text="Source PNG")
        svg_box = ttk.LabelFrame(compare, text="SVG Preview")
        src_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4), pady=4)
        svg_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 0), pady=4)

        self.source_label = tk.Label(src_box, text="-")
        self.source_label.pack(fill=tk.BOTH, expand=True)
        self.svg_label = tk.Label(svg_box, text="-")
        self.svg_label.pack(fill=tk.BOTH, expand=True)

    def _build_icons_tree(self, parent: ttk.Frame) -> ttk.Treeview:
        cols = ("slug", "quality", "override", "nodes", "holes")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=22)
        tree.heading("slug", text="Slug")
        tree.heading("quality", text="Quality")
        tree.heading("override", text="Override")
        tree.heading("nodes", text="Nodes")
        tree.heading("holes", text="Small holes")
        tree.column("slug", width=220)
        tree.column("quality", width=110)
        tree.column("override", width=90)
        tree.column("nodes", width=80)
        tree.column("holes", width=95)
        tree.pack(fill=tk.BOTH, expand=True)
        tree.bind("<<TreeviewSelect>>", self._on_select_icon)
        return tree

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

    def _set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.run_button.configure(state=state)
        self.rebuild_button.configure(state=state)

    def _run_iteration(self) -> None:
        reference = self.reference_var.get().strip()
        if not reference:
            messagebox.showerror("Validation", "Select reference PNG/SVG first.")
            return

        entities = self.entities_text.get("1.0", tk.END).strip()
        if not entities:
            messagebox.showerror("Validation", "Enter at least one entity.")
            return

        self._set_busy(True)
        t = threading.Thread(target=self._run_iteration_worker, args=(reference, entities), daemon=True)
        t.start()

    def _run_iteration_worker(self, reference: str, entities: str) -> None:
        try:
            cfg_path = self.config_path_var.get().strip() or None
            cfg = AppConfig.load(cfg_path)
            cfg.generation.provider = self.provider_var.get().strip() or cfg.generation.provider
            cfg.generation.openai_model = self.openai_model_var.get().strip() or cfg.generation.openai_model

            key = self.openai_key_var.get().strip()
            if key:
                os.environ[cfg.generation.openai_api_key_env] = key

            if cfg.generation.provider == "openai" and not os.getenv(cfg.generation.openai_api_key_env, ""):
                raise RuntimeError(
                    f"OpenAI key is required. Set it in UI field or environment variable {cfg.generation.openai_api_key_env}."
                )

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

    def _rebuild_preview(self) -> None:
        if not self.selected_session:
            messagebox.showwarning("Rebuild", "Select iteration first.")
            return

        self._set_busy(True)
        t = threading.Thread(target=self._rebuild_preview_worker, args=(self.selected_session,), daemon=True)
        t.start()

    def _rebuild_preview_worker(self, session: Path) -> None:
        try:
            cfg = AppConfig.load(self.config_path_var.get().strip() or None)
            manifest_path = session / "manifest.json"
            if not manifest_path.exists():
                raise RuntimeError("manifest.json not found in selected session")

            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            reference = Path(self.reference_var.get().strip() or data.get("reference", ""))
            if not reference.exists() and data.get("reference"):
                reference = Path(data["reference"])

            run_preview(cfg, reference, session)
            run_package(session)
            self.queue.put(("log", f"Preview rebuilt for {session.name}"))
            self.queue.put(("done", str(session)))
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
                messagebox.showerror("Operation failed", payload)
                self._set_busy(False)
            elif kind == "done":
                self._append_log(f"Preview: {Path(payload) / 'preview.html'}")
                self._set_busy(False)
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
        self._session_paths = sessions

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
        self.icons_all_tree.delete(*self.icons_all_tree.get_children())
        self.icons_weak_tree.delete(*self.icons_weak_tree.get_children())
        self._manifest_by_slug.clear()
        if not manifest_path.exists():
            return

        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        icons = data.get("icons", [])
        for icon in icons:
            slug = icon.get("slug", "")
            self._manifest_by_slug[slug] = icon
            metrics = icon.get("metrics", {})
            row = (
                slug,
                icon.get("quality", ""),
                "yes" if icon.get("used_manual_override", False) else "no",
                metrics.get("nodes", ""),
                metrics.get("small_holes", ""),
            )
            self.icons_all_tree.insert("", tk.END, iid=f"all::{slug}", values=row)
            if icon.get("quality") != "good":
                self.icons_weak_tree.insert("", tk.END, iid=f"weak::{slug}", values=row)

        all_rows = self.icons_all_tree.get_children()
        if all_rows:
            self.icons_all_tree.selection_set(all_rows[0])
            self._on_select_icon(None)

    def _selected_slug_from_trees(self) -> str | None:
        for tree in (self.icons_all_tree, self.icons_weak_tree):
            sel = tree.selection()
            if sel:
                key = sel[0]
                if "::" in key:
                    return key.split("::", 1)[1]
        return None

    def _on_select_icon(self, _event) -> None:
        slug = self._selected_slug_from_trees()
        if not slug:
            return
        self.selected_slug = slug
        self._refresh_debug_image()
        self._refresh_comparison()

    def _refresh_debug_image(self) -> None:
        if not self.selected_session or not self.selected_slug:
            return
        stage = self.stage_var.get()
        path = self.selected_session / "debug" / f"{self.selected_slug}_{stage}.png"
        if not path.exists():
            self.debug_canvas.configure(text=f"No image: {path.name}", image="")
            self.debug_image_ref = None
            return

        img = Image.open(path).convert("RGB")
        img.thumbnail((560, 340))
        tk_img = ImageTk.PhotoImage(img)
        self.debug_image_ref = tk_img
        self.debug_canvas.configure(image=tk_img, text="")

    def _refresh_comparison(self) -> None:
        if not self.selected_session or not self.selected_slug:
            return

        item = self._manifest_by_slug.get(self.selected_slug, {})

        src_rel = item.get("generated_png", "")
        src_path = self.selected_session / src_rel if src_rel else self.selected_session / "generated_png" / f"{self.selected_slug}.png"
        if src_path.exists():
            src_img = Image.open(src_path).convert("RGB")
            src_img.thumbnail((340, 340))
            tk_src = ImageTk.PhotoImage(src_img)
            self.source_image_ref = tk_src
            self.source_label.configure(image=tk_src, text="")
        else:
            self.source_label.configure(image="", text="No source PNG")
            self.source_image_ref = None

        svg_rel = item.get("svg", "")
        svg_path = self.selected_session / svg_rel if svg_rel else self.selected_session / "generated_svgs" / f"{self.selected_slug}.svg"
        if svg_path.exists():
            try:
                svg_img = render_svg_preview(svg_path)
                tk_svg = ImageTk.PhotoImage(svg_img)
                self.svg_image_ref = tk_svg
                self.svg_label.configure(image=tk_svg, text="")
            except Exception as exc:  # noqa: BLE001
                self.svg_label.configure(image="", text=f"SVG preview error: {exc}")
                self.svg_image_ref = None
        else:
            self.svg_label.configure(image="", text="No SVG")
            self.svg_image_ref = None

    def _copy_override_svg(self, source_svg: Path) -> None:
        if not self.selected_session or not self.selected_slug:
            messagebox.showwarning("Override", "Select icon first.")
            return
        if not source_svg.exists() or source_svg.suffix.lower() != ".svg":
            messagebox.showwarning("Override", "Select a valid .svg file.")
            return

        target = self.selected_session / "curated_svgs" / f"{self.selected_slug}.svg"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_svg, target)
        self._append_log(f"Manual override set: {target.name}")
        self._rebuild_preview()

    def _choose_override_svg(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("SVG", "*.svg")])
        if path:
            self._copy_override_svg(Path(path))

    def _on_drop_override(self, event) -> None:
        data = (event.data or "").strip()
        if not data:
            return
        parts = self.root.tk.splitlist(data)
        if not parts:
            return
        raw = parts[0].strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        self._copy_override_svg(Path(raw))

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
            if hasattr(os, "startfile"):
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Open path", str(exc))


def launch_desktop(config_path: str | None = None, output_root: Path | None = None) -> None:
    if HAS_DND and TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    app = DesktopApp(root, config_path=config_path, output_root=output_root or Path("output"))
    app._append_log("Desktop UI ready")
    root.mainloop()
