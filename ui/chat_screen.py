"""
Chat screen — message history and quick-send input.

Layout (480×320):
  ┌─────────────────────────────────────┐
  │  CHAT MESH                  3 nodi  │
  ├─────────────────────────────────────┤
  │  [Base Alpha] 14:22                 │
  │  Posizione confermata.              │
  │  [YOU] 14:23                        │
  │  Roger.                             │
  │  …                                  │
  ├─────────────────────────────────────┤
  │  [________________] [INVIA]         │
  ├─────────────────────────────────────┤
  │ [HOME] [CHAT] [NODI] [DEBUG]        │
  └─────────────────────────────────────┘
"""

import tkinter as tk
from .base_screen import BaseScreen


class ChatScreen(BaseScreen):

    def build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        self._build_messages()
        self._build_input()
        nav = self.nav_bar(self, "chat")
        nav.grid(row=3, column=0, sticky="ew")

        # Register once — callbacks are persistent across screen switches
        self.client.on_message(self._on_message)

        # Populate with buffered history
        for msg in self.client.get_messages():
            self._append(msg)

    # ------------------------------------------------------------------ #
    # Header                                                               #
    # ------------------------------------------------------------------ #

    def _build_header(self):
        hdr = tk.Frame(self, bg=self.dim)
        hdr.grid(row=0, column=0, sticky="ew")

        tk.Label(hdr, text="CHAT MESH", font=self.font_large,
                 fg=self.fg, bg=self.dim).pack(side="left", padx=8, pady=2)

        self._lbl_nodes = tk.Label(hdr, text="", font=self.font_small,
                                   fg=self.accent, bg=self.dim)
        self._lbl_nodes.pack(side="right", padx=8)

    # ------------------------------------------------------------------ #
    # Message area                                                         #
    # ------------------------------------------------------------------ #

    def _build_messages(self):
        frame = tk.Frame(self, bg=self.bg)
        frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=2)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self._txt = tk.Text(
            frame,
            font=self.font_normal,
            fg=self.fg, bg=self.bg,
            relief="flat",
            state="disabled",
            wrap="word",
            cursor="",
        )
        self._txt.grid(row=0, column=0, sticky="nsew")

        sb = tk.Scrollbar(frame, command=self._txt.yview, bg=self.dim,
                          troughcolor=self.bg, width=8)
        sb.grid(row=0, column=1, sticky="ns")
        self._txt.config(yscrollcommand=sb.set)

        # Tag styles
        self._txt.tag_configure("sender_you", foreground=self.fg,
                                font=self.font_bold)
        self._txt.tag_configure("sender_other", foreground=self.accent,
                                font=self.font_bold)
        self._txt.tag_configure("meta", foreground=self.dim,
                                font=self.font_small)
        self._txt.tag_configure("body", foreground=self.fg,
                                font=self.font_normal)

    # ------------------------------------------------------------------ #
    # Input bar                                                            #
    # ------------------------------------------------------------------ #

    def _build_input(self):
        bar = tk.Frame(self, bg=self.bg)
        bar.grid(row=2, column=0, sticky="ew", padx=4, pady=2)
        bar.columnconfigure(0, weight=1)

        self._entry_var = tk.StringVar()
        self._entry = tk.Entry(
            bar,
            textvariable=self._entry_var,
            font=self.font_normal,
            fg=self.fg, bg="#111111",
            insertbackground=self.fg,
            relief="flat", bd=2,
        )
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self._entry.bind("<Return>", lambda _e: self._send())

        self._btn_send = self.button(bar, "INVIA", self._send, width=6)
        self._btn_send.grid(row=0, column=1)

    # ------------------------------------------------------------------ #
    # Logic                                                                #
    # ------------------------------------------------------------------ #

    def on_enter(self):
        self._update_node_count()
        self._entry.focus_set()

    def _on_message(self, msg):
        # Called from background thread — schedule on GUI thread
        self._txt.after(0, self._append, msg)

    def _append(self, msg):
        from datetime import datetime
        is_you = msg.sender == "YOU"
        time_str = msg.timestamp.strftime("%H:%M")

        self._txt.configure(state="normal")

        sender_tag = "sender_you" if is_you else "sender_other"
        meta = f"  {time_str}  rssi:{msg.rssi}  snr:{msg.snr:.1f}  hop:{msg.hops}"

        self._txt.insert("end", f"[{msg.sender}]", sender_tag)
        self._txt.insert("end", f"{meta}\n", "meta")
        self._txt.insert("end", f"  {msg.text}\n\n", "body")
        self._txt.see("end")
        self._txt.configure(state="disabled")

        self._update_node_count()

    def _send(self):
        text = self._entry_var.get().strip()
        if not text:
            return
        sent = self.client.send(text)
        if sent:
            self._entry_var.set("")
        else:
            # Visual feedback for failed send
            self._entry.configure(bg="#330000")
            self._entry.after(800, lambda: self._entry.configure(bg="#111111"))

    def _update_node_count(self):
        n = len(self.client.nodes)
        self._lbl_nodes.config(text=f"{n} nodi")
