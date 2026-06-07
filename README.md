"""
main.py  ──  AttendanceIQ
─────────────────────────
Entry point.  Builds the Tkinter UI and wires it to the three modules:

    modules/face_recognition_module.py  →  face detection & matching
    modules/gesture_module.py           →  hand-gesture classification
    modules/attendance_module.py        →  student data & records

Run:
    python main.py
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import cv2

# ── Our modules ───────────────────────────────────────────────────────────────
from modules.face_recognition_module import (
    face_cascade, get_face_embedding, recognize_face,
    load_faces, save_faces,
)
from modules.gesture_module import (
    create_hands, detect_gesture, mp_draw, mp_hands,
)
from modules.attendance_module import (
    students, records,
    add_student, remove_student,
    mark_attendance, mark_remaining_absent,
    export_csv, today_str, time_str,
    today_records, attendance_stats,
)

# ── Global face DB (loaded once at start) ────────────────────────────────────
face_db = load_faces()


# ══════════════════════════════════════════════════════════════════════════════
class AttendanceApp:

    # ── colour tokens ─────────────────────────────────────────────────────────
    BG       = "#0D0F17"
    SURFACE  = "#141824"
    SURFACE2 = "#1A2035"
    BORDER   = "#232B42"
    ACCENT   = "#5B8DEF"
    ACCENT2  = "#3B6FD4"
    GREEN    = "#34D399"
    RED      = "#F87171"
    YELLOW   = "#FBBF24"
    TEXT     = "#F1F3FA"
    MUTED    = "#64748B"
    SUB      = "#94A3B8"
    WHITE    = "#FFFFFF"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("AttendanceIQ")
        self.root.geometry("1200x760")
        self.root.configure(bg=self.BG)
        self.root.resizable(True, True)
        self.root.minsize(900, 600)

        # ── runtime state ─────────────────────────────────────────────────────
        self.cap             = None
        self.running         = False
        self.gesture_hold    = 0
        self.HOLD_THRESH     = 22
        self._last_marked    = None
        self._recog_sid      = None
        self._recog_name     = ""
        self._recog_score    = 0.0
        self._capture_mode   = False
        self._capture_sid    = None
        self._captured_embs  = []
        self._CAPTURE_NEEDED = 10
        self._selected_sid   = None

        self._build_ui()
        self._refresh_all()

    # ══════════════════════════════════════════════════════════════════════════
    #  FONTS & STYLE
    # ══════════════════════════════════════════════════════════════════════════
    def _f(self, size, weight="normal"):
        return ("Segoe UI", size, weight)

    def _setup_treeview_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("A.Treeview",
            background=self.SURFACE, foreground=self.TEXT,
            rowheight=44, fieldbackground=self.SURFACE,
            borderwidth=0, font=self._f(10))
        s.configure("A.Treeview.Heading",
            background=self.SURFACE2, foreground=self.SUB,
            borderwidth=0, font=self._f(9, "bold"), relief="flat", padding=(8, 10))
        s.map("A.Treeview",
            background=[("selected", self.ACCENT)],
            foreground=[("selected", self.WHITE)])
        s.configure("Vertical.TScrollbar",
            background=self.SURFACE2, troughcolor=self.SURFACE,
            borderwidth=0, arrowsize=12)

    # ══════════════════════════════════════════════════════════════════════════
    #  ROOT LAYOUT
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        self._setup_treeview_style()

        # ── left rail ────────────────────────────────────────────────────────
        rail = tk.Frame(self.root, bg=self.SURFACE, width=220)
        rail.pack(side="left", fill="y")
        rail.pack_propagate(False)

        logo = tk.Frame(rail, bg=self.SURFACE)
        logo.pack(fill="x")
        tk.Frame(logo, bg=self.BG, height=32).pack(fill="x")
        icon_row = tk.Frame(logo, bg=self.SURFACE)
        icon_row.pack(fill="x", padx=20)
        dot = tk.Canvas(icon_row, width=36, height=36,
                        bg=self.SURFACE, highlightthickness=0)
        dot.pack(side="left")
        dot.create_oval(2, 2, 34, 34, fill=self.ACCENT, outline="")
        dot.create_text(18, 18, text="✋", font=("Segoe UI Emoji", 14), fill=self.WHITE)
        tk.Label(icon_row, text="AttendanceIQ",
                 font=self._f(13, "bold"), bg=self.SURFACE, fg=self.TEXT).pack(
                 side="left", padx=10)
        tk.Frame(logo, bg=self.BG, height=8).pack(fill="x")
        tk.Frame(logo, bg=self.BORDER, height=1).pack(fill="x")
        tk.Frame(logo, bg=self.SURFACE, height=16).pack(fill="x")

        self.nav_btns   = {}
        self._active_tab = "register"
        for key, icon, label, sub in [
            ("register",   "◈", "Students",   "Register & manage"),
            ("attendance", "⊙", "Attendance", "Mark via camera"),
            ("records",    "≡", "Records",    "History & export"),
        ]:
            self._nav_btn(rail, key, icon, label, sub)

        tk.Frame(rail, bg=self.BORDER, height=1).pack(side="bottom", fill="x")
        bottom = tk.Frame(rail, bg=self.SURFACE)
        bottom.pack(side="bottom", fill="x", padx=16, pady=14)
        tk.Label(bottom, text="Face + Gesture Recognition",
                 font=self._f(8), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        tk.Label(bottom, text=f"Today  ·  {today_str()}",
                 font=self._f(8), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w", pady=(2, 0))

        self.main = tk.Frame(self.root, bg=self.BG)
        self.main.pack(side="left", fill="both", expand=True)

        self.panels = {}
        for key in ["register", "attendance", "records"]:
            self.panels[key] = tk.Frame(self.main, bg=self.BG)

        self._build_register()
        self._build_attendance()
        self._build_records()
        self._switch_tab("register")

    def _nav_btn(self, parent, key, icon, label, sub):
        frame = tk.Frame(parent, bg=self.SURFACE, cursor="hand2")
        frame.pack(fill="x", padx=10, pady=2)
        c = tk.Canvas(frame, width=4, height=48, bg=self.SURFACE, highlightthickness=0)
        c.pack(side="left")
        inner = tk.Frame(frame, bg=self.SURFACE, padx=8, pady=8)
        inner.pack(side="left", fill="x", expand=True)
        row = tk.Frame(inner, bg=self.SURFACE)
        row.pack(anchor="w")
        tk.Label(row, text=icon, font=self._f(14), bg=self.SURFACE, fg=self.ACCENT).pack(side="left", padx=(0, 8))
        tk.Label(row, text=label, font=self._f(11, "bold"), bg=self.SURFACE, fg=self.TEXT).pack(side="left")
        tk.Label(inner, text=sub, font=self._f(8), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")

        def hover_on(e):
            if self._active_tab != key:
                for w in [frame, inner, row] + list(row.winfo_children()) + list(inner.winfo_children()):
                    try: w.config(bg=self.SURFACE2)
                    except: pass
        def hover_off(e):
            if self._active_tab != key:
                for w in [frame, inner, row] + list(row.winfo_children()) + list(inner.winfo_children()):
                    try: w.config(bg=self.SURFACE)
                    except: pass
        def on_click(e): self._switch_tab(key)

        for w in [frame, inner, row] + list(row.winfo_children()) + list(inner.winfo_children()):
            w.bind("<Enter>",    hover_on)
            w.bind("<Leave>",    hover_off)
            w.bind("<Button-1>", on_click)

        self.nav_btns[key] = (frame, inner, row, c)

    def _switch_tab(self, key):
        self._active_tab = key
        for k, (frame, inner, row, c) in self.nav_btns.items():
            active = k == key
            bg = self.SURFACE2 if active else self.SURFACE
            for w in [frame, inner, row] + list(row.winfo_children()) + list(inner.winfo_children()):
                try: w.config(bg=bg)
                except: pass
            c.config(bg=bg); c.delete("all")
            if active:
                c.create_rectangle(0, 6, 4, 42, fill=self.ACCENT, outline="")
        for k, p in self.panels.items(): p.pack_forget()
        self.panels[key].pack(fill="both", expand=True)
        if key == "records": self._refresh_records()

    # ── shared helpers ────────────────────────────────────────────────────────
    def _page_header(self, parent, title, subtitle):
        hdr = tk.Frame(parent, bg=self.BG)
        hdr.pack(fill="x", padx=32, pady=(28, 18))
        tk.Label(hdr, text=title, font=self._f(20, "bold"), bg=self.BG, fg=self.TEXT).pack(anchor="w")
        tk.Label(hdr, text=subtitle, font=self._f(10), bg=self.BG, fg=self.MUTED).pack(anchor="w", pady=(3, 0))
        tk.Frame(parent, bg=self.BORDER, height=1).pack(fill="x", padx=32)

    def _btn(self, parent, text, bg, fg, cmd, pad_x=16, pad_y=8):
        return tk.Button(parent, text=text, font=self._f(9, "bold"),
                         bg=bg, fg=fg, relief="flat", bd=0,
                         padx=pad_x, pady=pad_y, cursor="hand2",
                         activebackground=bg, activeforeground=fg, command=cmd)

    # ══════════════════════════════════════════════════════════════════════════
    #  REGISTER PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_register(self):
        p = self.panels["register"]
        self._page_header(p, "Student Registration",
                          "Add students and capture their face for automatic recognition")

        card = tk.Frame(p, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1)
        card.pack(fill="x", padx=32, pady=(20, 0))
        hdr_r = tk.Frame(card, bg=self.SURFACE)
        hdr_r.pack(fill="x", padx=20, pady=(18, 0))
        tk.Label(hdr_r, text="New Student", font=self._f(11, "bold"), bg=self.SURFACE, fg=self.TEXT).pack(side="left")

        fields = tk.Frame(card, bg=self.SURFACE)
        fields.pack(fill="x", padx=20, pady=(12, 18))
        fields.columnconfigure(0, weight=4)
        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(2, weight=0)

        nf = tk.Frame(fields, bg=self.SURFACE)
        nf.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        tk.Label(nf, text="FULL NAME", font=self._f(8, "bold"), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w", pady=(0, 5))
        ef1 = tk.Frame(nf, bg=self.SURFACE2, highlightbackground=self.BORDER, highlightthickness=1)
        ef1.pack(fill="x")
        self.ent_name = tk.Entry(ef1, font=self._f(11), bg=self.SURFACE2, fg=self.TEXT,
                                 insertbackground=self.ACCENT, relief="flat", bd=0)
        self.ent_name.pack(fill="x", padx=12, ipady=10)
        self.ent_name.bind("<Return>", lambda e: self._add_student())

        rf = tk.Frame(fields, bg=self.SURFACE)
        rf.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        tk.Label(rf, text="ROLL NO.", font=self._f(8, "bold"), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w", pady=(0, 5))
        vcmd = (self.root.register(lambda s: s.isdigit() or s == ""), "%S")
        ef2 = tk.Frame(rf, bg=self.SURFACE2, highlightbackground=self.BORDER, highlightthickness=1)
        ef2.pack(fill="x")
        self.ent_roll = tk.Entry(ef2, font=self._f(11), bg=self.SURFACE2, fg=self.TEXT,
                                 insertbackground=self.ACCENT, relief="flat", bd=0,
                                 validate="key", validatecommand=vcmd)
        self.ent_roll.pack(fill="x", padx=12, ipady=10)
        self.ent_roll.bind("<Return>", lambda e: self._add_student())

        bf = tk.Frame(fields, bg=self.SURFACE)
        bf.grid(row=0, column=2, sticky="s")
        tk.Label(bf, text=" ", font=self._f(8), bg=self.SURFACE).pack()
        self._btn(bf, "＋  Add Student", self.ACCENT, self.WHITE, self._add_student, pad_x=20, pad_y=10).pack()

        list_outer = tk.Frame(p, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1)
        list_outer.pack(fill="both", expand=True, padx=32, pady=(16, 28))
        lhdr = tk.Frame(list_outer, bg=self.SURFACE)
        lhdr.pack(fill="x", padx=20, pady=(16, 12))
        tk.Label(lhdr, text="Student Name", font=self._f(11, "bold"), bg=self.SURFACE, fg=self.TEXT).pack(side="left")
        self.lbl_count = tk.Label(lhdr, text="0", font=self._f(9, "bold"),
                                  bg=self.ACCENT, fg=self.WHITE, padx=10, pady=3)
        self.lbl_count.pack(side="left", padx=10)
        self._btn(lhdr, "📸  Capture Face", self.YELLOW, "#1A1400", self._start_face_capture, pad_x=12, pad_y=5).pack(side="right")
        self._btn(lhdr, "✕  Remove", self.SURFACE2, self.RED, self._remove_student, pad_x=12, pad_y=5).pack(side="right", padx=(0, 8))

        list_wrap = tk.Frame(list_outer, bg=self.SURFACE)
        list_wrap.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.student_canvas = tk.Canvas(list_wrap, bg=self.SURFACE, highlightthickness=0)
        sb = ttk.Scrollbar(list_wrap, orient="vertical", command=self.student_canvas.yview)
        self.student_canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.student_canvas.pack(side="left", fill="both", expand=True)
        self.student_list_frame = tk.Frame(self.student_canvas, bg=self.SURFACE)
        self._canvas_window = self.student_canvas.create_window((0, 0), window=self.student_list_frame, anchor="nw")
        self.student_list_frame.bind("<Configure>", lambda e: self.student_canvas.configure(scrollregion=self.student_canvas.bbox("all")))
        self.student_canvas.bind("<Configure>", lambda e: self.student_canvas.itemconfig(self._canvas_window, width=e.width))

        self.face_status_bar = tk.Frame(p, bg=self.SURFACE2, highlightbackground=self.ACCENT, highlightthickness=0)
        self.lbl_face_status = tk.Label(self.face_status_bar, text="", font=self._f(10, "bold"), bg=self.SURFACE2, fg=self.YELLOW)
        self.lbl_face_status.pack(padx=20, pady=10)

    def _render_student_cards(self):
        for w in self.student_list_frame.winfo_children():
            w.destroy()
        col_count = 3
        for idx, s in enumerate(students):
            r, c = divmod(idx, col_count)
            has_face  = s["id"] in face_db
            face_clr  = self.GREEN  if has_face else self.YELLOW
            face_text = "● Face OK"  if has_face else "○ No Face"
            card = tk.Frame(self.student_list_frame, bg=self.SURFACE2,
                            highlightbackground=self.BORDER, highlightthickness=1, cursor="hand2")
            card.grid(row=r, column=c, padx=8, pady=8, sticky="nsew")
            self.student_list_frame.columnconfigure(c, weight=1)
            tk.Frame(card, bg=self.ACCENT if not has_face else self.GREEN, height=3).pack(fill="x")
            inner = tk.Frame(card, bg=self.SURFACE2)
            inner.pack(fill="both", expand=True, padx=16, pady=12)
            tk.Label(inner, text=f"  #{s['roll']}  ", font=self._f(8, "bold"),
                     bg=self.SURFACE, fg=self.SUB, padx=0, pady=2).pack(anchor="w")
            tk.Label(inner, text=s["name"], font=self._f(14, "bold"), bg=self.SURFACE2,
                     fg=self.TEXT, anchor="w", wraplength=180, justify="left").pack(anchor="w", pady=(4, 2))
            tk.Label(inner, text=face_text, font=self._f(9), bg=self.SURFACE2, fg=face_clr).pack(anchor="w")
            tk.Label(inner, text=s.get("date", ""), font=self._f(8), bg=self.SURFACE2, fg=self.MUTED).pack(anchor="w", pady=(6, 0))

            def select_card(event, sid=s["id"], c=card):
                self._selected_sid = sid
                for w in self.student_list_frame.winfo_children():
                    w.config(highlightbackground=self.BORDER)
                c.config(highlightbackground=self.ACCENT, highlightthickness=2)

            for w in [card, inner] + list(inner.winfo_children()):
                w.bind("<Button-1>", select_card)

        self.student_canvas.update_idletasks()
        self.student_canvas.configure(scrollregion=self.student_canvas.bbox("all"))

    # ══════════════════════════════════════════════════════════════════════════
    #  ATTENDANCE PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_attendance(self):
        p = self.panels["attendance"]
        self._page_header(p, "Mark Attendance", "Camera detects face → show 👍 to mark Present")

        body = tk.Frame(p, bg=self.BG)
        body.pack(fill="both", expand=True, padx=32, pady=(20, 28))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        cam_col  = tk.Frame(body, bg=self.BG)
        cam_col.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        cam_col.rowconfigure(0, weight=1)
        cam_card = tk.Frame(cam_col, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1)
        cam_card.pack(fill="both", expand=True)
        self.cam_label = tk.Label(cam_card, bg="#07080F",
                                  text="📷\n\nCamera off\nClick Start Camera below",
                                  fg=self.MUTED, font=self._f(12))
        self.cam_label.pack(fill="both", expand=True)

        gesture_row  = tk.Frame(cam_col, bg=self.BG)
        gesture_row.pack(fill="x", pady=(10, 0))
        self.gesture_pill = tk.Frame(gesture_row, bg=self.SURFACE2, highlightbackground=self.BORDER, highlightthickness=1)
        self.gesture_pill.pack(fill="x")
        inner_pill = tk.Frame(self.gesture_pill, bg=self.SURFACE2)
        inner_pill.pack(fill="x", padx=16, pady=10)
        self.lbl_g_icon = tk.Label(inner_pill, text="🤲", font=("Segoe UI Emoji", 20), bg=self.SURFACE2, fg=self.TEXT)
        self.lbl_g_icon.pack(side="left", padx=(0, 12))
        gtext_col = tk.Frame(inner_pill, bg=self.SURFACE2)
        gtext_col.pack(side="left", fill="x", expand=True)
        self.lbl_g_text = tk.Label(gtext_col, text="Waiting for gesture...", font=self._f(11, "bold"), bg=self.SURFACE2, fg=self.MUTED, anchor="w")
        self.lbl_g_text.pack(fill="x")
        self.lbl_g_prog = tk.Label(gtext_col, text="", font=self._f(8), bg=self.SURFACE2, fg=self.MUTED, anchor="w")
        self.lbl_g_prog.pack(fill="x")
        self.btn_cam = self._btn(inner_pill, "▶  Start Camera", self.GREEN, "#071A0F", self._toggle_camera, pad_x=18, pad_y=10)
        self.btn_cam.pack(side="right")

        right = tk.Frame(body, bg=self.BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        recog_outer = tk.Frame(right, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1)
        recog_outer.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._recog_stripe = tk.Frame(recog_outer, bg=self.MUTED, height=3)
        self._recog_stripe.pack(fill="x")
        recog_inner = tk.Frame(recog_outer, bg=self.SURFACE)
        recog_inner.pack(fill="x", padx=16, pady=12)
        tk.Label(recog_inner, text="RECOGNISED STUDENT", font=self._f(8, "bold"), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        self.lbl_recog_name = tk.Label(recog_inner, text="—", font=self._f(16, "bold"), bg=self.SURFACE, fg=self.MUTED)
        self.lbl_recog_name.pack(anchor="w", pady=(4, 2))
        self.lbl_recog_conf = tk.Label(recog_inner, text="", font=self._f(9), bg=self.SURFACE, fg=self.MUTED)
        self.lbl_recog_conf.pack(anchor="w")

        absent_frame = tk.Frame(right, bg=self.BG)
        absent_frame.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self._btn(absent_frame, "❌  Mark Remaining Absent", self.RED, self.WHITE,
                  self._mark_remaining_absent_ui, pad_x=10, pad_y=11).pack(fill="x")
        tk.Label(absent_frame, text="Marks all un-marked students absent",
                 font=self._f(8), bg=self.BG, fg=self.MUTED, wraplength=260, justify="left").pack(anchor="w", pady=(4, 0))

        div_frame = tk.Frame(right, bg=self.BG)
        div_frame.grid(row=2, column=0, sticky="ew", pady=(10, 6))
        tk.Frame(div_frame, bg=self.BORDER, height=1).pack(fill="x", pady=(0, 8))
        tk.Label(div_frame, text="TODAY'S LOG", font=self._f(8, "bold"), bg=self.BG, fg=self.MUTED).pack(anchor="w")

        log_outer = tk.Frame(right, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1)
        log_outer.grid(row=3, column=0, sticky="nsew")
        log_outer.rowconfigure(0, weight=1)
        log_outer.columnconfigure(0, weight=1)
        self.tree_today = ttk.Treeview(log_outer, columns=("name", "status"), show="headings", style="A.Treeview")
        self.tree_today.heading("name",   text="Name")
        self.tree_today.heading("status", text="Status")
        self.tree_today.column("name",   width=130, minwidth=80)
        self.tree_today.column("status", width=90,  anchor="center")
        self.tree_today.tag_configure("present", foreground=self.GREEN)
        self.tree_today.tag_configure("absent",  foreground=self.RED)
        log_sb = ttk.Scrollbar(log_outer, orient="vertical", command=self.tree_today.yview)
        self.tree_today.configure(yscrollcommand=log_sb.set)
        self.tree_today.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=4)
        log_sb.grid(row=0, column=1, sticky="ns", pady=4, padx=(0, 4))

    # ══════════════════════════════════════════════════════════════════════════
    #  RECORDS PANEL
    # ══════════════════════════════════════════════════════════════════════════
    def _build_records(self):
        p = self.panels["records"]
        self._page_header(p, "Attendance Records", "Full history with export")

        stat_row = tk.Frame(p, bg=self.BG)
        stat_row.pack(fill="x", padx=32, pady=(20, 16))
        self.stat_total   = self._stat(stat_row, "0",  "Total Students",  self.ACCENT)
        self.stat_present = self._stat(stat_row, "0",  "Present Today",   self.GREEN)
        self.stat_absent  = self._stat(stat_row, "0",  "Absent Today",    self.RED)
        self.stat_rate    = self._stat(stat_row, "0%", "Attendance Rate", self.YELLOW)

        tbl_outer = tk.Frame(p, bg=self.SURFACE, highlightbackground=self.BORDER, highlightthickness=1)
        tbl_outer.pack(fill="both", expand=True, padx=32, pady=(0, 28))
        tbl_hdr = tk.Frame(tbl_outer, bg=self.SURFACE)
        tbl_hdr.pack(fill="x", padx=20, pady=(16, 10))
        tk.Label(tbl_hdr, text="All Records", font=self._f(11, "bold"), bg=self.SURFACE, fg=self.TEXT).pack(side="left")
        self._btn(tbl_hdr, "⬇  Export CSV",   self.ACCENT,   self.WHITE, self._save_csv,    pad_x=14, pad_y=6).pack(side="right")
        self._btn(tbl_hdr, "Clear Today",      self.SURFACE2, self.RED,   self._clear_today, pad_x=12, pad_y=6).pack(side="right", padx=(0, 8))

        cols = ("date", "roll", "name", "status", "time")
        self.tree_records = ttk.Treeview(tbl_outer, columns=cols, show="headings", style="A.Treeview", height=14)
        for col, lbl, w, anchor in [
            ("date",   "Date",         110, "center"),
            ("roll",   "Roll",          70, "center"),
            ("name",   "Student Name", 260, "w"),
            ("status", "Status",       120, "center"),
            ("time",   "Time",          90, "center"),
        ]:
            self.tree_records.heading(col, text=lbl)
            self.tree_records.column(col,  width=w, anchor=anchor)
        self.tree_records.tag_configure("present", foreground=self.GREEN)
        self.tree_records.tag_configure("absent",  foreground=self.RED)
        self.tree_records.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 10))
        sb2 = ttk.Scrollbar(tbl_outer, orient="vertical", command=self.tree_records.yview)
        sb2.pack(side="right", fill="y", pady=(0, 10), padx=(0, 8))
        self.tree_records.configure(yscrollcommand=sb2.set)

    def _stat(self, parent, value, label, color):
        card = tk.Frame(parent, bg=self.SURFACE, padx=18, pady=14,
                        highlightbackground=color, highlightthickness=1)
        card.pack(side="left", expand=True, fill="x", padx=(0, 14))
        tk.Frame(card, bg=color, height=2).pack(fill="x", pady=(0, 10))
        v = tk.Label(card, text=value, font=self._f(26, "bold"), bg=self.SURFACE, fg=color)
        v.pack(anchor="w")
        tk.Label(card, text=label, font=self._f(8), bg=self.SURFACE, fg=self.MUTED).pack(anchor="w")
        return v

    # ══════════════════════════════════════════════════════════════════════════
    #  DATA OPERATIONS  (delegate to attendance_module)
    # ══════════════════════════════════════════════════════════════════════════
    def _add_student(self):
        name = self.ent_name.get().strip()
        roll = self.ent_roll.get().strip()
        if not name:
            messagebox.showwarning("Missing Name", "Please enter the student's full name."); return
        result = add_student(name, roll)
        if result is None:
            messagebox.showwarning("Already Exists", f"'{name}' is already registered."); return
        self.ent_name.delete(0, "end")
        self.ent_roll.delete(0, "end")
        self.ent_name.focus()
        self._refresh_all()
        messagebox.showinfo("Added", f"{name} registered!\n\nClick their card → then '📸 Capture Face'")

    def _remove_student(self):
        sid = self._selected_sid
        if not sid:
            messagebox.showwarning("No Selection", "Click a student card first, then press Remove."); return
        s = next((x for x in students if x["id"] == sid), None)
        if not s: return
        if not messagebox.askyesno("Remove", f"Remove '{s['name']}' completely?"): return
        remove_student(sid, face_db)
        save_faces(face_db)
        self._selected_sid = None
        self._refresh_all()

    def _mark(self, sid, status):
        mark_attendance(sid, status)
        self._refresh_today()
        self._refresh_records()

    def _mark_remaining_absent_ui(self):
        unmarked = [s for s in students if s["id"] not in {r["studentId"] for r in today_records()}]
        if not unmarked:
            messagebox.showinfo("All Done", "Everyone is already marked."); return
        names = "\n".join(f"  • {s['name']}" for s in unmarked)
        if not messagebox.askyesno("Confirm", f"Mark {len(unmarked)} student(s) absent?\n\n{names}"): return
        mark_remaining_absent()
        self._refresh_today()
        self._refresh_records()
        messagebox.showinfo("Done", f"{len(unmarked)} student(s) marked Absent.")

    def _save_csv(self):
        try:
            path = export_csv()
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except ValueError:
            messagebox.showwarning("Empty", "No records to export.")

    def _clear_today(self):
        if not messagebox.askyesno("Confirm", "Clear all of today's records?"): return
        global records
        from modules import attendance_module as am
        am.records[:] = [r for r in am.records if r["date"] != today_str()]
        am._save_all()
        self._refresh_all()

    # ══════════════════════════════════════════════════════════════════════════
    #  FACE CAPTURE  (uses face_recognition_module)
    # ══════════════════════════════════════════════════════════════════════════
    def _start_face_capture(self):
        sid = self._selected_sid
        if not sid:
            messagebox.showwarning("Select First", "Click a student card first, then press Capture Face."); return
        s = next((x for x in students if x["id"] == sid), None)
        if not s: return
        self._capture_sid   = sid
        self._capture_mode  = True
        self._captured_embs = []
        self.face_status_bar.config(highlightthickness=1)
        self.face_status_bar.pack(fill="x", padx=32, pady=(0, 8))
        self.lbl_face_status.config(text=f"📸  Capturing face for {s['name']} — look straight into the camera", fg=self.YELLOW)
        if not self.running:
            self.running = True
            threading.Thread(target=self._face_capture_loop, daemon=True).start()

    def _face_capture_loop(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            self.root.after(0, lambda: messagebox.showerror("Camera Error", "Cannot open camera."))
            self._capture_mode = False; self.running = False; return

        while self._capture_mode and self.running:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1)
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.2, 6, minSize=(80, 80))
            for rect in faces:
                emb = get_face_embedding(frame, rect)     # ← face_recognition_module
                if emb is not None:
                    self._captured_embs.append(emb)
                x, y, w, h = rect
                cv2.rectangle(frame, (x, y), (x+w, y+h), (91, 141, 239), 2)
            n      = len(self._captured_embs)
            status = f"📸  Captured {min(n, self._CAPTURE_NEEDED)}/{self._CAPTURE_NEEDED}  —  hold still..."
            h2, w2 = frame.shape[:2]
            nw  = 420; nh = int(nw * h2 / w2)
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((nw, nh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.root.after(0, self._update_capture_ui, photo, status)
            if n >= self._CAPTURE_NEEDED:
                break

        cap.release(); self.running = False
        if len(self._captured_embs) >= self._CAPTURE_NEEDED:
            self.root.after(0, self._save_captured_face)
        else:
            self._capture_mode = False
            self.root.after(0, lambda: self.lbl_face_status.config(text="⚠  Capture failed. Try again.", fg=self.RED))

    def _update_capture_ui(self, photo, status):
        if not hasattr(self, "_cap_win") or not self._cap_win.winfo_exists():
            self._cap_win = tk.Toplevel(self.root)
            self._cap_win.title("Face Capture")
            self._cap_win.configure(bg=self.BG)
            self._cap_win.resizable(False, False)
            self._cap_win.protocol("WM_DELETE_WINDOW", self._cancel_capture)
            tk.Frame(self._cap_win, bg=self.BG, height=12).pack()
            self._cap_lbl  = tk.Label(self._cap_win, bg=self.BG)
            self._cap_lbl.pack(padx=16)
            self._cap_info = tk.Label(self._cap_win, font=self._f(10, "bold"), bg=self.BG, fg=self.YELLOW)
            self._cap_info.pack(padx=16, pady=(8, 16))
        self._cap_lbl.config(image=photo); self._cap_lbl.image = photo
        self._cap_info.config(text=status)
        self.lbl_face_status.config(text=status)

    def _cancel_capture(self):
        self._capture_mode = False; self.running = False
        if hasattr(self, "_cap_win") and self._cap_win.winfo_exists():
            self._cap_win.destroy()

    def _save_captured_face(self):
        sid = self._capture_sid
        self._capture_mode = False
        face_db[sid] = self._captured_embs[:self._CAPTURE_NEEDED]
        save_faces(face_db)                              # ← face_recognition_module
        s = next((x for x in students if x["id"] == sid), None)
        self.lbl_face_status.config(text=f"✅  Face saved for {s['name'] if s else sid}", fg=self.GREEN)
        if hasattr(self, "_cap_win") and self._cap_win.winfo_exists():
            self._cap_win.destroy()
        self._refresh_all()
        messagebox.showinfo("Done", f"Face registered for {s['name'] if s else sid}!\nThey'll now be recognised automatically.")

    # ══════════════════════════════════════════════════════════════════════════
    #  CAMERA LOOP  (uses all three modules)
    # ══════════════════════════════════════════════════════════════════════════
    def _toggle_camera(self):
        if self.running:
            self.running = False
            self.btn_cam.config(text="▶  Start Camera", bg=self.GREEN, fg="#071A0F")
            if self.cap: self.cap.release(); self.cap = None
            self.cam_label.config(image="", text="📷\n\nCamera off\nClick Start Camera below", fg=self.MUTED)
            self.lbl_g_icon.config(text="🤲")
            self.lbl_g_text.config(text="Waiting for gesture...", fg=self.MUTED)
            self.lbl_g_prog.config(text="")
            self.lbl_recog_name.config(text="—", fg=self.MUTED)
            self.lbl_recog_conf.config(text="")
        else:
            self.running = True
            self.btn_cam.config(text="⏹  Stop Camera", bg=self.RED, fg=self.WHITE)
            threading.Thread(target=self._camera_loop, daemon=True).start()

    def _camera_loop(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.root.after(0, lambda: messagebox.showerror("Camera Error", "Could not open camera."))
            self.running = False; return

        hands_sol    = create_hands()                    # ← gesture_module
        prev_gesture = "none"
        frame_count  = 0
        recog_every  = 8

        while self.running:
            ret, frame = self.cap.read()
            if not ret: break
            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # face recognition (every N frames) ← face_recognition_module
            if frame_count % recog_every == 0:
                gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.2, 6, minSize=(70, 70))
                best_sid, best_score = None, 0.0
                for rect in faces:
                    emb = get_face_embedding(frame, rect)
                    if emb is not None:
                        sid, score = recognize_face(emb, face_db)
                        if score > best_score:
                            best_score, best_sid = score, sid
                self._recog_sid   = best_sid
                self._recog_score = best_score
                if best_sid:
                    s = next((x for x in students if x["id"] == best_sid), None)
                    self._recog_name = s["name"] if s else "Unknown"
                else:
                    self._recog_name = ""
            frame_count += 1

            gray2  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces2 = face_cascade.detectMultiScale(gray2, 1.2, 5, minSize=(60, 60))
            for (x, y, w, h) in faces2:
                col = (52, 211, 153) if self._recog_sid else (100, 116, 139)
                cv2.rectangle(frame, (x, y), (x+w, y+h), col, 2)
                cv2.putText(frame, self._recog_name or "Unknown",
                            (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2)

            # gesture detection ← gesture_module
            result  = hands_sol.process(rgb)
            gesture = "none"
            if result.multi_hand_landmarks:
                for hl in result.multi_hand_landmarks:
                    mp_draw.draw_landmarks(frame, hl, mp_hands.HAND_CONNECTIONS)
                    gesture = detect_gesture(hl)          # ← gesture_module

            if gesture == prev_gesture and gesture != "none":
                self.gesture_hold += 1
            else:
                self.gesture_hold = 0
                self._last_marked = None
            prev_gesture = gesture

            # auto-mark attendance ← attendance_module
            if self.gesture_hold == self.HOLD_THRESH and gesture == "thumbsup":
                sid = self._recog_sid
                if sid and sid != self._last_marked:
                    self._last_marked = sid
                    self.root.after(0, lambda s=sid: self._flash_present(s))
                elif not sid:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Not Recognised",
                        "No registered face detected.\nMake sure the student's face was captured."))
                self.gesture_hold = 0

            c_bgr  = (52, 211, 153) if gesture == "thumbsup" else \
                     (248, 113, 113) if gesture == "thumbsdown" else (100, 116, 139)
            ov     = f"👍  {self._recog_name} → PRESENT" if gesture == "thumbsup" and self._recog_name \
                     else "👍  No face recognised" if gesture == "thumbsup" \
                     else "👎  Thumbs down" if gesture == "thumbsdown" else "Show your hand..."
            pct_bar = min(int(self.gesture_hold / self.HOLD_THRESH * 100), 100)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 46), (13, 15, 23), -1)
            cv2.putText(frame, ov, (12, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, c_bgr, 2)
            if pct_bar > 0:
                bw = int(frame.shape[1] * pct_bar / 100)
                cv2.rectangle(frame, (0, frame.shape[0]-5), (bw, frame.shape[0]), c_bgr, -1)

            nw = 560; nh = int(nw * frame.shape[0] / frame.shape[1])
            img   = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).resize((nw, nh), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            g_icon = "👍" if gesture == "thumbsup" else "👎" if gesture == "thumbsdown" else "🤲"
            g_text = "Thumbs Up — hold steady!" if gesture == "thumbsup" else \
                     "Thumbs Down detected" if gesture == "thumbsdown" else "Show your hand to the camera"
            g_clr  = self.GREEN if gesture == "thumbsup" else self.RED if gesture == "thumbsdown" else self.MUTED
            prog   = f"{pct_bar}%  keep holding..." if pct_bar > 0 else ""
            rname  = self._recog_name or "No face detected"
            rconf  = f"Confidence: {int(self._recog_score * 100)}%" if self._recog_sid else ""
            rclr   = self.GREEN if self._recog_sid else self.MUTED

            self.root.after(0, self._update_frame, photo, g_icon, g_text, g_clr, prog, rname, rconf, rclr, rclr)

        hands_sol.close()
        if self.cap: self.cap.release()

    def _flash_present(self, sid):
        self._mark(sid, "present")
        s = next((x for x in students if x["id"] == sid), None)
        name = s["name"] if s else sid
        self.lbl_recog_name.config(fg=self.GREEN, text=f"✅  {name}  —  PRESENT!")
        self.root.after(2500, lambda: self.lbl_recog_name.config(
            text=self._recog_name or "—", fg=self.GREEN if self._recog_sid else self.MUTED))

    def _update_frame(self, photo, icon, text, clr, prog, rname, rconf, rclr, rstripe):
        self.cam_label.config(image=photo, text=""); self.cam_label.image = photo
        self.lbl_g_icon.config(text=icon)
        self.lbl_g_text.config(text=text, fg=clr)
        self.lbl_g_prog.config(text=prog, fg=clr)
        self.lbl_recog_name.config(text=rname, fg=rclr)
        self.lbl_recog_conf.config(text=rconf)
        self._recog_stripe.config(bg=rstripe)

    # ══════════════════════════════════════════════════════════════════════════
    #  REFRESH
    # ══════════════════════════════════════════════════════════════════════════
    def _refresh_all(self):
        self._setup_treeview_style()
        self._render_student_cards()
        self.lbl_count.config(text=str(len(students)))
        self._refresh_today()
        self._refresh_records()

    def _refresh_today(self):
        for i in self.tree_today.get_children(): self.tree_today.delete(i)
        for r in today_records():
            tag  = "present" if r["status"] == "present" else "absent"
            icon = "✅ Present" if r["status"] == "present" else "❌ Absent"
            self.tree_today.insert("", "end", values=(r["studentName"], icon), tags=(tag,))

    def _refresh_records(self):
        for i in self.tree_records.get_children(): self.tree_records.delete(i)
        stats = attendance_stats()
        self.stat_total["text"]   = str(stats["total"])
        self.stat_present["text"] = str(stats["present"])
        self.stat_absent["text"]  = str(stats["absent"])
        self.stat_rate["text"]    = f"{stats['rate_pct']}%"
        from modules import attendance_module as am
        for r in sorted(am.records, key=lambda x: (x["date"], x["roll"]), reverse=True):
            tag  = "present" if r["status"] == "present" else "absent"
            icon = "✅ Present" if r["status"] == "present" else "❌ Absent"
            self.tree_records.insert("", "end", values=(
                r["date"], r["roll"], r["studentName"], icon, r.get("time", "")), tags=(tag,))

    def on_close(self):
        self.running = self._capture_mode = False
        if self.cap: self.cap.release()
        self.root.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = AttendanceApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
