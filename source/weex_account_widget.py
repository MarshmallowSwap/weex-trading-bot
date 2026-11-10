"""Read-only desktop card for the WEEX Futures account.

The app only requests the documented account-balance GET operation through
the existing WEEX reader, which applies the local API budget guard. It has no
order, position-management, or Telegram capabilities.
"""
from __future__ import annotations

import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tkinter import ttk
from typing import Callable, Any

REFRESH_SECONDS = 60
STALE_AFTER_SECONDS = 150
WEEX_ROOT = Path(r"D:\FUNDSHOT\weex_alerts")
BALANCE_PATH = "/capi/v3/account/balance"
POSITIONS_PATH = "/capi/v3/account/position/allPosition"
READ_OPERATIONS = {
    BALANCE_PATH: "get_capi_v3_account_balance",
    POSITIONS_PATH: "get_capi_v3_account_position_allPosition",
}
BG = "#05080e"
CARD = "#081a32"
MUTED = "#8fa3bd"
CYAN = "#18c9f4"
GREEN = "#2cdda8"
RED = "#ff4b59"


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("BALANCE_VALUE_INVALID") from exc
    if not result.is_finite():
        raise ValueError("BALANCE_VALUE_INVALID")
    return result


def parse_balance(rows: Any) -> dict[str, Decimal]:
    """Validate and normalize the USDT row returned by WEEX."""
    if not isinstance(rows, list):
        raise ValueError("BALANCE_SCHEMA_INVALID")
    matches = [row for row in rows if isinstance(row, dict) and row.get("asset") == "USDT"]
    if len(matches) != 1:
        raise ValueError("USDT_BALANCE_ROW_INVALID")
    row = matches[0]
    balance = _decimal(row.get("balance"))
    unrealized = _decimal(row.get("unrealizePnl"))
    return {
        "balance": balance,
        "unrealized": unrealized,
        "equity": balance + unrealized,
    }


def load_live_balance(query: Callable[[str], Any]) -> dict[str, Decimal]:
    """Fetch account balance only; query must be the existing guarded GET reader."""
    return parse_balance(query(BALANCE_PATH))


def parse_positions(rows: Any) -> list[dict[str, Any]]:
    """Validate active USDT futures positions and retain only display fields."""
    if not isinstance(rows, list):
        raise ValueError("POSITIONS_SCHEMA_INVALID")
    active = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("POSITIONS_SCHEMA_INVALID")
        if row.get("asset") != "USDT":
            continue
        symbol = row.get("symbol")
        side = row.get("side")
        if not isinstance(symbol, str) or not symbol.endswith("USDT") or side not in ("LONG", "SHORT"):
            raise ValueError("POSITION_IDENTITY_INVALID")
        quantity = _decimal(row.get("size"))
        if quantity == 0:
            continue
        if quantity < 0:
            raise ValueError("POSITION_SIZE_INVALID")
        key = (symbol, side, str(row.get("id", "")))
        if key in seen:
            raise ValueError("DUPLICATE_POSITION")
        seen.add(key)
        active.append({
            "symbol": symbol,
            "side": side,
            "leverage": _decimal(row.get("leverage")),
            "quantity": quantity,
            "pnl": _decimal(row.get("unrealizePnl")),
        })
    return sorted(active, key=lambda p: (p["symbol"], p["side"]))


def load_snapshot(query: Callable[[str], Any]) -> dict[str, Any]:
    return {
        "account": parse_balance(query(BALANCE_PATH)),
        "positions": parse_positions(query(POSITIONS_PATH)),
    }


class LiveReadOnlySource:
    """Use the existing budgeted SDK client, whose transport rejects all writes."""
    def __init__(self):
        if str(WEEX_ROOT) not in sys.path:
            sys.path.insert(0, str(WEEX_ROOT))
        from weex_simple_bot import make_client, read

        self.client = make_client()
        self.read = read

    def __call__(self, path: str) -> Any:
        operation = READ_OPERATIONS.get(path)
        if operation is None:
            raise PermissionError("ACCOUNT_WIDGET_PATH_NOT_ALLOWED")
        return self.read(self.client, operation)


class AccountWidget:
    def __init__(self, root: tk.Tk, query: Callable[[str], Any] | None = None):
        self.root = root
        self.query = query or LiveReadOnlySource()
        self._result: tuple[dict[str, Decimal] | None, str | None, float] | None = None
        self._fetching = False
        self._closing = False
        self.root.title("WEEX · Futures account")
        self.root.configure(bg=BG)
        self.root.geometry("1030x475+80+80")
        self.root.minsize(820, 350)
        self.root.attributes("-topmost", False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._style()
        self._build()
        self._refresh_now()
        self.root.after(250, self._consume_result)
        self.root.after(REFRESH_SECONDS * 1000, self._refresh_now)

    def _style(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Root.TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("Title.TLabel", background=CARD, foreground="white", font=("Segoe UI", 17, "bold"))
        style.configure("Caption.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Value.TLabel", background=CARD, foreground="white", font=("Segoe UI", 25, "bold"))
        style.configure("Unit.TLabel", background=CARD, foreground=CYAN, font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", background=CARD, foreground=GREEN, font=("Segoe UI", 9))
        style.configure("Footnote.TLabel", background=CARD, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Treeview", background="#0a203b", foreground="white", fieldbackground="#0a203b",
                        rowheight=27, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#102946", foreground=MUTED,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#154369")])
        style.configure("TCheckbutton", background=CARD, foreground=MUTED)

    def _build(self) -> None:
        outer = ttk.Frame(self.root, style="Root.TFrame", padding=8)
        outer.pack(fill="both", expand=True)
        self.card = ttk.Frame(outer, style="Card.TFrame", padding=(20, 14))
        self.card.pack(fill="both", expand=True)
        header = ttk.Frame(self.card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="Futures account", style="Title.TLabel").pack(side="left")
        ttk.Checkbutton(header, text="Sempre in primo piano", command=self._toggle_topmost).pack(side="right")

        metrics = ttk.Frame(self.card, style="Card.TFrame")
        metrics.pack(fill="x", expand=False, pady=(15, 8))
        for col, (key, label) in enumerate((
            ("equity", "Account equity"),
            ("balance", "Account balance"),
            ("unrealized", "Unrealized PnL"),
        )):
            block = ttk.Frame(metrics, style="Card.TFrame")
            block.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 14, 0))
            ttk.Label(block, text=label, style="Caption.TLabel").pack(anchor="w")
            row = ttk.Frame(block, style="Card.TFrame")
            row.pack(anchor="w", pady=(6, 0))
            value = ttk.Label(row, text="—", style="Value.TLabel")
            value.pack(side="left")
            ttk.Label(row, text=" USDT", style="Unit.TLabel").pack(side="left", anchor="s", pady=(0, 5))
            self.__dict__[f"{key}_label"] = value
            metrics.columnconfigure(col, weight=1, uniform="metric")

        positions_header = ttk.Frame(self.card, style="Card.TFrame")
        positions_header.pack(fill="x", pady=(6, 5))
        ttk.Label(positions_header, text="Posizioni aperte", style="Caption.TLabel").pack(side="left")
        self.position_count = ttk.Label(positions_header, text="—", style="Caption.TLabel")
        self.position_count.pack(side="right")
        table_wrap = ttk.Frame(self.card, style="Card.TFrame")
        table_wrap.pack(fill="both", expand=True)
        columns = ("symbol", "side", "leverage", "quantity", "pnl")
        self.positions_table = ttk.Treeview(table_wrap, columns=columns, show="headings", height=5, selectmode="none")
        for col, title, width, anchor in (
            ("symbol", "Coppia", 210, "w"),
            ("side", "Lato", 120, "center"),
            ("leverage", "Leva", 100, "center"),
            ("quantity", "Quantità", 180, "e"),
            ("pnl", "PnL non realizzato", 220, "e"),
        ):
            self.positions_table.heading(col, text=title)
            self.positions_table.column(col, width=width, anchor=anchor, stretch=(col == "symbol"))
        self.positions_table.tag_configure("positive", foreground=GREEN)
        self.positions_table.tag_configure("negative", foreground=RED)
        position_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.positions_table.yview)
        self.positions_table.configure(yscrollcommand=position_scroll.set)
        self.positions_table.pack(side="left", fill="both", expand=True)
        position_scroll.pack(side="right", fill="y")

        footer = ttk.Frame(self.card, style="Card.TFrame")
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, text="WEEX FUTURES · SOLA LETTURA", style="Footnote.TLabel").pack(side="left")
        self.status_label = ttk.Label(footer, text="Connessione in avvio…", style="Status.TLabel")
        self.status_label.pack(side="right")

        # The card can be repositioned without forcing it to stay above work windows.
        for widget in (self.card, header):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

    def _toggle_topmost(self) -> None:
        self.root.attributes("-topmost", not self.root.attributes("-topmost"))

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x, self._drag_y = event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y()

    def _drag_move(self, event: tk.Event) -> None:
        self.root.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _refresh_now(self) -> None:
        if self._closing or self._fetching:
            return
        self._fetching = True

        def worker() -> None:
            try:
                data = load_snapshot(self.query)
                result = (data, None, time.time())
            except Exception as exc:
                # Do not display exception text: SDK errors can contain request details.
                result = (None, type(exc).__name__, time.time())
            self._result = result
            self._fetching = False

        threading.Thread(target=worker, name="weex-account-read", daemon=True).start()
        self.root.after(REFRESH_SECONDS * 1000, self._refresh_now)

    def _consume_result(self) -> None:
        if self._closing:
            return
        if self._result is not None:
            data, error, observed_at = self._result
            self._result = None
            if data is not None:
                account = data["account"]
                self.equity_label.configure(text=self._format(account["equity"]))
                self.balance_label.configure(text=self._format(account["balance"]))
                self.unrealized_label.configure(text=self._format(account["unrealized"]))
                self.unrealized_label.configure(foreground=GREEN if account["unrealized"] >= 0 else RED)
                for item in self.positions_table.get_children():
                    self.positions_table.delete(item)
                for position in data["positions"]:
                    pnl = position["pnl"]
                    tag = "positive" if pnl >= 0 else "negative"
                    self.positions_table.insert("", "end", values=(
                        position["symbol"], position["side"], f"{self._format(position['leverage'])}×",
                        self._format(position["quantity"]), f"{self._format(pnl)} USDT",
                    ), tags=(tag,))
                count = len(data["positions"])
                self.position_count.configure(text=f"{count} {'posizione' if count == 1 else 'posizioni'}")
                if count == 0:
                    self.positions_table.insert("", "end", values=("Nessuna posizione aperta", "", "", "", ""))
                self.status_label.configure(text=f"AGGIORNATO {datetime.fromtimestamp(observed_at).strftime('%H:%M:%S')}", foreground=GREEN)
                self._last_good = observed_at
            else:
                last_good = getattr(self, "_last_good", None)
                if last_good is None or time.time() - last_good > STALE_AFTER_SECONDS:
                    self.status_label.configure(text="DATI NON DISPONIBILI · RITENTO", foreground=RED)
                else:
                    self.status_label.configure(text=f"DATI NON AGGIORNATI · ULTIMO {datetime.fromtimestamp(last_good).strftime('%H:%M:%S')}", foreground=RED)
        self.root.after(250, self._consume_result)

    @staticmethod
    def _format(value: Decimal) -> str:
        return f"{value:,.4f}"

    def close(self) -> None:
        self._closing = True
        self.root.destroy()


def main() -> None:
    app = tk.Tk()
    AccountWidget(app)
    app.mainloop()


if __name__ == "__main__":
    main()
