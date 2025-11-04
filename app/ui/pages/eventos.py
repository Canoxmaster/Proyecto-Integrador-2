import csv
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Optional, List, Tuple
import customtkinter as ctk
from .. import theme
from ... import db


class EventosPage(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, corner_radius=0)
        self.configure(fg_color=theme.APP_BG)

        title = ctk.CTkLabel(self, text="Eventos del sistema", font=("Arial", 22, "bold"), text_color=theme.TEXT_PRIMARY)
        title.pack(anchor="w", padx=24, pady=(20, 6))

        self._limit = 500
        self._filters = {
            "desde": None,
            "hasta": None,
            "actor_tipo": None,
            "actor_id": None,
            "texto": None,
        }
        self._current_rows: List[Tuple] = []

        filters = ctk.CTkFrame(
            self,
            fg_color=theme.CARD_BG,
            corner_radius=16,
            border_width=1,
            border_color=theme.CARD_BORDER,
        )
        filters.pack(fill="x", padx=24, pady=(10, 4))
        filters.grid_columnconfigure(3, weight=1)

        entry_cfg = dict(fg_color=theme.INPUT_BG, text_color=theme.TEXT_PRIMARY)

        self.entry_desde = ctk.CTkEntry(filters, placeholder_text="Desde (YYYY-MM-DD)", **entry_cfg)
        self.entry_desde.grid(row=0, column=0, padx=6, pady=10)

        self.entry_hasta = ctk.CTkEntry(filters, placeholder_text="Hasta (YYYY-MM-DD)", **entry_cfg)
        self.entry_hasta.grid(row=0, column=1, padx=6, pady=10)

        self.combo_actor = ctk.CTkComboBox(
            filters,
            values=["Todos", "ADMIN", "AUTORIZADO"],
            state="readonly",
            width=120,
            button_color=theme.PRIMARY,
            border_color=theme.INPUT_BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.combo_actor.set("Todos")
        self.combo_actor.grid(row=0, column=2, padx=6, pady=10)

        self.entry_buscar = ctk.CTkEntry(filters, placeholder_text="Buscar en acción/detalle", **entry_cfg)
        self.entry_buscar.grid(row=0, column=3, padx=6, pady=10, sticky="ew")

        self.entry_actor_id = ctk.CTkEntry(filters, placeholder_text="Actor ID", **entry_cfg)
        self.entry_actor_id.grid(row=0, column=4, padx=6, pady=10)

        ctk.CTkButton(
            filters,
            text="Aplicar filtros",
            width=140,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._apply_filters,
        ).grid(row=0, column=5, padx=6, pady=10)

        ctk.CTkButton(
            filters,
            text="Limpiar",
            width=110,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_MUTED,
            text_color=theme.TEXT_PRIMARY,
            command=self._clear_filters,
        ).grid(row=0, column=6, padx=6, pady=10)

        ctk.CTkButton(
            filters,
            text="Exportar CSV",
            width=140,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_HOVER,
            text_color=theme.PRIMARY_TEXT,
            command=self._export_csv,
        ).grid(row=0, column=7, padx=6, pady=10)

        self.summary_label = ctk.CTkLabel(self, text="", font=("Arial", 12), text_color=theme.TEXT_SECONDARY)
        self.summary_label.pack(anchor="w", padx=24)

        self.table = ctk.CTkScrollableFrame(
            self,
            height=600,
            fg_color=theme.CARD_BG,
            corner_radius=18,
            border_width=1,
            border_color=theme.CARD_BORDER,
        )
        self.table.pack(fill="both", expand=True, padx=24, pady=8)

        self.refresh()

    def _apply_filters(self):
        try:
            desde = self._normalize_inicio(self.entry_desde.get())
        except ValueError:
            messagebox.showerror("Fecha", "Formato inválido en 'Desde'. Usa YYYY-MM-DD opcionalmente con hora.")
            return
        try:
            hasta = self._normalize_fin(self.entry_hasta.get())
        except ValueError:
            messagebox.showerror("Fecha", "Formato inválido en 'Hasta'. Usa YYYY-MM-DD opcionalmente con hora.")
            return

        actor_tipo = self.combo_actor.get()
        if actor_tipo == "Todos":
            actor_tipo = None

        actor_id_txt = self.entry_actor_id.get().strip()
        if actor_id_txt:
            if actor_id_txt.isdigit():
                actor_id = int(actor_id_txt)
            else:
                messagebox.showerror("Actor ID", "Actor ID debe ser numérico")
                return
        else:
            actor_id = None

        texto = self.entry_buscar.get().strip() or None

        self._filters = {
            "desde": desde,
            "hasta": hasta,
            "actor_tipo": actor_tipo,
            "actor_id": actor_id,
            "texto": texto,
        }
        self.refresh()

    def _clear_filters(self):
        self.entry_desde.delete(0, "end")
        self.entry_hasta.delete(0, "end")
        self.entry_buscar.delete(0, "end")
        self.entry_actor_id.delete(0, "end")
        self.combo_actor.set("Todos")
        self._filters = {
            "desde": None,
            "hasta": None,
            "actor_tipo": None,
            "actor_id": None,
            "texto": None,
        }
        self.refresh()

    def _export_csv(self):
        if not self._current_rows:
            messagebox.showinfo("Exportar", "No hay eventos para exportar")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["ID", "Actor", "Actor ID", "Acción", "Detalle", "Fecha"])
                writer.writerows(self._current_rows)
            messagebox.showinfo("Exportar", f"Exportación completada en {path}")
        except Exception as exc:
            messagebox.showerror("Exportar", f"No se pudo exportar: {exc}")

    @staticmethod
    def _normalize_datetime(value: str, end: bool) -> Optional[str]:
        text = value.strip()
        if not text:
            return None
        formatos = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"]
        for fmt in formatos:
            try:
                dt = datetime.strptime(text, fmt)
                if fmt == "%Y-%m-%d":
                    dt = dt.replace(hour=23 if end else 0, minute=59 if end else 0, second=59 if end else 0)
                elif fmt == "%Y-%m-%d %H:%M":
                    dt = dt.replace(second=59 if end else 0)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        raise ValueError

    @classmethod
    def _normalize_inicio(cls, value: str) -> Optional[str]:
        return cls._normalize_datetime(value, end=False)

    @classmethod
    def _normalize_fin(cls, value: str) -> Optional[str]:
        return cls._normalize_datetime(value, end=True)

    def refresh(self):
        for w in self.table.winfo_children():
            w.destroy()
        rows = db.search_eventos(
            fecha_inicio=self._filters["desde"],
            fecha_fin=self._filters["hasta"],
            actor_tipo=self._filters["actor_tipo"],
            actor_id=self._filters["actor_id"],
            texto=self._filters["texto"],
            limit=self._limit,
        )
        self._current_rows = rows
        headers = [
            ("ID", 70),
            ("Actor", 90),
            ("Actor ID", 80),
            ("Acción", 130),
            ("Detalle", 420),
            ("Fecha", 160),
        ]
        for col, (label, width) in enumerate(headers):
            ctk.CTkLabel(
                self.table,
                text=label,
                font=("Arial", 13, "bold"),
                fg_color=theme.TABLE_HEADER_BG,
                text_color=theme.TABLE_HEADER_TEXT,
                width=width,
            ).grid(row=0, column=col, padx=4, pady=4, sticky="w")
        for r, row in enumerate(rows, start=1):
            eid, actor_tipo, actor_id, accion, detalle, ts = row
            valores = [eid, actor_tipo, actor_id, accion, detalle, ts]
            for c, val in enumerate(valores):
                fg = theme.TABLE_ROW_ALT_BG if r % 2 == 0 else theme.TABLE_ROW_BG
                label = ctk.CTkLabel(
                    self.table,
                    text=str(val),
                    font=("Arial", 12),
                    fg_color=fg,
                    text_color=theme.TABLE_ROW_TEXT,
                    width=headers[c][1],
                )
                label.grid(row=r, column=c, padx=4, pady=2, sticky="w")
        resumen = f"{len(rows)} evento(s)"
        if len(rows) >= self._limit:
            resumen += " (mostrando los más recientes)"
        self.summary_label.configure(text=resumen)
