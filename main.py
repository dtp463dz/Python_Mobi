"""
YOLO Detector - app Flet, chạy được cả desktop lẫn web.
Cài đặt:  pip install "flet[all]>=1.0" ultralytics opencv-python
Chạy:     flet run main.py          (desktop)
          flet run --web main.py    (web)

Cấu trúc:
  main.py   - logic (upload, load model, detect) + bố cục màn hình
  theme.py  - theme sáng/tối + các thành phần UI dùng lại

Web mode: trình duyệt không cho server biết đường dẫn file trên máy người dùng,
nên file ảnh / .pt phải được UPLOAD lên server (thư mục ./uploads) rồi mới đọc.
Chạy desktop và web cùng lúc: mở hai terminal và đặt FLET_UPLOAD_DIR khác nhau
cho mỗi lệnh để các file upload không ghi đè lên nhau.
"""
import asyncio
import base64
import os
import secrets
import time
from pathlib import Path

import cv2
import flet as ft

import theme as T

# Web mode: Flet cần khoá bí mật để ký URL upload. Nếu bạn chưa đặt FLET_SECRET_KEY
# thì tự sinh khoá ngẫu nhiên cho mỗi lần chạy (đủ dùng cho app cá nhân/local).
os.environ.setdefault("FLET_SECRET_KEY", secrets.token_urlsafe(32))

UPLOAD_DIR = Path(
    os.environ.get("FLET_UPLOAD_DIR", str(Path(__file__).resolve().parent / "uploads"))
).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_model_cache = {"path": None, "model": None}


# --------------------------------------------------------------------------- #
# Logic (không đụng tới UI)
# --------------------------------------------------------------------------- #
def load_model(weights_path: str):
    """Chỉ nạp lại model khi người dùng đổi file .pt."""
    if _model_cache["path"] != weights_path:
        from ultralytics import YOLO  # import trễ để app mở nhanh

        _model_cache["model"] = YOLO(weights_path)
        _model_cache["path"] = weights_path
    return _model_cache["model"]


def file_to_b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def run_detection(image_path: str, weights_path: str, imgsz: int, conf: float):
    """Chạy trong thread riêng để không làm đứng giao diện.

    Trả về (ảnh kết quả base64, [(tên class, độ tin cậy)...] giảm dần, số giây).
    """
    t0 = time.perf_counter()
    model = load_model(weights_path)
    result = model.predict(image_path, imgsz=imgsz, conf=conf, verbose=False)[0]

    annotated = result.plot()  # ảnh BGR đã vẽ box
    ok, buf = cv2.imencode(".jpg", annotated)
    if not ok:
        raise RuntimeError("Không mã hoá được ảnh kết quả")
    b64 = base64.b64encode(buf.tobytes()).decode()

    names = result.names
    dets = sorted(
        ((names[int(b.cls)], float(b.conf)) for b in result.boxes),
        key=lambda d: d[1],
        reverse=True,
    )
    return b64, dets, time.perf_counter() - t0


# --------------------------------------------------------------------------- #
# Giao diện
# --------------------------------------------------------------------------- #
async def main(page: ft.Page):
    page.title = "YOLO Detector"
    page.scroll = ft.ScrollMode.AUTO
    T.apply_theme(page)
    if not page.web:
        page.window.min_width = 420
        page.window.min_height = 640

    state = {"image": None, "weights": None, "orig_b64": None, "result_b64": None, "busy": False}
    upload_done: dict[str, asyncio.Event] = {}
    upload_error: dict[str, str] = {}

    # ---- khai báo control ------------------------------------------------- #
    status = T.StatusLine()
    busy_bar = ft.ProgressBar(visible=False, bar_height=4, border_radius=2)

    tile_weights = T.FileTile(
        ft.Icons.MODEL_TRAINING, "Model YOLO (.pt)", "Chưa chọn file trọng số",
        "Chọn file", None,  # on_click gán bên dưới, sau khi định nghĩa pick_weights
    )
    tile_image = T.FileTile(
        ft.Icons.IMAGE_OUTLINED, "Ảnh đầu vào", "Chưa chọn ảnh",
        "Chọn ảnh", None,  # on_click gán bên dưới, sau khi định nghĩa pick_image
    )

    imgsz_seg = ft.SegmentedButton(
        segments=[
            ft.Segment(value="640", label="640 px", icon=ft.Icons.SPEED),
            ft.Segment(value="1280", label="1280 px", icon=ft.Icons.HIGH_QUALITY),
        ],
        selected=["640"],
        allow_empty_selection=False,
        expand=True,
    )
    imgsz_hint = T.muted("Nhanh hơn, phù hợp vật thể lớn.")

    conf_value = ft.Text("0.25", size=14, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY)
    conf_slider = ft.Slider(min=0.05, max=0.95, value=0.25, divisions=18, expand=True)

    btn_detect = ft.FilledButton(
        "Phân tích ảnh", icon=ft.Icons.AUTO_AWESOME, height=48, expand=True, disabled=True,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=T.RADIUS_INNER)),
    )

    view_seg = ft.SegmentedButton(
        segments=[
            ft.Segment(value="orig", label="Ảnh gốc"),
            ft.Segment(value="result", label="Kết quả"),
        ],
        selected=["result"],
        allow_empty_selection=False,
        visible=False,
    )

    empty = T.empty_state(
        ft.Icons.ADD_PHOTO_ALTERNATE_OUTLINED,
        "Chưa có ảnh",
        "Chọn ảnh ở bảng bên trái, ảnh sẽ hiển thị tại đây.",
    )
    image = ft.Image(src="", fit=ft.BoxFit.CONTAIN, visible=False, expand=True,
                     border_radius=T.RADIUS_INNER)
    stage = ft.Container(
        content=ft.Stack(
            [
                ft.Container(empty, alignment=ft.Alignment.CENTER, expand=True),
                ft.Container(image, alignment=ft.Alignment.CENTER, expand=True),
            ],
            expand=True,
        ),
        height=420,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        border_radius=T.RADIUS_INNER,
        padding=8,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )
    empty_holder = stage.content.controls[0]

    stat_count = T.StatTile(ft.Icons.DATA_OBJECT, "Đối tượng")
    stat_size = T.StatTile(ft.Icons.PHOTO_SIZE_SELECT_LARGE, "Image size")
    stat_time = T.StatTile(ft.Icons.TIMER_OUTLINED, "Thời gian")
    stats = ft.ResponsiveRow([stat_count.control, stat_size.control, stat_time.control], spacing=10)

    det_list = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, height=240)
    det_empty = ft.Container(
        T.muted("Kết quả phát hiện sẽ hiện ở đây sau khi bấm “Phân tích ảnh”.", 13),
        padding=ft.Padding.symmetric(vertical=24), alignment=ft.Alignment.CENTER,
    )
    det_list.controls = [det_empty]

    # ---- helper UI ---------------------------------------------------------- #
    def show_image(b64: str | None) -> None:
        if b64:
            image.src = b64
            image.visible = True
            empty_holder.visible = False
        else:
            image.visible = False
            empty_holder.visible = True

    def missing_text() -> str:
        """Gợi ý còn thiếu gì; rỗng nếu đã đủ."""
        missing = []
        if not state["weights"]:
            missing.append("file .pt")
        if not state["image"]:
            missing.append("ảnh")
        return " Còn thiếu: " + " và ".join(missing) + "." if missing else " Bấm “Phân tích ảnh” để chạy."

    def refresh_ready() -> None:
        """Chỉ bật/tắt nút Detect. Không đụng tới dòng trạng thái (để không che thông báo lỗi)."""
        btn_detect.disabled = not (state["image"] and state["weights"]) or state["busy"]
        page.update()

    # ---- sự kiện ------------------------------------------------------------ #
    def on_imgsz_change(e):
        v = e.control.selected[0]
        imgsz_hint.value = (
            "Nhanh hơn, phù hợp vật thể lớn." if v == "640"
            else "Chi tiết hơn cho vật thể nhỏ, nhưng chậm và tốn RAM hơn."
        )
        page.update()

    imgsz_seg.on_change = on_imgsz_change

    def on_conf_change(e):
        conf_value.value = f"{e.control.value:.2f}"
        page.update()

    conf_slider.on_change = on_conf_change

    def on_view_change(e):
        show_image(state["result_b64"] if e.control.selected[0] == "result" else state["orig_b64"])
        page.update()

    view_seg.on_change = on_view_change

    def toggle_theme(e):
        page.theme_mode = T.next_theme_mode(page.theme_mode)
        theme_btn.icon = T.THEME_ICON[page.theme_mode]
        theme_btn.tooltip = f"Giao diện: {T.THEME_LABEL[page.theme_mode]}"
        page.update()

    # ---- upload (chỉ dùng khi chạy web) -------------------------------------- #
    def on_upload(e: ft.FilePickerUploadEvent):
        if e.error:
            upload_error[e.file_name] = str(e.error)
            upload_done[e.file_name].set()
        elif e.progress is not None and e.progress >= 1.0:
            upload_done[e.file_name].set()
        else:
            status.set("loading", f"Đang upload {e.file_name}: {(e.progress or 0):.0%}")
            page.update()

    picker = ft.FilePicker(on_upload=on_upload)
    page.services.append(picker)

    async def resolve_local_path(f: ft.FilePickerFile) -> str:
        """Desktop: dùng thẳng f.path. Web: upload lên server rồi trả về đường dẫn trên server."""
        if not page.web and f.path:
            return f.path

        done = asyncio.Event()
        upload_done[f.name] = done
        upload_error.pop(f.name, None)

        await picker.upload(
            files=[
                ft.FilePickerUploadFile(
                    name=f.name,
                    upload_url=page.get_upload_url(f.name, 600),
                )
            ]
        )
        await asyncio.wait_for(done.wait(), timeout=600)
        if f.name in upload_error:
            raise RuntimeError(f"Upload {f.name} lỗi: {upload_error[f.name]}")
        return str(UPLOAD_DIR / f.name)

    async def pick_image(e):
        files = await picker.pick_files(
            dialog_title="Chọn ảnh",
            file_type=ft.FilePickerFileType.IMAGE,
            cancel_upload_on_window_blur=False,
        )
        if not files:
            return
        try:
            tile_image.set_loading(True, "Đang xử lý ảnh...")
            page.update()
            path = await resolve_local_path(files[0])
            state["image"] = path
            # preview bằng base64 để chạy được cả web lẫn desktop
            state["orig_b64"] = await asyncio.to_thread(file_to_b64, path)
            state["result_b64"] = None
            tile_image.set_file(files[0].name)
            show_image(state["orig_b64"])
            view_seg.visible = False
            det_list.controls = [det_empty]
            stat_count.set("—")
            stat_time.set("—")
            stat_size.set("—")
            status.set("success", f"Đã nhận ảnh {files[0].name}." + missing_text())
        except Exception as ex:  # noqa: BLE001
            state["image"] = None
            tile_image.subtitle.value = "Chưa chọn ảnh"
            status.set("error", str(ex))
            T.toast(page, f"Lỗi khi chọn ảnh: {ex}", "error")
        finally:
            tile_image.set_loading(False)
            refresh_ready()

    async def pick_weights(e):
        files = await picker.pick_files(
            dialog_title="Chọn file trọng số (.pt)",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pt"],
            cancel_upload_on_window_blur=False,
        )
        if not files:
            return
        try:
            tile_weights.set_loading(True, "Đang tải lên server (file lớn có thể mất vài phút)...")
            page.update()
            state["weights"] = await resolve_local_path(files[0])
            tile_weights.set_file(files[0].name)
            status.set("success", f"Đã nhận model {files[0].name}." + missing_text())
        except Exception as ex:  # noqa: BLE001
            state["weights"] = None
            tile_weights.subtitle.value = "Chưa chọn file trọng số"
            status.set("error", str(ex))
            T.toast(page, f"Lỗi khi chọn model: {ex}", "error")
        finally:
            tile_weights.set_loading(False)
            refresh_ready()

    async def detect(e):
        if not state["image"] or not state["weights"]:
            status.set("warning", "Hãy chọn đủ ảnh và file .pt.")
            page.update()
            return

        imgsz = int(imgsz_seg.selected[0])
        state["busy"] = True
        btn_detect.disabled = True
        busy_bar.visible = True
        status.set("loading", "Đang nạp model và phát hiện đối tượng...")
        page.update()

        try:
            b64, dets, secs = await asyncio.to_thread(
                run_detection, state["image"], state["weights"], imgsz, float(conf_slider.value),
            )
            state["result_b64"] = b64
            show_image(b64)
            view_seg.selected = ["result"]
            view_seg.visible = True

            stat_count.set(str(len(dets)))
            stat_size.set(f"{imgsz}")
            stat_time.set(f"{secs:.2f}s")
            det_list.controls = (
                [T.detection_row(n, c) for n, c in dets]
                if dets else [ft.Container(T.muted("Không phát hiện đối tượng nào. Thử hạ ngưỡng confidence.", 13),
                                           padding=ft.Padding.symmetric(vertical=24),
                                           alignment=ft.Alignment.CENTER)]
            )
            status.set("success", f"Hoàn tất: {len(dets)} đối tượng trong {secs:.2f}s (imgsz={imgsz}).")
        except Exception as ex:  # noqa: BLE001
            status.set("error", f"Lỗi: {ex}")
            T.toast(page, "Phát hiện thất bại, xem chi tiết ở bảng trạng thái.", "error")
        finally:
            state["busy"] = False
            busy_bar.visible = False
            refresh_ready()

    btn_detect.on_click = detect
    tile_weights.button.on_click = pick_weights
    tile_image.button.on_click = pick_image

    # ---- bố cục ------------------------------------------------------------- #
    theme_btn = ft.IconButton(
        icon=T.THEME_ICON[page.theme_mode],
        tooltip=f"Giao diện: {T.THEME_LABEL[page.theme_mode]}",
        on_click=toggle_theme,
    )
    page.appbar = ft.AppBar(
        leading=ft.Container(T.app_logo(), alignment=ft.Alignment.CENTER_LEFT,
                             padding=ft.Padding.only(left=16)),
        leading_width=60,
        title=ft.Column(
            [
                ft.Text("YOLO Detector", size=18, weight=ft.FontWeight.W_700),
                T.muted("Nhận diện đối tượng bằng model .pt", 11),
            ],
            spacing=0, tight=True,
        ),
        center_title=False,
        bgcolor=ft.Colors.SURFACE,
        actions=[theme_btn, ft.Container(width=8)],
    )

    left = ft.Column(
        [
            T.card("1 · Dữ liệu đầu vào", ft.Icons.UPLOAD_FILE, tile_weights.control, tile_image.control),
            T.card(
                "2 · Thiết lập", ft.Icons.TUNE,
                ft.Column([ft.Text("Image size", size=13, weight=ft.FontWeight.W_600),
                           ft.Row([imgsz_seg]), imgsz_hint], spacing=8),
                ft.Column([ft.Row([ft.Text("Confidence tối thiểu", size=13, weight=ft.FontWeight.W_600),
                                   ft.Container(expand=True), conf_value]),
                           ft.Row([conf_slider]),
                           T.muted("Chỉ giữ đối tượng có độ tin cậy ≥ giá trị này.")], spacing=4),
            ),
            T.card(
                "3 · Chạy", ft.Icons.PLAY_CIRCLE_OUTLINE,
                ft.Row([btn_detect]), busy_bar, status.control,
            ),
        ],
        spacing=T.GAP,
    )

    right = ft.Column(
        [
            T.card("Hình ảnh", ft.Icons.PHOTO_OUTLINED, stage, trailing=view_seg),
            T.card("Kết quả phát hiện", ft.Icons.INSIGHTS, stats, det_list),
        ],
        spacing=T.GAP,
    )

    page.add(
        ft.Container(
            ft.ResponsiveRow(
                [
                    ft.Container(left, col={"xs": 12, "lg": 5}),
                    ft.Container(right, col={"xs": 12, "lg": 7}),
                ],
                spacing=T.GAP, run_spacing=T.GAP,
            ),
            padding=ft.Padding.all(T.GAP + 4),
        )
    )
    status.set("info", "Chọn file model và ảnh để bắt đầu.")
    refresh_ready()


ft.run(main, upload_dir=str(UPLOAD_DIR))