"""
theme.py - Theme và các thành phần giao diện dùng lại cho YOLO Detector.

Chỉ chứa phần "nhìn": màu, theme sáng/tối, card, file tile, hàng kết quả...
Toàn bộ màu lấy từ token của Material 3 (ft.Colors.PRIMARY, SURFACE_...) nên
tự đổi đúng theo chế độ sáng/tối. Muốn đổi thương hiệu chỉ cần sửa SEED_COLOR.
"""
from __future__ import annotations

import zlib

import flet as ft

# --------------------------------------------------------------------------- #
# Hằng số thiết kế
# --------------------------------------------------------------------------- #
SEED_COLOR = "#4F46E5"  # indigo - toàn bộ bảng màu M3 sinh ra từ màu này
RADIUS_CARD = 16
RADIUS_INNER = 12
GAP = 16

# Màu cho từng class (chọn theo hash của tên để cùng class luôn cùng màu)
CLASS_COLORS = [
    "#EF4444", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6",
    "#EC4899", "#14B8A6", "#F97316", "#6366F1", "#84CC16",
]


def class_color(name: str) -> str:
    return CLASS_COLORS[zlib.crc32(name.encode("utf-8")) % len(CLASS_COLORS)]


# --------------------------------------------------------------------------- #
# Theme
# --------------------------------------------------------------------------- #
def light_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=SEED_COLOR, use_material3=True)


def dark_theme() -> ft.Theme:
    return ft.Theme(color_scheme_seed=SEED_COLOR, use_material3=True)


def apply_theme(page: ft.Page, mode: ft.ThemeMode = ft.ThemeMode.SYSTEM) -> None:
    page.theme = light_theme()
    page.dark_theme = dark_theme()
    page.theme_mode = mode
    page.padding = 0


THEME_CYCLE = [ft.ThemeMode.SYSTEM, ft.ThemeMode.LIGHT, ft.ThemeMode.DARK]
THEME_ICON = {
    ft.ThemeMode.SYSTEM: ft.Icons.BRIGHTNESS_AUTO,
    ft.ThemeMode.LIGHT: ft.Icons.LIGHT_MODE_OUTLINED,
    ft.ThemeMode.DARK: ft.Icons.DARK_MODE_OUTLINED,
}
THEME_LABEL = {
    ft.ThemeMode.SYSTEM: "Theo hệ thống",
    ft.ThemeMode.LIGHT: "Sáng",
    ft.ThemeMode.DARK: "Tối",
}


def next_theme_mode(current: ft.ThemeMode) -> ft.ThemeMode:
    i = THEME_CYCLE.index(current) if current in THEME_CYCLE else 0
    return THEME_CYCLE[(i + 1) % len(THEME_CYCLE)]


# --------------------------------------------------------------------------- #
# Khung & tiêu đề
# --------------------------------------------------------------------------- #
def card(title: str, icon: str, *controls: ft.Control, trailing: ft.Control | None = None,
         expand: bool = False) -> ft.Container:
    """Khối nội dung bo góc có tiêu đề + icon."""
    header = ft.Row(
        [
            ft.Icon(icon, size=20, color=ft.Colors.PRIMARY),
            ft.Text(title, size=16, weight=ft.FontWeight.W_600, expand=True),
            *([trailing] if trailing else []),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    return ft.Container(
        content=ft.Column([header, *controls], spacing=GAP, tight=not expand,
                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        padding=20,
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=RADIUS_CARD,
        expand=expand,
    )


def muted(text: str, size: int = 12) -> ft.Text:
    return ft.Text(text, size=size, color=ft.Colors.ON_SURFACE_VARIANT)


def app_logo() -> ft.Container:
    return ft.Container(
        content=ft.Icon(ft.Icons.CENTER_FOCUS_STRONG, color=ft.Colors.ON_PRIMARY, size=20),
        width=36,
        height=36,
        border_radius=10,
        alignment=ft.Alignment.CENTER,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.PRIMARY, ft.Colors.TERTIARY],
        ),
    )


# --------------------------------------------------------------------------- #
# File tile: 1 dòng chọn file (ảnh / .pt)
# --------------------------------------------------------------------------- #
class FileTile:
    def __init__(self, icon: str, title: str, hint: str, button_text: str, on_pick):
        self._icon_name = icon
        self._hint = hint
        self.icon = ft.Icon(icon, color=ft.Colors.PRIMARY, size=22)
        self.icon_box = ft.Container(
            content=self.icon,
            width=44,
            height=44,
            border_radius=RADIUS_INNER,
            bgcolor=ft.Colors.PRIMARY_CONTAINER,
            alignment=ft.Alignment.CENTER,
        )
        self.title = ft.Text(title, size=14, weight=ft.FontWeight.W_600)
        self.subtitle = ft.Text(
            hint, size=12, color=ft.Colors.ON_SURFACE_VARIANT,
            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.spinner = ft.ProgressRing(width=18, height=18, stroke_width=2.5, visible=False)
        self.button = ft.OutlinedButton(button_text, icon=ft.Icons.FOLDER_OPEN, on_click=on_pick)
        self.control = ft.Container(
            content=ft.Row(
                [
                    self.icon_box,
                    ft.Column([self.title, self.subtitle], spacing=2, expand=True),
                    self.spinner,
                    self.button,
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=RADIUS_INNER,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

    def set_file(self, name: str) -> None:
        self.subtitle.value = name
        self.subtitle.color = ft.Colors.ON_SURFACE
        self.icon.icon = ft.Icons.CHECK_CIRCLE
        self.icon.color = ft.Colors.ON_PRIMARY
        self.icon_box.bgcolor = ft.Colors.PRIMARY
        self.control.border = ft.Border.all(1.5, ft.Colors.PRIMARY)
        self.button.content = "Đổi file"

    def set_loading(self, loading: bool, text: str | None = None) -> None:
        self.spinner.visible = loading
        self.button.disabled = loading
        if text is not None:
            self.subtitle.value = text
            self.subtitle.color = ft.Colors.ON_SURFACE_VARIANT


# --------------------------------------------------------------------------- #
# Trạng thái (1 dòng icon + chữ, đổi màu theo loại)
# --------------------------------------------------------------------------- #
_STATUS_STYLE = {
    "info": (ft.Icons.INFO_OUTLINE, ft.Colors.ON_SURFACE_VARIANT),
    "success": (ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.PRIMARY),
    "warning": (ft.Icons.WARNING_AMBER_ROUNDED, ft.Colors.TERTIARY),
    "error": (ft.Icons.ERROR_OUTLINE, ft.Colors.ERROR),
    "loading": (ft.Icons.HOURGLASS_TOP, ft.Colors.ON_SURFACE_VARIANT),
}


class StatusLine:
    def __init__(self, message: str = "Chọn ảnh và file .pt để bắt đầu."):
        self.icon = ft.Icon(ft.Icons.INFO_OUTLINE, size=18)
        self.text = ft.Text(size=13, expand=True)
        self.control = ft.Row([self.icon, self.text], spacing=8,
                              vertical_alignment=ft.CrossAxisAlignment.START)
        self.set("info", message)

    def set(self, kind: str, message: str) -> None:
        icon, color = _STATUS_STYLE[kind]
        self.icon.icon = icon
        self.icon.color = color
        self.text.value = message
        self.text.color = color


def toast(page: ft.Page, message: str, kind: str = "info") -> None:
    icon, _ = _STATUS_STYLE[kind]
    bg = ft.Colors.ERROR_CONTAINER if kind == "error" else ft.Colors.INVERSE_SURFACE
    fg = ft.Colors.ON_ERROR_CONTAINER if kind == "error" else ft.Colors.ON_INVERSE_SURFACE
    page.show_dialog(
        ft.SnackBar(
            content=ft.Row([ft.Icon(icon, color=fg, size=18), ft.Text(message, color=fg, expand=True)],
                           spacing=10),
            bgcolor=bg,
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=3500,
        )
    )


# --------------------------------------------------------------------------- #
# Ô thống kê & hàng kết quả
# --------------------------------------------------------------------------- #
class StatTile:
    def __init__(self, icon: str, label: str, value: str = "—", col: dict | int = 4):
        self.value = ft.Text(value, size=20, weight=ft.FontWeight.W_700)
        self.control = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=ft.Colors.PRIMARY),
                    ft.Column([self.value, muted(label)], spacing=0, tight=True),
                ],
                spacing=12,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=RADIUS_INNER,
            col=col,
        )

    def set(self, value: str) -> None:
        self.value.value = value


def detection_row(name: str, conf: float) -> ft.Control:
    color = class_color(name)
    return ft.Column(
        [
            ft.Row(
                [
                    ft.Container(width=10, height=10, bgcolor=color, border_radius=5),
                    ft.Text(name, size=14, weight=ft.FontWeight.W_500, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{conf:.0%}", size=13, weight=ft.FontWeight.W_600, color=color),
                ],
                spacing=10,
            ),
            ft.ProgressBar(value=conf, color=color, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                           bar_height=6, border_radius=3),
        ],
        spacing=6,
    )


def empty_state(icon: str, title: str, subtitle: str) -> ft.Control:
    return ft.Column(
        [
            ft.Container(
                content=ft.Icon(icon, size=34, color=ft.Colors.PRIMARY),
                width=72, height=72, border_radius=36,
                bgcolor=ft.Colors.PRIMARY_CONTAINER, alignment=ft.Alignment.CENTER,
            ),
            ft.Text(title, size=15, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER),
            ft.Text(subtitle, size=12, color=ft.Colors.ON_SURFACE_VARIANT,
                    text_align=ft.TextAlign.CENTER),
        ],
        spacing=10,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )