"""
Chat screen — message bubbles, Meshtastic-style.

Received messages align left (teal bubble).
Sent messages align right (dark teal bubble).

Layout (480×320):
  ┌─────────────────────────────────────────────┐
  │  ✉ CHAT                          3 nodi     │
  ├─────────────────────────────────────────────┤
  │  Base Alpha  14:22                          │
  │  ┌────────────────────────────────────────┐ │
  │  │ Posizione confermata, tutto regolare.  │ │
  │  └────────────────────────────────────────┘ │
  │                              YOU  14:23     │
  │    ┌────────────────────────────────────┐   │
  │    │ Roger, ricevuto 5 su 5.            │   │
  │    └────────────────────────────────────┘   │
  ├─────────────────────────────────────────────┤
  │  [Scrivi un messaggio…         ]  [▶ INVIA] │
  ├─────────────────────────────────────────────┤
  │  ⌂ HOME   ✉ CHAT   ◉ NODI   ⚙ DEBUG        │
  └─────────────────────────────────────────────┘
"""

import tkinter as tk
from .base_screen import BaseScreen
from .icons import DOT_ON


_RECV_INDENT = 8      # px left margin for received bubbles
_SENT_INDENT = 60     # px left margin for sent bubbles (pushes right)


class ChatScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_topbar()
        self._build_messages()
        self._build_input()
        nav = self.nav_bar(self, "chat")
        nav.grid(row=3, column=0, sticky="ew")

        self.client.on_message(self._on_message)

        # Populate buffered history
        for msg in self.client.get_messages():
            self._append(msg)

    # ------------------------------------------------------------------ #
    # Top bar                                                              #
    # ------------------------------------------------------------------ #

    def _build_topbar(self):
        bar = tk.Frame(self, bg=self.topbar)
        bar.grid(row=0, column=0, sticky="ew")

        tk.Label(bar, text="✉ CHAT", font=self.f_bold,
                 fg=self.fg, bg=self.topbar).pack(side="left", padx=8, pady=4)

        self._lbl_nodes = tk.Label(bar, text="", font=self.f_small,
                                   fg=self.dim, bg=self.topbar)
        self._lbl_nodes.pack(side="right", padx=10)

    # ------------------------------------------------------------------ #
    # Message area (Text widget with margin-based bubbles)                #
    # ------------------------------------------------------------------ #

    def _build_messages(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=1, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._txt = tk.Text(
            frame,
            font=self.f_normal,
            fg=self.fg,
            bg=self.bg,
            relief="flat",
            state="disabled",
            wrap="word",
            cursor="",
            spacing1=2,
            spacing3=2,
        )
        self._txt.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(frame, command=self._txt.yview,
                          bg=self.card, troughcolor=self.bg, width=6)
        sb.grid(row=0, column=1, sticky="ns")
        self._txt.config(yscrollcommand=sb.set)

        self._configure_tags()

    def _configure_tags(self):
        t = self._txt

        # Sender header lines
        t.tag_configure("hdr_recv",
                        foreground=self.accent, font=self.f_small,
                        lmargin1=_RECV_INDENT + 8, lmargin2=_RECV_INDENT + 8)
        t.tag_configure("hdr_sent",
                        foreground=self.dim, font=self.f_small,
                        justify="right",
                        rmargin=8)

        # Bubble body lines — received
        t.tag_configure("body_recv",
                        foreground=self.fg,
                        background=self.recv_bg,
                        font=self.f_normal,
                        lmargin1=_RECV_INDENT + 6, lmargin2=_RECV_INDENT + 6,
                        rmargin=80,
                        spacing1=4, spacing3=4)

        # Bubble body lines — sent
        t.tag_configure("body_sent",
                        foreground=self.fg,
                        background=self.sent_bg,
                        font=self.f_normal,
                        lmargin1=_SENT_INDENT, lmargin2=_SENT_INDENT,
                        rmargin=8,
                        spacing1=4, spacing3=4)

        # Spacer
        t.tag_configure("spacer", font=("TkDefaultFont", 3))

        # Signal meta line
        t.tag_configure("meta_recv",
                        foreground=self.dim, font=self.f_small,
                        lmargin1=_RECV_INDENT + 6, lmargin2=_RECV_INDENT + 6,
                        spacing3=6)
        t.tag_configure("meta_sent",
                        foreground=self.dim, font=self.f_small,
                        justify="right",
                        rmargin=8,
                        spacing3=6)

    # ------------------------------------------------------------------ #
    # Input bar                                                            #
    # ------------------------------------------------------------------ #

    def _build_input(self):
        bar = tk.Frame(self, bg=self.card)
        bar.grid(row=2, column=0, sticky="ew")
        bar.columnconfigure(0, weight=1)

        self._entry_var = tk.StringVar()
        self._entry = tk.Entry(
            bar,
            textvariable=self._entry_var,
            font=self.f_normal,
            fg=self.fg,
            bg=self.bg,
            insertbackground=self.accent,
            relief="flat",
            bd=6,
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(8, 4), pady=6)
        self._entry.insert(0, "")
        self._entry.bind("<Return>", lambda _e: self._send())
        self.bind_touch_entry(self._entry)

        send_btn = tk.Button(
            bar, text="▶",
            font=self.f_icon,
            fg=self.bg, bg=self.accent,
            activeforeground=self.bg, activebackground=self.fg,
            relief="flat", bd=0,
            padx=12, pady=4,
            command=self._send,
        )
        send_btn.grid(row=0, column=1, padx=(0, 8), pady=6)

    # ------------------------------------------------------------------ #
    # Logic                                                                #
    # ------------------------------------------------------------------ #

    def on_enter(self):
        self._update_nodes()

    def on_scroll(self, direction: int):
        self._txt.yview_scroll(direction, "units")

    def _on_message(self, msg):
        self._txt.after(0, self._append, msg)

    def _append(self, msg):
        is_you = msg.sender == "YOU"
        ts = msg.timestamp.strftime("%H:%M")
        meta = f"rssi {msg.rssi}  snr {msg.snr:.1f}  {msg.hops}hop"

        self._txt.configure(state="normal")

        if is_you:
            self._txt.insert("end", f"TU  {ts}\n", "hdr_sent")
            self._txt.insert("end", f"{msg.text}\n", "body_sent")
            self._txt.insert("end", f"{meta}\n", "meta_sent")
        else:
            self._txt.insert("end", f"{msg.sender}  {ts}\n", "hdr_recv")
            self._txt.insert("end", f"{msg.text}\n", "body_recv")
            self._txt.insert("end", f"{meta}\n", "meta_recv")

        self._txt.insert("end", "\n", "spacer")
        self._txt.see("end")
        self._txt.configure(state="disabled")
        self._update_nodes()

    def _send(self):
        text = self._entry_var.get().strip()
        if not text:
            return
        if self.client.send(text):
            self._entry_var.set("")
        else:
            orig = self._entry.cget("bg")
            self._entry.configure(bg="#3D1010")
            self._entry.after(600, lambda: self._entry.configure(bg=orig))

    def _update_nodes(self):
        n = len(self.client.nodes)
        self._lbl_nodes.config(
            text=f"{DOT_ON} {n} nod{'o' if n == 1 else 'i'}")
