# main.py — 学期タブ + 時間割グリッド + 画像OCR取り込み
import os, sys, sqlite3, re
from dataclasses import dataclass
from typing import List, Optional


os.environ.setdefault("KIVY_NO_ARGS", "1")
if sys.platform.startswith("win"):
    os.environ.setdefault("KIVY_GL_BACKEND", "angle_sdl2")
else:
    os.environ.setdefault("KIVY_GL_BACKEND", "gl")

from kivy.config import Config
Config.set("graphics", "multisamples", "0")

from kivy.app import App
from kivy.lang import Builder
from kivy.properties import ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.metrics import dp
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.factory import Factory
from kivy.uix.filechooser import FileChooserIconView

# ---------- ----------
def register_cjk_font() -> str:
    here = os.path.dirname(__file__)
    for p in [
        os.path.join(here, "NotoSansJP-Regular.ttf"),
        os.path.join(here, "NotoSansCJKsc-Regular.otf"),
        r"C:\Windows\Fonts\meiryo.ttc",
        r"C:\Windows\Fonts\YuGothM.ttc",
        r"C:\Windows\Fonts\MSMINCHO.TTC",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    ]:
        if os.path.exists(p):
            try:
                LabelBase.register(name="CJK", fn_regular=p)
                return "CJK"
            except Exception:
                pass
    return ""
FONT_NAME = register_cjk_font()

# ---------- OCR 依赖 ----------
OCR_AVAILABLE = True
TESSERACT_CMD = r""  
try:
    from PIL import Image, ImageOps, ImageFilter
    import pytesseract
    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
except Exception:
    OCR_AVAILABLE = False

# ---------- 常量 ----------
TERMS = ['春ターム', '夏ターム', '秋ターム', '冬ターム']
WEEK_SHORT = ['月','火','水','木','金','土']     
WEEK_FULL  = ['月曜日','火曜日','水曜日','木曜日','金曜日','土曜日']
MAX_PERIOD = 7                                   # 1〜7 限

# ---------- KV ----------
KV = f"""
#:kivy 2.3.0

<Label>:
    font_name: '{FONT_NAME if FONT_NAME else ""}'
<Button>:
    font_name: '{FONT_NAME if FONT_NAME else ""}'
<TextInput>:
    font_name: '{FONT_NAME if FONT_NAME else ""}'
<Spinner>:
    font_name: '{FONT_NAME if FONT_NAME else ""}'

<LinkLabel@ButtonBehavior+Label>:
    color: 0.35, 0.1, 0.75, 1
    markup: True
    text: "[u]未登録[/u]"
    halign: 'center'
    valign: 'middle'
    text_size: self.size

<Cell@BoxLayout>:
    orientation: 'vertical'
    padding: dp(6)
    spacing: dp(4)
    canvas.before:
        Color:
            rgba: 0.95, 0.95, 0.95, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.88, 0.88, 0.88, 1
        Line:
            rectangle: (*self.pos, *self.size)

<CourseCard@ButtonBehavior+BoxLayout>:
    course_id: 0
    title: ""
    subtitle: ""
    orientation: 'vertical'
    size_hint_y: None
    height: dp(64)
    padding: (6, 6)
    spacing: 4
    on_release: app.root.open_edit_dialog(self.course_id)
    canvas.before:
        Color:
            rgba: 1.0, 0.92, 0.78, 1
        Rectangle:
            pos: self.pos
            size: self.size
        Color:
            rgba: 0.95, 0.6, 0.2, 1
        Line:
            rectangle: (*self.pos, *self.size)
    Label:
        text: "[b]"+root.title+"[/b]"
        markup: True
        color: 0, 0, 0, 1
        halign: 'left'
        valign: 'middle'
        text_size: self.size
    Label:
        text: root.subtitle
        color: 0, 0, 0, 1
        halign: 'left'
        valign: 'top'
        text_size: self.size

<Root>:
    orientation: 'vertical'
    padding: dp(12)
    spacing: dp(10)


    BoxLayout:
        size_hint_y: None
        height: dp(44)
        spacing: dp(6)
        ToggleButton:
            id: tab_spring
            text: '{TERMS[0]}'
            group: 'term'
            state: 'down'
            on_state: root.on_term_changed(self, '{TERMS[0]}')
        ToggleButton:
            id: tab_summer
            text: '{TERMS[1]}'
            group: 'term'
            on_state: root.on_term_changed(self, '{TERMS[1]}')
        ToggleButton:
            id: tab_autumn
            text: '{TERMS[2]}'
            group: 'term'
            on_state: root.on_term_changed(self, '{TERMS[2]}')
        ToggleButton:
            id: tab_winter
            text: '{TERMS[3]}'
            group: 'term'
            on_state: root.on_term_changed(self, '{TERMS[3]}')
        Widget:
        Button:
            text: '画像から読み取り'
            size_hint_x: None
            width: dp(160)
            on_release: root.open_image_import()

    # 
    GridLayout:
        cols: 7
        size_hint_y: None
        height: dp(34)
        Label:
            text: ''
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
        Label:
            text: '{WEEK_FULL[0]}'
            color: 1, 1, 1, 1
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
        Label:
            text: '{WEEK_FULL[1]}'
            color: 1, 1, 1, 1
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
        Label:
            text: '{WEEK_FULL[2]}'
            color: 1, 1, 1, 1
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
        Label:
            text: '{WEEK_FULL[3]}'
            color: 1, 1, 1, 1
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
        Label:
            text: '{WEEK_FULL[4]}'
            color: 1, 1, 1, 1
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size
        Label:
            text: '{WEEK_FULL[5]}'
            color: 1, 1, 1, 1
            canvas.before:
                Color:
                    rgba: 1, 0.6, 0.3, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

    # （1 列“限” + 6 列曜日）
    GridLayout:
        id: grid
        cols: 7
        rows: 7
        spacing: dp(2)
        row_default_height: dp(86)   # 固定行高（你可按需要调大/小）
        row_force_default: True
"""

# ---------- DB ----------
@dataclass
class Course:
    id: int
    term: str
    name: str
    teacher: Optional[str]
    location: Optional[str]
    weekday: int   # 1..6
    period: int    # 1..7

class DB:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS timetable(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT,
                name TEXT NOT NULL,
                teacher TEXT,
                location TEXT,
                weekday INTEGER NOT NULL,
                period_start INTEGER NOT NULL,
                period_end INTEGER NOT NULL
            );
        """)
        self.conn.commit()
        self._ensure_schema()

    def _ensure_schema(self):
        cur = self.conn.execute("PRAGMA table_info(timetable)")
        cols = {r[1] for r in cur.fetchall()}
        if "term" not in cols:
            self.conn.execute("ALTER TABLE timetable ADD COLUMN term TEXT")
            self.conn.execute("UPDATE timetable SET term='春ターム' WHERE term IS NULL")
            self.conn.commit()
      
        cur = self.conn.execute("PRAGMA table_info(timetable)")
        cols = {r[1] for r in cur.fetchall()}
        if "period_start" not in cols:
            self.conn.execute("ALTER TABLE timetable ADD COLUMN period_start INTEGER")
            self.conn.execute("UPDATE timetable SET period_start=1 WHERE period_start IS NULL")
        if "period_end" not in cols:
            self.conn.execute("ALTER TABLE timetable ADD COLUMN period_end INTEGER")
            self.conn.execute("UPDATE timetable SET period_end=period_start WHERE period_end IS NULL")
        self.conn.commit()

    def list_by_term(self, term: str) -> List[Course]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, term, name, teacher, location, weekday, period_start
            FROM timetable
            WHERE term=? ORDER BY weekday ASC, period_start ASC;
        """, (term,))
        return [Course(r[0], r[1], r[2], r[3], r[4], r[5], r[6]) for r in cur.fetchall()]

    def add(self, term, name, teacher, location, weekday, period):
        self.conn.execute("""
            INSERT INTO timetable(term, name, teacher, location, weekday, period_start, period_end)
            VALUES (?,?,?,?,?,?,?);
        """, (term, name, teacher, location, weekday, period, period))
        self.conn.commit()

    def update(self, cid, name, teacher, location):
        self.conn.execute("UPDATE timetable SET name=?, teacher=?, location=? WHERE id=?;",
                          (name, teacher, location, cid))
        self.conn.commit()

    def delete_by_id(self, cid):
        self.conn.execute("DELETE FROM timetable WHERE id=?;", (cid,))
        self.conn.commit()

    def get_one(self, cid) -> Optional[Course]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT id, term, name, teacher, location, weekday, period_start
            FROM timetable WHERE id=?;
        """, (cid,))
        r = cur.fetchone()
        if not r: return None
        return Course(r[0], r[1], r[2], r[3], r[4], r[5], r[6])

# ---------- OCR 解析 ----------
# 支持：1-2限、1～2限、１〜２限、3限 
_period_pat = re.compile(r"(?:([0-9０-９]{1,2})\s*[-~〜～–]\s*([0-9０-９]{1,2})|\b([0-9０-９]{1,2}))\s*限?")
def _to_int(s: str) -> int:
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    return int(s.translate(trans))

def preprocess_image(path: str):
    img = Image.open(path)
    img = ImageOps.exif_transpose(img).convert("L")
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    return img

def ocr_image_to_text(image_path: str) -> str:
    if not OCR_AVAILABLE:
        raise RuntimeError("OCR ライブラリ（pytesseract/Pillow/Tesseract本体）が利用不可です。")
    img = preprocess_image(image_path)
    return pytesseract.image_to_string(img, lang="jpn+eng", config="--psm 6")

def parse_timetable_text(text: str) -> List[dict]:

    cur_wd = None
    rows = []
    lines = [re.sub(r"[ \t]+", " ", ln.strip()) for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        for i, ch in enumerate(WEEK_SHORT, start=1):
            if ch in ln or WEEK_FULL[i-1] in ln:
                cur_wd = i; break
        if cur_wd is None:
            if   "Mon" in ln: cur_wd = 1
            elif "Tue" in ln: cur_wd = 2
            elif "Wed" in ln: cur_wd = 3
            elif "Thu" in ln: cur_wd = 4
            elif "Fri" in ln: cur_wd = 5
            elif "Sat" in ln: cur_wd = 6

        m = _period_pat.search(ln)
        if not m or cur_wd is None:
            continue

        if m.group(1) and m.group(2):
            s, e = _to_int(m.group(1)), _to_int(m.group(2))
        else:
            s = e = _to_int(m.group(3))

        name = ln
        for ch in WEEK_SHORT: name = name.replace(ch, " ")
        for ch in WEEK_FULL:  name = name.replace(ch, " ")
        name = re.sub(r"(曜|曜日|限|時限)", " ", name)
        name = _period_pat.sub(" ", name)
        name = re.sub(r"[()\[\]【】〔〕<>〈〉『』「」@＠：:・,，/／\-–~〜～]+", " ", name)
        name = re.sub(r"\s+", " ", name).strip() or "科目"

        teacher = None; location = None

        for p in range(max(1, s), min(MAX_PERIOD, e)+1):
            rows.append({"weekday": cur_wd, "period": p, "name": name, "teacher": teacher, "location": location})
    return rows

# ---------- Root ----------
class Root(BoxLayout):
    term = StringProperty(TERMS[0])
    grid_ref: GridLayout = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        user_dir = App.get_running_app().user_data_dir
        self.db = DB(os.path.join(user_dir, "comalink.db"))
        Clock.schedule_once(lambda *_: self._build_grid_and_refresh())

    # 学期
    def on_term_changed(self, btn, term_name: str):
        if btn.state == 'down':
            self.term = term_name
            self._refresh_grid()

    def _build_grid_and_refresh(self):
        grid: GridLayout = self.ids.grid
        self.grid_ref = grid
        grid.clear_widgets()

        from kivy.graphics import Color, Rectangle

        for p in range(1, MAX_PERIOD+1):
            side = Label(text=f"[b]{p}限[/b]", markup=True, color=(1,1,1,1))
            with side.canvas.before:
                Color(1, 0.6, 0.3, 1)
                rect = Rectangle(pos=side.pos, size=side.size)
            def _bind_rect(_w, _v, r=rect, s=side):
                r.pos = s.pos; r.size = s.size
            side.bind(pos=_bind_rect, size=_bind_rect)
            grid.add_widget(side)

            # 6 列 cell
            for wd in range(1, 7):
                cell = Factory.Cell()
                cell.id = f"cell_{wd}_{p}"
                grid.add_widget(cell)

        self._refresh_grid()

    def _cell(self, wd: int, period: int):
        target_id = f"cell_{wd}_{period}"
        for ch in self.ids.grid.children:
            if isinstance(ch, BoxLayout) and getattr(ch, "id", "") == target_id:
                return ch
        return None

    def _refresh_grid(self):
        for p in range(1, MAX_PERIOD+1):
            for wd in range(1, 7):
                cell = self._cell(wd, p)
                if not cell: continue
                cell.clear_widgets()
                link = Factory.LinkLabel()
                link.bind(on_release=lambda *_a, wd=wd, p=p: self.open_create_dialog(wd, p))
                cell.add_widget(link)

        # add
        for c in self.db.list_by_term(self.term):
            cell = self._cell(c.weekday, c.period)
            if not cell: continue
            cell.clear_widgets()
            card = Factory.CourseCard()
            card.course_id = c.id
            card.title = c.name
            details = []
            if c.teacher:  details.append(c.teacher)
            if c.location: details.append(c.location)
            card.subtitle = " / ".join(details)
            cell.add_widget(card)

    # —— edit —— #
    def open_create_dialog(self, wd: int, period: int):
        self._open_form_dialog(mode="create", weekday=wd, period=period)

    def open_edit_dialog(self, cid: int):
        row = self.db.get_one(cid)
        if not row: return
        self._open_form_dialog(mode="edit", course=row)

    def _open_form_dialog(self, mode: str, weekday=None, period=None, course: Optional[Course]=None):
        is_edit = (mode == "edit")
        if is_edit and course is None:
            return

        wd_val = weekday if weekday else (course.weekday if course else 1)
        pd_val = period  if period  else (course.period  if course  else 1)
        name_val = course.name if is_edit else ""
        teacher_val = course.teacher if (is_edit and course.teacher) else ""
        location_val = course.location if (is_edit and course.location) else ""

        root_box = BoxLayout(orientation="vertical", padding=10, spacing=8)

        line1 = BoxLayout(size_hint_y=None, height=dp(40), spacing=8)
        sp_wd = Spinner(text=WEEK_FULL[wd_val-1], values=WEEK_FULL, size_hint_x=None, width=dp(150))
        sp_pd = Spinner(text=str(pd_val), values=[str(i) for i in range(1, MAX_PERIOD+1)], size_hint_x=None, width=dp(100))
        line1.add_widget(Label(text="曜日：", size_hint_x=None, width=dp(60)))
        line1.add_widget(sp_wd)
        line1.add_widget(Label(text="時限：", size_hint_x=None, width=dp(60)))
        line1.add_widget(sp_pd)

        ti_name = TextInput(text=name_val, hint_text="科目名*", multiline=False)
        ti_teacher = TextInput(text=teacher_val, hint_text="担当教員（任意）", multiline=False)
        ti_location = TextInput(text=location_val, hint_text="教室（任意）", multiline=False)

        root_box.add_widget(line1)
        root_box.add_widget(ti_name)
        root_box.add_widget(ti_teacher)
        root_box.add_widget(ti_location)

        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=8)
        p = Popup(title=("編集" if is_edit else "登録"), content=root_box, size_hint=(0.6, 0.6))
        btns.add_widget(Button(text="キャンセル", on_release=lambda *_: p.dismiss()))
        if is_edit:
            def _save_edit_action(*_):
                name = ti_name.text.strip()
                if not name:
                    self._toast("科目名は必須です。"); return
                self.db.update(course.id, name, ti_teacher.text.strip() or None, ti_location.text.strip() or None)
                p.dismiss(); self._refresh_grid()
            btns.add_widget(Button(text="削除", on_release=lambda *_: (self.db.delete_by_id(course.id), self._refresh_grid(), p.dismiss())))
            btns.add_widget(Button(text="保存", on_release=_save_edit_action))
        else:
            btns.add_widget(Button(text="登録", on_release=lambda *_: self._save_new(sp_wd.text, sp_pd.text, ti_name.text, ti_teacher.text, ti_location.text, p)))
        root_box.add_widget(btns)
        p.open()

    def _save_new(self, wd_txt, pd_txt, name, teacher, location, popup: Popup):
        name = name.strip()
        if not name:
            self._toast("科目名は必須です。"); return
        wd = WEEK_FULL.index(wd_txt) + 1   # 1..6
        pd = int(pd_txt)
        self.db.add(self.term, name, teacher.strip() or None, location.strip() or None, wd, pd)
        popup.dismiss()
        self._refresh_grid()

    # ---------- OCR 入口 ----------
    def open_image_import(self):
        if not OCR_AVAILABLE:
            self._toast("OCR機能を使うには Pillow / pytesseract と Tesseract 本体が必要です。"); return
        chooser = FileChooserIconView(filters=["*.png","*.jpg","*.jpeg","*.bmp","*.tif","*.tiff"])
        box = BoxLayout(orientation="vertical", padding=10, spacing=10)
        btns = BoxLayout(size_hint_y=None, height=dp(44), spacing=10)
        p = Popup(title="画像を選択", content=box, size_hint=(0.9, 0.9))
        btns.add_widget(Button(text="キャンセル", on_release=lambda *_: p.dismiss()))
        btns.add_widget(Button(text="読み取る", on_release=lambda *_: self._do_import_from_image(chooser.selection, p)))
        box.add_widget(chooser); box.add_widget(btns); p.open()

    def _do_import_from_image(self, selection, popup: Popup):
        if not selection:
            self._toast("画像が選択されていません。"); return
        path = selection[0]
        try:
            text = ocr_image_to_text(path)
            rows = parse_timetable_text(text)
            if not rows:
                self._toast("抽出できる時間割が見つかりませんでした。"); return
            added = 0
            for r in rows:
                if 1 <= r["weekday"] <= 6 and 1 <= r["period"] <= MAX_PERIOD:
                    self.db.add(self.term, r["name"], r["teacher"], r["location"], r["weekday"], r["period"])
                    added += 1
            popup.dismiss()
            self._toast(f"読み取り完了：{added}件を追加しました。")
            self._refresh_grid()
        except Exception as e:
            self._toast(f"OCRエラー：{e}")
            try: popup.dismiss()
            except: pass

    @staticmethod
    def _toast(msg: str, title="お知らせ"):
        Popup(title=title, content=Label(text=msg), size_hint=(0.45, 0.28)).open()

class AppKivy(App):
    def build(self):
        Builder.load_string(KV)   
        return Root()             
# --- Tesseract bootstrap (Windows) ---
import os, shutil
import pytesseract

def ensure_tesseract():
    p = os.getenv("TESSERACT_PATH")
    if p and os.path.exists(p):
        pass
    else:
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\UB-Mannheim.TesseractOCR*\Tesseract-OCR\tesseract.exe"),
        ]
        p = next((c for c in candidates if os.path.exists(c)), None) or shutil.which("tesseract")

    if not p:
        raise RuntimeError(
            "tesseract.exe not found. Install UB-Mannheim Tesseract or set TESSERACT_PATH."
        )

    pytesseract.pytesseract.tesseract_cmd = p

    tessdata = os.path.join(os.path.dirname(p), "tessdata")
    if os.path.isdir(tessdata):
        os.environ["TESSDATA_PREFIX"] = tessdata

    return p

TESS_PATH = ensure_tesseract()
print("Using Tesseract at:", TESS_PATH)
# --- end bootstrap ---

if __name__ == "__main__":
    AppKivy().run()
