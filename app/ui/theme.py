import customtkinter as ctk

# Core palette (tailored for a bright, vibrant dashboard)
PRIMARY = "#6366F1"          # Indigo 500
PRIMARY_HOVER = "#4F46E5"    # Indigo 600
PRIMARY_TEXT = "#F8FAFC"
ACCENT = "#22D3EE"           # Cyan 400
ACCENT_MUTED = "#67E8F9"

SUCCESS = "#22C55E"
SUCCESS_HOVER = "#16A34A"
WARNING = "#FACC15"
DANGER = "#F87171"
DANGER_HOVER = "#EF4444"

APP_BG = "#EEF2FF"           # Soft indigo tint
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E0E7FF"
TABLE_HEADER_BG = "#E0E7FF"
TABLE_HEADER_TEXT = "#312E81"
TABLE_ROW_BG = "#FFFFFF"
TABLE_ROW_ALT_BG = "#F5F3FF"
TABLE_ROW_TEXT = "#1F2937"
TABLE_MUTED_TEXT = "#6B7280"

SIDEBAR_BG = "#111827"
SIDEBAR_BORDER = "#1F2937"
SIDEBAR_ACTIVE = "#4F46E5"
SIDEBAR_ACTIVE_HOVER = "#4338CA"
SIDEBAR_TEXT = "#E5E7EB"
SIDEBAR_TEXT_MUTED = "#9CA3AF"

TEXT_PRIMARY = "#111827"
TEXT_SECONDARY = "#4B5563"

INPUT_BG = "#F9FAFB"
INPUT_BORDER = "#D1D5DB"

TRANSPARENT = "transparent"


def apply_global_theme() -> None:
    """Configure CustomTkinter defaults to match the palette."""
    try:
        ctk.set_appearance_mode("light")
    except Exception:
        pass
    # CustomTkinter themes expect a JSON file; we keep manual styling per widget instead.
    # Still, ensure rounded corners feel consistent.
    try:
        ctk.set_default_color_theme("blue")
    except Exception:
        pass
