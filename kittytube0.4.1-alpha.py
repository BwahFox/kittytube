#!/usr/bin/env python3
# KittyTube — Basic frontend for yt-dlp
# Note: This software was generated using ChatGPT. It should work just fine, but please keep in mind that it isn't intended to be used for anything critical. BwahFox just wanted a way to search and watch youtube while freetube isn't working. 
import sys, os, json, shutil, subprocess, threading, time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser

try:
    from yt_dlp import YoutubeDL
except ImportError:
    messagebox.showerror("Missing dependency", "Install with: pip install yt-dlp")
    sys.exit(1)

APP_NAME = "KittyTube"

def user_config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME

CONFIG_DIR = user_config_dir()
THEME_PATH = CONFIG_DIR / "kittytube_theme.json"

def ply():
    if shutil.which("mpv"): return ["mpv"]
    if shutil.which("ffplay"): return ["ffplay", "-autoexit", "-loglevel", "warning"]
    return None

def hms(x):
    if x is None: return "?:??"
    m, s = divmod(int(x), 60); h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def yts(q, n=20):
    with YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True}) as y:
        i = y.extract_info(f"ytsearch{n}:{q}", download=False)
    return i.get("entries", []) if i else []

def prog_url(page_url):
    # Progressive (audio+video) for ffplay fallback
    opts = {"quiet": True, "no_warnings": True, "noplaylist": True,
            "format": "best[acodec!=none][vcodec!=none]/best"}
    with YoutubeDL(opts) as y:
        i = y.extract_info(page_url, download=False)
        if not i: return None
        if "url" in i: return i["url"]
        for f in reversed(i.get("formats") or []):
            if f.get("acodec") not in (None, "none") and f.get("vcodec") not in (None, "none"):
                u = f.get("url")
                if u and u.startswith(("http://","https://")): return u
    return None

def dl(page_url, outdir, cb=None):
    outdir.mkdir(parents=True, exist_ok=True)
    opts = {
        "outtmpl": str(outdir / "%(title).200s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "format": "bv*+ba/best",
        "quiet": False, "no_warnings": True,
        "progress_hooks": [lambda d: cb and cb(d)],
    }
    with YoutubeDL(opts) as y:
        try:
            info = y.extract_info(page_url, download=True)
        except Exception as e:
            cb and cb({"status":"error","error":str(e)})
            return None
    fp = None
    rd = (info or {}).get("requested_downloads") or []
    if rd and rd[0].get("filepath"): fp = rd[0]["filepath"]
    fp = fp or info.get("filepath") or info.get("_filename")
    if not fp: return None
    p = Path(fp)
    for _ in range(50):  # wait up to ~5s for post-processing/rename
        if p.exists(): break
        time.sleep(0.1)
    return p if p.exists() else None

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("760x560")

        # Defaults
        self.results = []
        self.download_dir = Path.cwd() / "downloads"
        self.bg = "#1e1e1e"
        self.fg = "#e6e6e6"
        self._style = ttk.Style()
        try:
            self._style.theme_use("clam")
        except Exception:
            pass

        # Load theme from user config (persistent across runs)
        self._load_theme()

        self._ui()
        self._apply_theme()

    # ---------- Theme persistence ----------
    def _load_theme(self):
        try:
            # Backward-compat: if a theme file sits next to the script/exe, import it once.
            sibling = Path(__file__).with_name("kittytube_theme.json")
            if not THEME_PATH.exists() and sibling.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                THEME_PATH.write_text(sibling.read_text(encoding="utf-8"), encoding="utf-8")

            if THEME_PATH.exists():
                data = json.loads(THEME_PATH.read_text(encoding="utf-8"))
                self.bg = data.get("bg", self.bg)
                self.fg = data.get("fg", self.fg)
        except Exception:
            # Fail silently to safe defaults
            pass

    def _save_theme(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            THEME_PATH.write_text(json.dumps({"bg": self.bg, "fg": self.fg}, indent=2), encoding="utf-8")
            self.log.set(f"Theme saved to {THEME_PATH}")
        except Exception as e:
            self.log.set(f"Theme save error: {e}")

    # ---------- Theming ----------
    def _apply_theme(self):
        bg, fg = self.bg, self.fg
        self.config(bg=bg)

        s = self._style
        s.configure(".", background=bg, foreground=fg)
        s.configure("TFrame", background=bg)
        s.configure("TLabel", background=bg, foreground=fg)
        s.configure("TButton", background=bg, foreground=fg)
        s.configure("TSeparator", background=bg)
        s.configure("TEntry", fieldbackground=bg, foreground=fg)
        s.map("TButton", background=[("active", bg)])

        # Classic widgets that don’t inherit ttk styles
        sel_bg = "#3a86ff"; sel_fg = "#ffffff"
        self.lb.config(bg=bg, fg=fg, highlightbackground=bg,
                       selectbackground=sel_bg, selectforeground=sel_fg)
        self.entry.config(bg=bg, fg=fg, insertbackground=fg,
                          highlightbackground=bg, highlightcolor=fg)
        self.status_lbl.configure(foreground=fg, background=bg)
        self.folder_lbl.configure(foreground=fg, background=bg)

    def _pick_bg(self):
        c = colorchooser.askcolor(color=self.bg, title="Pick background color")
        if c and c[1]:
            self.bg = c[1]
            self._apply_theme()

    def _pick_fg(self):
        c = colorchooser.askcolor(color=self.fg, title="Pick text color")
        if c and c[1]:
            self.fg = c[1]
            self._apply_theme()

    def _reset_theme(self):
        self.bg, self.fg = "#1e1e1e", "#e6e6e6"
        self._apply_theme()
        self.log.set("Theme reset to defaults.")

    # ---------- UI ----------
    def _ui(self):
        # Top: query + limit + search
        top = ttk.Frame(self, padding=8); top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.q = tk.StringVar()
        self.entry = tk.Entry(top, textvariable=self.q, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, padx=6)
        self.entry.bind("<Return>", lambda _ : self.search())
        ttk.Label(top, text="Limit:").pack(side="left", padx=(6,2))
        self.limit = tk.IntVar(value=20)
        ttk.Spinbox(top, from_=1, to=50, textvariable=self.limit, width=4).pack(side="left")
        ttk.Button(top, text="Search", command=self.search).pack(side="left", padx=(6,0))

        # Middle: results + actions
        mid = ttk.Frame(self, padding=(8,0)); mid.pack(fill="both", expand=True)
        lf = ttk.Frame(mid); lf.pack(side="left", fill="both", expand=True)
        self.lb = tk.Listbox(lf, activestyle="dotbox")
        self.lb.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview)
        sb.pack(side="left", fill="y")
        self.lb.config(yscrollcommand=sb.set)

        rt = ttk.Frame(mid, padding=(8,0)); rt.pack(side="left", fill="y")
        ttk.Button(rt, text="Download", command=self.do_dl).pack(fill="x", pady=3)
        ttk.Button(rt, text="Stream",   command=self.do_stream).pack(fill="x", pady=3)
        ttk.Button(rt, text="Both",     command=self.do_both).pack(fill="x", pady=3)
        ttk.Separator(rt, orient="horizontal").pack(fill="x", pady=6)
        ttk.Button(rt, text="Folder…",  command=self.choose_folder).pack(fill="x", pady=3)
        self.folder_lbl = tk.Label(rt, text=str(Path.cwd() / "downloads"), justify="left", wraplength=240, anchor="w")
        self.folder_lbl.pack(fill="x", pady=(2,8))
        ttk.Label(rt, text="Theme:").pack(anchor="w", pady=(8,2))
        ttk.Button(rt, text="BG Color…", command=self._pick_bg).pack(fill="x", pady=2)
        ttk.Button(rt, text="FG Color…", command=self._pick_fg).pack(fill="x", pady=2)
        ttk.Button(rt, text="Save Theme", command=self._save_theme).pack(fill="x", pady=(6,2))
        ttk.Button(rt, text="Reset Theme", command=self._reset_theme).pack(fill="x", pady=2)

        # Bottom: status
        bot = ttk.Frame(self, padding=8); bot.pack(fill="both")
        ttk.Label(bot, text="Status:").pack(anchor="w")
        self.log = tk.StringVar(value="Ready.")
        self.status_lbl = tk.Label(bot, textvariable=self.log, justify="left", wraplength=700, anchor="w")
        self.status_lbl.pack(fill="x")

    # Thread-safe cursor toggle
    def set_busy(self, b): self.after(0, lambda: self.config(cursor=("watch" if b else "arrow")))

    def choose_folder(self):
        path = filedialog.askdirectory(title="Choose download folder", mustexist=True)
        if path:
            self.download_dir = Path(path)
            self.folder_lbl.config(text=str(self.download_dir))

    def sel(self):
        s = self.lb.curselection()
        if not s:
            messagebox.showinfo("Pick one", "Select a video first.")
            return None
        i = s[0]
        return self.results[i] if 0 <= i < len(self.results) else None

    # ---------- Actions ----------
    def search(self):
        q = self.q.get().strip()
        if not q: return
        n = self.limit.get() or 20
        n = max(1, min(50, n))
        def work():
            self.set_busy(True); self.log.set(f"Searching: {q} (limit {n}) …")
            try: res = yts(q, n)
            except Exception as e:
                self.after(0, lambda: self.log.set(f"Search error: {e}"))
                self.after(0, lambda: self.set_busy(False)); return
            def ui():
                self.results = res; self.lb.delete(0,"end")
                if not res: self.log.set("No results.")
                else:
                    for e in res:
                        t = e.get("title") or "(no title)"
                        ch = (e.get("uploader") or e.get("channel")) or "Unknown"
                        self.lb.insert("end", f"{t}  [{hms(e.get('duration'))}] — {ch}")
                    self.log.set(f"Found {len(res)} result(s).")
                self.set_busy(False)
            self.after(0, ui)
        threading.Thread(target=work, daemon=True).start()

    def do_stream(self):
        ent = self.sel()
        if not ent: return
        page = ent.get("webpage_url") or ent.get("url")
        if not page: self.log.set("No URL."); return
        def work():
            self.set_busy(True)
            p = ply()
            if not p:
                self.after(0, lambda: self.log.set("Install mpv or ffplay."))
                self.after(0, lambda: self.set_busy(False)); return
            if p[0] == "mpv":
                cmd = p + ["--ytdl=yes","--ytdl-format=bestvideo+bestaudio/best", page]
            else:
                self.after(0, lambda: self.log.set("Resolving progressive stream…"))
                u = prog_url(page)
                if not u:
                    self.after(0, lambda: self.log.set("Could not get progressive URL."))
                    self.after(0, lambda: self.set_busy(False)); return
                cmd = p + [u]
            self.after(0, lambda: self.log.set("Launching player…"))
            try: subprocess.run(cmd, check=False)
            except Exception as e: self.after(0, lambda: self.log.set(f"Player error: {e}"))
            finally: self.after(0, lambda: self.set_busy(False))
        threading.Thread(target=work, daemon=True).start()

    def _download(self, ent, then_play=False):
        page = ent.get("webpage_url") or ent.get("url")
        if not page: self.log.set("No URL."); return
        def cb(d):
            s = d.get("status")
            if s == "downloading":
                p = d.get("_percent_str","").strip(); v = d.get("_speed_str","").strip(); e = d.get("_eta_str","").strip()
                self.after(0, lambda: self.log.set(f"Downloading… {p}  {v}  ETA {e}"))
            elif s == "finished":
                self.after(0, lambda: self.log.set("Merging…"))
            elif s == "error":
                self.after(0, lambda: self.log.set(f"Error: {d.get('error')}"))
        def work():
            self.set_busy(True)
            path = dl(page, self.download_dir, cb)
            if not path:
                self.after(0, lambda: self.log.set("Download failed."))
                self.after(0, lambda: self.set_busy(False)); return
            self.after(0, lambda: self.log.set(f"Saved: {path}"))
            if then_play:
                p = ply()
                if p:
                    try: subprocess.run(p + [str(path.resolve())], check=False)
                    except Exception as e: self.after(0, lambda: self.log.set(f"Player error: {e}"))
                else:
                    self.after(0, lambda: self.log.set("Install mpv or ffplay to play."))
            self.after(0, lambda: self.set_busy(False))
        threading.Thread(target=work, daemon=True).start()

    def do_dl(self):
        ent = self.sel()
        if ent: self._download(ent, then_play=False)

    def do_both(self):
        ent = self.sel()
        if ent: self._download(ent, then_play=True)

if __name__ == "__main__":
    App().mainloop()
