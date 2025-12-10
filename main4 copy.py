# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import List, Set, Dict, Tuple
import random
import json
import os

from kivy.core.window import Window
from kivy.graphics import Color, Line, Rectangle
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.metrics import dp
from kivy.uix.behaviors import ToggleButtonBehavior
from kivy.core.text import LabelBase
from kivy.resources import resource_add_path

resource_add_path(r"C:\Windows\Fonts")
LabelBase.register(name="JP", fn_regular="meiryo.ttc")
LabelBase.register(name="EMOJI", fn_regular="seguiemj.ttf") 

Window.clearcolor = (1, 1, 1, 1)



class JpLabel(Label):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", "JP")
        kwargs.setdefault("color", (0, 0, 0, 1))  
        super().__init__(**kwargs)


class JpButton(Button):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", "JP")
        kwargs.setdefault("color", (0, 0, 0, 1))  
        super().__init__(**kwargs)


class JpToggleButton(ToggleButton):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", "JP")
        kwargs.setdefault("color", (0, 0, 0, 1))  
        super().__init__(**kwargs)


class JpTextInput(TextInput):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", "JP")
        kwargs.setdefault("foreground_color", (0, 0, 0, 1))  
        kwargs.setdefault("background_color", (1, 1, 1, 1))  
        super().__init__(**kwargs)

class EmojiLabel(Label):
    def __init__(self, **kwargs):
        kwargs.setdefault("font_name", "EMOJI")
        kwargs.setdefault("font_size", dp(20))
        super().__init__(**kwargs)


class CategoryToggleButton(ToggleButtonBehavior, BoxLayout):
    """
    カテゴリ用のトグルボタン：
    - 上：emoji（EmojiLabel）
    - 下：日文ラベル（JpLabel）
    - 白底 + 緑枠，選択時は淡い緑で塗る
    """

    def __init__(self, icon_text: str, label_text: str, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(2))
        kwargs.setdefault("spacing", dp(2))
        super().__init__(**kwargs)

        if "size_hint_x" not in kwargs:
            self.size_hint_x = None
        if "width" not in kwargs:
            self.width = dp(70)


        self.icon = EmojiLabel(text=icon_text)
        self.caption = JpLabel(text=label_text, font_size=dp(12))
        self.add_widget(self.icon)
        self.add_widget(self.caption)


        with self.canvas.before:
            self.bg_color = Color(1, 1, 1, 1)  
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            Color(0.1, 0.6, 0.1, 1)           # 绿
            self.border_line = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1
            )

        self.bind(pos=self._update_rect, size=self._update_rect, state=self._on_state_change)
        self._on_state_change(self, self.state)

    def _update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rectangle = (self.x, self.y, self.width, self.height)

    def _on_state_change(self, instance, value):
        # ToggleButtonBehavior: state == "down" / "normal"
        if value == "down":
            self.bg_color.rgba = (0.9, 1.0, 0.9, 1)  # 绿
        else:
            self.bg_color.rgba = (1.0, 1.0, 1.0, 1)  # 白



DAYS: List[Tuple[str, str]] = [
    ("MON", "月"),
    ("TUE", "火"),
    ("WED", "水"),
    ("THU", "木"),
    ("FRI", "金"),
]

SLOTS: List[Tuple[str, str]] = [
    ("1", "1限"),
    ("2", "2限"),
    ("3", "3限"),
    ("4", "4限"),
    ("5", "5限"),
    ("LUNCH", "昼休み"),
]
SLOT_IDS = [s[0] for s in SLOTS]


@dataclass
class EventCategory:
    id: str
    icon: str
    label: str


CATEGORIES: List[EventCategory] = [
    EventCategory("meal", "🍚", "食事"),
    EventCategory("study", "📚", "勉強"),
    EventCategory("work", "💻", "作業"),
    EventCategory("play", "🎮", "遊び"),
    EventCategory("chat", "🗣", "雑談"),
]


def get_category_by_id(cat_id: str) -> EventCategory:
    for c in CATEGORIES:
        if c.id == cat_id:
            return c
    return CATEGORIES[0]


@dataclass
class Event:
    id: str
    title: str
    category_id: str
    day_id: str
    slot_start_id: str
    slot_end_id: str
    owner_user_id: str
    participants_count: int
    max_participants: int


@dataclass
class TimeSlotSummary:
    day_id: str
    slot_id: str
    events_count: int
    categories: Set[str]


DATA_FILE = "coma_data.json"  
class ComaLinkRepository:
    def __init__(self, current_user_id: str = "user_me"):
        self.user_name: str = "ゲスト"          # 默认名字
        self.current_user_id: str = current_user_id
        # 募集 / 授業 / 报名名单
        self.events: List[Event] = []
        self.my_busy_slots: Set[Tuple[str, str]] = set()
        self.event_participants: Dict[str, Set[str]] = {}  # ✅ 每个 event 的参加者ID集合
        self.current_user_id = current_user_id
        self.events: List[Event] = []
        self.my_busy_slots: Set[Tuple[str, str]] = set()

        # 如果你有 load()
        self.load()

        # 如果需要默认数据
        if not self.events and not self.my_busy_slots:
            self._init_default_data()
            self.save()

    # ----------------- 默认初始数据 -----------------
    def _init_default_data(self):
        self.events = [
            Event(
                id="1",
                title="水曜ランチ会",
                category_id="meal",
                day_id="WED",
                slot_start_id="LUNCH",
                slot_end_id="LUNCH",
                owner_user_id="user_a",
                participants_count=3,
                max_participants=5,
            ),
            Event(
                id="2",
                title="金曜3-4限自習会",
                category_id="study",
                day_id="FRI",
                slot_start_id="3",
                slot_end_id="4",
                owner_user_id="user_b",
                participants_count=2,
                max_participants=6,
            ),
        ]

        # 当前用户的上课コマ（非空きコマ）
        self.my_busy_slots = {
            ("MON", "1"),
            ("MON", "2"),
            ("TUE", "3"),
            ("WED", "4"),
            ("FRI", "1"),
        }

    # ----------------- 永続化（JSON） -----------------
    def load(self):
        """从 JSON 文件加载 events / my_busy_slots"""
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # 读坏了就算了，用默认初始化
            return

        ev_list = data.get("events", [])
        self.events = [
            Event(
                id=str(ev.get("id", "")),
                title=ev.get("title", ""),
                category_id=ev.get("category_id", "meal"),
                day_id=ev.get("day_id", "MON"),
                slot_start_id=ev.get("slot_start_id", "1"),
                slot_end_id=ev.get("slot_end_id", "1"),
                owner_user_id=ev.get("owner_user_id", "user_me"),
                participants_count=int(ev.get("participants_count", 1)),
                max_participants=int(ev.get("max_participants", 4)),
            )
            for ev in ev_list
        ]

        slots = data.get("my_busy_slots", [])
        # 存的时候是 [["MON","1"], ...]，这里转回 set[tuple]
        self.my_busy_slots = {(d, s) for d, s in slots}
    def join_event(self, event_id: str) -> bool:
        """
        指定IDの募集に参加する（participants_count を +1）
        - すでに満席なら False を返す
        - 参加できたら True を返す
        """
        for e in self.events:
            if e.id == event_id:
                if e.participants_count >= e.max_participants:
                    return False
                e.participants_count += 1
                self.save()
                return True
        return False
   
    def save(self):
        """把当前数据写回 JSON 文件"""
        data = {
            "events": [e.__dict__ for e in self.events],
            "my_busy_slots": list(self.my_busy_slots),
        }
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存数据失败:", e)

    # ----------------- 业务逻辑 -----------------
    def slot_range_overlap(self, start_id: str, end_id: str, target_id: str) -> bool:
        try:
            start_idx = SLOT_IDS.index(start_id)
            end_idx = SLOT_IDS.index(end_id)
            target_idx = SLOT_IDS.index(target_id)
        except ValueError:
            return False
        return start_idx <= target_idx <= end_idx

    def get_time_table_summaries(self) -> List[TimeSlotSummary]:
        summaries: List[TimeSlotSummary] = []
        for day_id, _ in DAYS:
            for slot_id, _ in SLOTS:
                evs = [
                    e for e in self.events
                    if e.day_id == day_id
                    and self.slot_range_overlap(e.slot_start_id, e.slot_end_id, slot_id)
                ]
                cat_ids = {e.category_id for e in evs}
                summaries.append(
                    TimeSlotSummary(
                        day_id=day_id,
                        slot_id=slot_id,
                        events_count=len(evs),
                        categories=cat_ids,
                    )
                )
        return summaries

    def get_events_for_slot(self, day_id: str, slot_id: str) -> List[Event]:
        return [
            e for e in self.events
            if e.day_id == day_id
            and self.slot_range_overlap(e.slot_start_id, e.slot_end_id, slot_id)
        ]

    def is_my_slot_free(self, day_id: str, slot_id: str) -> bool:
        return (day_id, slot_id) not in self.my_busy_slots

    def _event_is_free_for_me(self, event: Event) -> bool:
        try:
            start_idx = SLOT_IDS.index(event.slot_start_id)
            end_idx = SLOT_IDS.index(event.slot_end_id)
        except ValueError:
            return False
        for i in range(start_idx, end_idx + 1):
            slot_id = SLOT_IDS[i]
            if (event.day_id, slot_id) in self.my_busy_slots:
                return False
        return True

    def search_events(
        self,
        category_ids: Set[str],
        day_ids: Set[str],
        slot_ids: Set[str],
        only_my_free_slots: bool,
    ) -> List[Event]:
        res: List[Event] = []
        for e in self.events:
            if category_ids and e.category_id not in category_ids:
                continue
            if day_ids and e.day_id not in day_ids:
                continue
            if slot_ids:
                ok = False
                for sid in slot_ids:
                    if self.slot_range_overlap(e.slot_start_id, e.slot_end_id, sid):
                        ok = True
                        break
                if not ok:
                    continue
            if only_my_free_slots and not self._event_is_free_for_me(e):
                continue
            res.append(e)
        return res

    def get_free_user_info(
        self, day_id: str, slot_start_id: str, slot_end_id: str
    ) -> int:
        base = 5
        variance = random.randint(0, 15)
        return base + variance

    # ---- 下面三个是“会修改数据”的方法：记得 save() ----
    def create_event(
        self,
        category_id: str,
        day_id: str,
        slot_start_id: str,
        slot_end_id: str,
        title: str,
        max_participants: int,
    ) -> Event:
        new_id = str(len(self.events) + 1)
        ev = Event(
            id=new_id,
            title=title,
            category_id=category_id,
            day_id=day_id,
            slot_start_id=slot_start_id,
            slot_end_id=slot_end_id,
            owner_user_id=self.current_user_id,
            participants_count=1,
            max_participants=max_participants,
        )
        self.events.append(ev)
        self.save()
        return ev

    def add_busy_slot(self, day_id: str, slot_id: str):
        """指定コマを『授業』として登録"""
        self.my_busy_slots.add((day_id, slot_id))
        self.save()

    def remove_busy_slot(self, day_id: str, slot_id: str):
        """指定コマの『授業』登録を解除"""
        self.my_busy_slots.discard((day_id, slot_id))
        self.save()


def heatmap_color(value: int, max_value: int):
    if max_value <= 0 or value <= 0:
        return [1.0, 1.0, 1.0, 1]

    ratio = min(1.0, float(value) / float(max_value))
    start_rgb = (232, 245, 233)
    end_rgb = (56, 142, 60)
    r = (start_rgb[0] + (end_rgb[0] - start_rgb[0]) * ratio) / 255.0
    g = (start_rgb[1] + (end_rgb[1] - start_rgb[1]) * ratio) / 255.0
    b = (start_rgb[2] + (end_rgb[2] - start_rgb[2]) * ratio) / 255.0
    return [r, g, b, 1]


# ---------- UI 组件 ----------

class TimeSlotButton(JpButton):

    def __init__(self, day_id: str, slot_id: str, **kwargs):
        kwargs.setdefault("font_size", dp(14))
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (1, 1, 1, 1))  
        kwargs.setdefault("color", (0, 0, 0, 1))             # 黑
        super().__init__(**kwargs)
        self.markup = True
        self.day_id = day_id
        self.slot_id = slot_id
        self.text_size = (0, 0)

        with self.canvas.before:
            Color(0.1, 0.6, 0.1, 1)  # 绿
            self.border_line = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1
            )

        self.bind(pos=self._update_border, size=self._update_border)

    def _update_border(self, *args):
        self.border_line.rectangle = (self.x, self.y, self.width, self.height)
        self.text_size = (self.width - dp(6), self.height - dp(6))


class GreenToggleButton(JpToggleButton):

    def __init__(self, **kwargs):
        kwargs.setdefault("background_normal", "")
        kwargs.setdefault("background_down", "")
        kwargs.setdefault("background_color", (1, 1, 1, 1))  # 白
        kwargs.setdefault("color", (0, 0, 0, 1))             # 黑
        super().__init__(**kwargs)

        with self.canvas.before:
            Color(0.1, 0.6, 0.1, 1)
            self.border_line = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1
            )

        self.bind(pos=self._update_border, size=self._update_border)
        self.bind(state=self._on_state_change)
        self._on_state_change(self, self.state)

    def _update_border(self, *args):
        self.border_line.rectangle = (self.x, self.y, self.width, self.height)

    def _on_state_change(self, instance, value):
        if value == 'down':
            self.background_color = (0.9, 1.0, 0.9, 1)  # 绿
        else:
            self.background_color = (1.0, 1.0, 1.0, 1)  # 白


class HeaderLabel(JpLabel):
    """表头：浅灰背景 + 绿框"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.halign = "center"
        self.valign = "middle"
        self.text_size = (0, 0)
        with self.canvas.before:
            Color(0.96, 0.96, 0.96, 1)       
            self.bg = Rectangle(pos=self.pos, size=self.size)
            Color(0.1, 0.6, 0.1, 1)          # 绿
            self.border_line = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1
            )
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size
        self.border_line.rectangle = (self.x, self.y, self.width, self.height)
        self.text_size = (self.width - dp(4), self.height - dp(4))


# ---------- 時間割画面 ----------

class TimetableScreen(Screen):
    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo
        self.selected_day_id = None
        self.selected_slot_id = None

        root = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(4))
        self.add_widget(root)

        scroll = ScrollView()
        root.add_widget(scroll)

        self.grid = GridLayout(
            cols=len(DAYS) + 1,
            size_hint_y=None,
            row_default_height=dp(60),
            row_force_default=True,
        )
        self.grid.bind(minimum_height=self.grid.setter('height'))
        scroll.add_widget(self.grid)

        self.build_grid()

    def build_grid(self):
        self.grid.clear_widgets()
        summaries = self.repo.get_time_table_summaries()
        summary_map: Dict[Tuple[str, str], TimeSlotSummary] = {}
        for s in summaries:
            summary_map[(s.day_id, s.slot_id)] = s
        max_count = max((s.events_count for s in summaries), default=0)

        self.grid.add_widget(HeaderLabel(text="", size_hint_x=None, width=dp(50)))
        for day_id, day_label in DAYS:
            self.grid.add_widget(HeaderLabel(text=day_label, bold=True))

        # 各コマ
        for slot_id, slot_label in SLOTS:
            self.grid.add_widget(HeaderLabel(text=slot_label, size_hint_x=None, width=dp(50)))

            for day_id, _ in DAYS:
                summary = summary_map.get((day_id, slot_id))
                count = summary.events_count if summary else 0
                cat_ids = summary.categories if summary else set()
                bg_color = heatmap_color(count, max_count)
                is_free = self.repo.is_my_slot_free(day_id, slot_id)

                raw_icons = "".join(
                    get_category_by_id(c).icon for c in list(cat_ids)[:3]
                )

                lines = []
                if raw_icons:
                    lines.append(f"[font=EMOJI]{raw_icons}[/font]")
                if count > 0:
                    lines.append(f"{count}件")
                if not is_free:
                    lines.append("授業")

                text = "\n".join(lines) if lines else ""


                btn = TimeSlotButton(
                    day_id=day_id,
                    slot_id=slot_id,
                    text=text,
                    background_color=bg_color,
                )
                btn.bind(on_press=self.on_slot_pressed)
                self.grid.add_widget(btn)

    def on_slot_pressed(self, btn: TimeSlotButton):
        self.selected_day_id = btn.day_id
        self.selected_slot_id = btn.slot_id
        self.show_slot_popup()
    def show_slot_popup(self):
        if not self.selected_day_id or not self.selected_slot_id:
            return

        day_label = next(l for i, l in DAYS if i == self.selected_day_id)
        slot_label = next(l for i, l in SLOTS if i == self.selected_slot_id)

        events = self.repo.get_events_for_slot(self.selected_day_id, self.selected_slot_id)
        is_busy = not self.repo.is_my_slot_free(self.selected_day_id, self.selected_slot_id)

        # ---- 内容区域：白底 + 竖排 ----
        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        with content.canvas.before:
            Color(1, 1, 1, 1)  # 纯白
            content.bg_rect = Rectangle(pos=content.pos, size=content.size)

        def _update_content_bg(instance, *args):
            content.bg_rect.pos = instance.pos
            content.bg_rect.size = instance.size

        content.bind(pos=_update_content_bg, size=_update_content_bg)

        # 标题
        title_lbl = JpLabel(text=f"{day_label} {slot_label}", size_hint_y=None, height=dp(30))
        content.add_widget(title_lbl)

        # ---- 募集リスト（每个募集 +「参加する」按钮）----
        if not events:
            content.add_widget(
                JpLabel(text="このコマにはまだ募集がありません。", size_hint_y=None, height=dp(40))
            )
        else:
            sv = ScrollView(size_hint=(1, 0.5))
            box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
            box.bind(minimum_height=box.setter('height'))
            sv.add_widget(box)

            for e in events:
                cat = get_category_by_id(e.category_id)

                row = BoxLayout(
                    orientation='horizontal',
                    size_hint_y=None,
                    height=dp(36),
                    spacing=dp(4),
                )

                lbl = JpLabel(
                    text=f"{cat.icon} {e.title}  参加: {e.participants_count}/{e.max_participants}",
                    halign="left",
                    valign="middle",
                )
                lbl.text_size = (0, None)

                btn_join = JpButton(
                    text="参加する",
                    size_hint_x=None,
                    width=dp(80),
                    font_size=dp(14),
                )

                # 每个募集一个 join 回调
                def on_join(_btn, ev=e):
                    ok = self.repo.join_event(ev.id)
                    if not ok:
                        # 简单提示一下满席
                        info = Popup(
                            title="参加できません",
                            content=JpLabel(
                                text="この募集はすでに満席です。",
                                size_hint_y=None,
                                height=dp(40),
                            ),
                            size_hint=(0.7, 0.3),
                        )
                        info.title_font = "JP"
                        info.title_color = (0, 0, 0, 1)
                        info.open()
                    else:
                        # 参加成功：刷新时间割 & 关闭当前弹窗
                        popup.dismiss()
                        self.build_grid()

                btn_join.bind(on_press=on_join)

                row.add_widget(lbl)
                row.add_widget(btn_join)
                box.add_widget(row)

            content.add_widget(sv)

        # ----- 授業の追加 / 解除 -----
        if is_busy:
            content.add_widget(
                JpLabel(
                    text="このコマは現在『授業』として登録されています。",
                    size_hint_y=None,
                    height=dp(24),
                )
            )
            btn_clear_class = JpButton(
                text="授業を削除（空きコマにする）",
                size_hint_y=None,
                height=dp(36),
            )
            content.add_widget(btn_clear_class)
        else:
            content.add_widget(
                JpLabel(
                    text="このコマを『授業』として登録できます。",
                    size_hint_y=None,
                    height=dp(24),
                )
            )
            btn_add_class = JpButton(
                text="このコマを授業として追加",
                size_hint_y=None,
                height=dp(36),
            )
            content.add_widget(btn_add_class)

        # 募集作成按钮
        btn_create = JpButton(
            text="このコマで募集を作成",
            size_hint_y=None,
            height=dp(40),
        )
        content.add_widget(btn_create)

        # 关闭按钮
        btn_close = JpButton(
            text="閉じる",
            size_hint_y=None,
            height=dp(40),
        )
        content.add_widget(btn_close)

        # ---- Popup 本体 ----
        popup = Popup(
            title="コマ詳細",
            content=content,
            size_hint=(0.9, 0.8),
        )

        popup.title_font = "JP"
        popup.title_color = (0, 0, 0, 1)
        popup.title_size = dp(18)
        popup.separator_color = (0.2, 0.6, 0.9, 1)
        popup.background = ""
        popup.background_color = (0.95, 0.95, 0.97, 1)

        # ---- 下面给按钮绑逻辑（需要 popup 变量）----
        def on_create_pressed(_btn):
            popup.dismiss()
            self.show_create_popup()

        btn_create.bind(on_press=on_create_pressed)
        btn_close.bind(on_press=lambda *_: popup.dismiss())

        if is_busy:
            def on_clear_class(_btn):
                self.repo.remove_busy_slot(self.selected_day_id, self.selected_slot_id)
                popup.dismiss()
                self.build_grid()
            btn_clear_class.bind(on_press=on_clear_class)
        else:
            def on_add_class(_btn):
                self.repo.add_busy_slot(self.selected_day_id, self.selected_slot_id)
                popup.dismiss()
                self.build_grid()
            btn_add_class.bind(on_press=on_add_class)

        popup.open()

    # def show_slot_popup(self):
    #     if not self.selected_day_id or not self.selected_slot_id:
    #         return

    #     day_label = next(l for i, l in DAYS if i == self.selected_day_id)
    #     slot_label = next(l for i, l in SLOTS if i == self.selected_slot_id)

    #     events = self.repo.get_events_for_slot(self.selected_day_id, self.selected_slot_id)
    #     is_busy = not self.repo.is_my_slot_free(self.selected_day_id, self.selected_slot_id)

    #     # ---- 内容区域：白底 + 竖排 ----
    #     content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

    #     # 白色背景
    #     with content.canvas.before:
    #         Color(1, 1, 1, 1)  # 纯白
    #         content.bg_rect = Rectangle(pos=content.pos, size=content.size)

    #     def _update_content_bg(instance, *args):
    #         content.bg_rect.pos = instance.pos
    #         content.bg_rect.size = instance.size

    #     content.bind(pos=_update_content_bg, size=_update_content_bg)

    #     # 上面的标题（哪一天第几限）
    #     title_lbl = JpLabel(text=f"{day_label} {slot_label}", size_hint_y=None, height=dp(30))
    #     content.add_widget(title_lbl)

    #     # 该コマ的募集列表
    #     if not events:
    #         content.add_widget(
    #             JpLabel(text="このコマにはまだ募集がありません。", size_hint_y=None, height=dp(40))
    #         )
    #     else:
    #         sv = ScrollView(size_hint=(1, 0.6))
    #         box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
    #         box.bind(minimum_height=box.setter('height'))
    #         sv.add_widget(box)
    #         for e in events:
    #             cat = get_category_by_id(e.category_id)
    #             lbl = JpLabel(
    #                 text=f"{cat.icon} {e.title}  参加: {e.participants_count}/{e.max_participants}",
    #                 size_hint_y=None,
    #                 height=dp(30),
    #             )
    #             box.add_widget(lbl)
    #         content.add_widget(sv)

    #     # ----- ここから 授業の追加 / 解除 -----
    #     if is_busy:
    #         # 已登记为授業
    #         content.add_widget(
    #             JpLabel(
    #                 text="このコマは現在『授業』として登録されています。",
    #                 size_hint_y=None,
    #                 height=dp(24),
    #             )
    #         )
    #         btn_clear_class = JpButton(
    #             text="授業を削除（空きコマにする）",
    #             size_hint_y=None,
    #             height=dp(36),
    #         )
    #         content.add_widget(btn_clear_class)
    #     else:
    #         # 还不是授業，可以登记
    #         content.add_widget(
    #             JpLabel(
    #                 text="このコマを『授業』として登録できます。",
    #                 size_hint_y=None,
    #                 height=dp(24),
    #             )
    #         )
    #         btn_add_class = JpButton(
    #             text="このコマを授業として追加",
    #             size_hint_y=None,
    #             height=dp(36),
    #         )
    #         content.add_widget(btn_add_class)

    #     # 募集作成按钮
    #     btn_create = JpButton(
    #         text="このコマで募集を作成",
    #         size_hint_y=None,
    #         height=dp(40),
    #     )
    #     content.add_widget(btn_create)

    #     # 关闭按钮
    #     btn_close = JpButton(
    #         text="閉じる",
    #         size_hint_y=None,
    #         height=dp(40),
    #     )
    #     content.add_widget(btn_close)

    #     # ---- Popup 本体 ----
    #     popup = Popup(
    #         title="コマ詳細",
    #         content=content,
    #         size_hint=(0.9, 0.7),
    #     )

    #     # 标题样式
    #     popup.title_font = "JP"
    #     popup.title_color = (0, 0, 0, 1)
    #     popup.title_size = dp(18)
    #     popup.separator_color = (0.2, 0.6, 0.9, 1)

    #     # 外框稍微亮一点
    #     popup.background = ""
    #     popup.background_color = (0.95, 0.95, 0.97, 1)

    #     # ----- 绑定按钮逻辑 -----
    #     def on_create_pressed(_btn):
    #         popup.dismiss()
    #         self.show_create_popup()

    #     btn_create.bind(on_press=on_create_pressed)
    #     btn_close.bind(on_press=lambda *_: popup.dismiss())

    #     # 上面为了在定义函数时引用 popup，所以在 popup 定义之后再绑
    #     if is_busy:
    #         def on_clear_class(_btn):
    #             self.repo.remove_busy_slot(self.selected_day_id, self.selected_slot_id)
    #             popup.dismiss()
    #             self.build_grid()  # 重新刷新时间割
    #         btn_clear_class.bind(on_press=on_clear_class)
    #     else:
    #         def on_add_class(_btn):
    #             self.repo.add_busy_slot(self.selected_day_id, self.selected_slot_id)
    #             popup.dismiss()
    #             self.build_grid()
    #         btn_add_class.bind(on_press=on_add_class)

    #     popup.open()

    # def show_slot_popup(self):
    #     if not self.selected_day_id or not self.selected_slot_id:
    #         return
    #     popup = Popup(
    #         title="コマ詳細",
    #         content=content,
    #         size_hint=(0.9, 0.7),
    #     )   
    #     popup.title_font = "JP"
    #     popup.title_color = (0, 0, 0, 1)
    #     popup.title_size = dp(18)
    #     popup.title_align = "center"
    #     popup.separator_color = (0.2, 0.6, 0.9, 1)  # 蓝色分隔线
    #     day_label = next(l for i, l in DAYS if i == self.selected_day_id)
    #     slot_label = next(l for i, l in SLOTS if i == self.selected_slot_id)
    #     events = self.repo.get_events_for_slot(self.selected_day_id, self.selected_slot_id)

    #     content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))
    #             # ✅ 给内容区域加白底
    #     with content.canvas.before:
    #         Color(1, 1, 1, 1)  # 纯白
    #         content.bg_rect = Rectangle(pos=content.pos, size=content.size)

    #     def _update_content_bg(inst, *args):
    #         content.bg_rect.pos = inst.pos
    #         content.bg_rect.size = inst.size

    #     content.bind(pos=_update_content_bg, size=_update_content_bg)
    #     title_lbl = JpLabel(text=f"{day_label} {slot_label}", size_hint_y=None, height=dp(30))
    #     content.add_widget(title_lbl)

    #     if not events:
    #         content.add_widget(
    #             JpLabel(text="このコマにはまだ募集がありません。", size_hint_y=None, height=dp(40))
    #         )
    #     else:
    #         sv = ScrollView(size_hint=(1, 0.6))
    #         box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
    #         box.bind(minimum_height=box.setter('height'))
    #         sv.add_widget(box)
    #         for e in events:
    #             cat = get_category_by_id(e.category_id)
    #             lbl = JpLabel(
    #                 text=f"{cat.icon} {e.title}  参加: {e.participants_count}/{e.max_participants}",
    #                 size_hint_y=None,
    #                 height=dp(30),
    #             )
    #             box.add_widget(lbl)
    #         content.add_widget(sv)

    #     btn_create = JpButton(
    #         text="このコマで募集を作成",
    #         size_hint_y=None,
    #         height=dp(40),
    #     )
    #     popup = Popup(
    #         title="コマ詳細",
    #         content=content,
    #         size_hint=(0.9, 0.7),
    #     )

    #     def on_create_pressed(_btn):
    #         popup.dismiss()
    #         self.show_create_popup()

    #     btn_create.bind(on_press=on_create_pressed)
    #     content.add_widget(btn_create)

    #     content.add_widget(
    #         JpButton(
    #             text="閉じる",
    #             size_hint_y=None,
    #             height=dp(40),
    #             on_press=lambda *_: popup.dismiss(),
    #         )
    #     )

    #     popup.open()

    # def show_create_popup(self):
    #     if not self.selected_day_id or not self.selected_slot_id:
    #         return
    #     popup = Popup(
    #         title="募集を作成",
    #         content=content,
    #         size_hint=(0.9, 0.8),
    #     )
    #     popup.title_font = "JP"
    #     popup.title_color = (0, 0, 0, 1)
    #     popup.title_size = dp(18)
    #     popup.title_align = "center"
    #     popup.separator_color = (0.2, 0.6, 0.9, 1)  
    #     state = {
    #         "category_id": CATEGORIES[0].id,
    #         "day_id": self.selected_day_id,
    #         "slot_start_id": self.selected_slot_id,
    #         "slot_end_id": self.selected_slot_id,
    #     }

    #     day_label = next(l for i, l in DAYS if i == state["day_id"])

    #     content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

    #     # カテゴリ
    #     content.add_widget(JpLabel(text="カテゴリ", size_hint_y=None, height=dp(24)))
    #     cat_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(2))
    #     content.add_widget(cat_box)

    #     def on_cat_btn_press(btn):
    #         state["category_id"] = btn.cat_id

    #     for cat in CATEGORIES:
    #         b = CategoryToggleButton(
    #             icon_text=cat.icon,
    #             label_text=cat.label,
    #             width=dp(60),
    #             # group="create_cat",  
    #         )
    #         b.cat_id = cat.id
    #         if cat.id == state["category_id"]:
    #             b.state = 'down'
    #         b.bind(on_press=on_cat_btn_press)
    #         cat_box.add_widget(b)


    #     content.add_widget(
    #         JpLabel(
    #             text=f"曜日: {day_label}（今回は固定）",
    #             size_hint_y=None,
    #             height=dp(24),
    #         )
    #     )

    #     # コマ选择
    #     content.add_widget(JpLabel(text="開始コマ / 終了コマ", size_hint_y=None, height=dp(24)))

    #     start_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(2))
    #     end_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(2))
    #     content.add_widget(start_box)
    #     content.add_widget(end_box)

    #     def on_start_btn_press(btn):
    #         state["slot_start_id"] = btn.slot_id

    #     def on_end_btn_press(btn):
    #         state["slot_end_id"] = btn.slot_id

    #     for slot_id, slot_label in SLOTS:
    #         b = GreenToggleButton(
    #             text=slot_label,
    #             size_hint_x=None,
    #             width=dp(60),
    #             group="start_slot",
    #         )
    #         b.slot_id = slot_id
    #         if slot_id == state["slot_start_id"]:
    #             b.state = 'down'
    #         b.bind(on_press=on_start_btn_press)
    #         start_box.add_widget(b)

    #     for slot_id, slot_label in SLOTS:
    #         b = GreenToggleButton(
    #             text=slot_label,
    #             size_hint_x=None,
    #             width=dp(60),
    #             group="end_slot",
    #         )
    #         b.slot_id = slot_id
    #         if slot_id == state["slot_end_id"]:
    #             b.state = 'down'
    #         b.bind(on_press=on_end_btn_press)
    #         end_box.add_widget(b)

    #     # 标题 & 最大人数
    #     ti_title = JpTextInput(
    #         hint_text="タイトル（食事などは空でも可）",
    #         multiline=False,
    #         size_hint_y=None,
    #         height=dp(32),
    #     )
    #     content.add_widget(ti_title)

    #     ti_max = JpTextInput(
    #         text="4",
    #         hint_text="最大参加人数",
    #         multiline=False,
    #         size_hint_y=None,
    #         height=dp(32),
    #     )
    #     content.add_widget(ti_max)

    #     free_count = self.repo.get_free_user_info(
    #         state["day_id"], state["slot_start_id"], state["slot_end_id"]
    #     )
    #     lbl_free = JpLabel(
    #         text=f"この時間帯の空きコマユーザー（推定）: {free_count}人",
    #         size_hint_y=None,
    #         height=dp(24),
    #     )
    #     content.add_widget(lbl_free)

    #     popup = Popup(
    #         title="募集を作成",
    #         content=content,
    #         size_hint=(0.9, 0.8),
    #     )

    #     def on_create(_btn):
    #         title = ti_title.text.strip()
    #         cat_id = state["category_id"]
    #         if not title:
    #             if cat_id == "meal":
    #                 title = "ランチ"
    #             elif cat_id == "study":
    #                 title = "勉強会"
    #             else:
    #                 title = get_category_by_id(cat_id).label

    #         try:
    #             max_part = int(ti_max.text.strip())
    #         except ValueError:
    #             max_part = 4

    #         try:
    #             si = SLOT_IDS.index(state["slot_start_id"])
    #             ei = SLOT_IDS.index(state["slot_end_id"])
    #         except ValueError:
    #             si, ei = 0, 0
    #         if ei < si:
    #             si, ei = ei, si
    #         slot_start_id = SLOT_IDS[si]
    #         slot_end_id = SLOT_IDS[ei]

    #         self.repo.create_event(
    #             category_id=cat_id,
    #             day_id=state["day_id"],
    #             slot_start_id=slot_start_id,
    #             slot_end_id=slot_end_id,
    #             title=title,
    #             max_participants=max_part,
    #         )
    #         popup.dismiss()
    #         self.build_grid()

    #     btn_create = JpButton(
    #         text="作成",
    #         size_hint_y=None,
    #         height=dp(40),
    #     )
    #     btn_create.bind(on_press=on_create)

    #     btn_cancel = JpButton(
    #         text="キャンセル",
    #         size_hint_y=None,
    #         height=dp(40),
    #         on_press=lambda *_: popup.dismiss(),
    #     )

    #     content.add_widget(btn_create)
    #     content.add_widget(btn_cancel)

    #     popup.open()

    def show_create_popup(self):
        """创建募集弹窗"""
        if not self.selected_day_id or not self.selected_slot_id:
            return

        state = {
            "category_id": CATEGORIES[0].id,
            "day_id": self.selected_day_id,
            "slot_start_id": self.selected_slot_id,
            "slot_end_id": self.selected_slot_id,
        }

        day_label = next(l for i, l in DAYS if i == state["day_id"])

        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        with content.canvas.before:
            Color(1, 1, 1, 1)
            content.bg_rect = Rectangle(pos=content.pos, size=content.size)

        def _update_content_bg(instance, *args):
            content.bg_rect.pos = instance.pos
            content.bg_rect.size = instance.size

        content.bind(pos=_update_content_bg, size=_update_content_bg)

        # カテゴリ
        content.add_widget(JpLabel(text="カテゴリ", size_hint_y=None, height=dp(24)))
        cat_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(2))
        content.add_widget(cat_box)

        def on_cat_btn_press(btn):
            state["category_id"] = btn.cat_id

        for cat in CATEGORIES:
            b = CategoryToggleButton(
                icon_text=cat.icon,
                label_text=cat.label,
                width=dp(60),
            )
            b.cat_id = cat.id
            if cat.id == state["category_id"]:
                b.state = 'down'
            b.bind(on_press=on_cat_btn_press)
            cat_box.add_widget(b)

        # 曜日
        content.add_widget(
            JpLabel(
                text=f"曜日: {day_label}（今回は固定）",
                size_hint_y=None,
                height=dp(24),
            )
        )

        # コマ範囲
        content.add_widget(JpLabel(text="開始コマ / 終了コマ", size_hint_y=None, height=dp(24)))

        start_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(2))
        end_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(2))
        content.add_widget(start_box)
        content.add_widget(end_box)

        def on_start_btn_press(btn):
            state["slot_start_id"] = btn.slot_id

        def on_end_btn_press(btn):
            state["slot_end_id"] = btn.slot_id

        for slot_id, slot_label in SLOTS:
            b = GreenToggleButton(
                text=slot_label,
                size_hint_x=None,
                width=dp(60),
                group="start_slot",
            )
            b.slot_id = slot_id
            if slot_id == state["slot_start_id"]:
                b.state = 'down'
            b.bind(on_press=on_start_btn_press)
            start_box.add_widget(b)

        for slot_id, slot_label in SLOTS:
            b = GreenToggleButton(
                text=slot_label,
                size_hint_x=None,
                width=dp(60),
                group="end_slot",
            )
            b.slot_id = slot_id
            if slot_id == state["slot_end_id"]:
                b.state = 'down'
            b.bind(on_press=on_end_btn_press)
            end_box.add_widget(b)

        # タイトル / 最大人数
        ti_title = JpTextInput(
            hint_text="タイトル（食事などは空でも可）",
            multiline=False,
            size_hint_y=None,
            height=dp(32),
        )
        content.add_widget(ti_title)

        ti_max = JpTextInput(
            text="4",
            hint_text="最大参加人数",
            multiline=False,
            size_hint_y=None,
            height=dp(32),
        )
        content.add_widget(ti_max)

        # 空きコマユーザ数
        free_count = self.repo.get_free_user_info(
            state["day_id"], state["slot_start_id"], state["slot_end_id"]
        )
        lbl_free = JpLabel(
            text=f"この時間帯の空きコマユーザー（推定）: {free_count}人",
            size_hint_y=None,
            height=dp(24),
        )
        content.add_widget(lbl_free)

        popup = Popup(
            title="募集を作成",
            content=content,
            size_hint=(0.9, 0.8),
        )

        popup.title_font = "JP"
        popup.title_color = (0, 0, 0, 1)
        popup.title_size = dp(18)
        popup.separator_color = (0.2, 0.6, 0.9, 1)
        popup.background = ""
        popup.background_color = (0.95, 0.95, 0.97, 1)

        def on_create(_btn):
            title = ti_title.text.strip()
            cat_id = state["category_id"]
            if not title:
                if cat_id == "meal":
                    title = "ランチ"
                elif cat_id == "study":
                    title = "勉強会"
                else:
                    title = get_category_by_id(cat_id).label

            try:
                max_part = int(ti_max.text.strip())
            except ValueError:
                max_part = 4

            try:
                si = SLOT_IDS.index(state["slot_start_id"])
                ei = SLOT_IDS.index(state["slot_end_id"])
            except ValueError:
                si, ei = 0, 0
            if ei < si:
                si, ei = ei, si
            slot_start_id = SLOT_IDS[si]
            slot_end_id = SLOT_IDS[ei]

            self.repo.create_event(
                category_id=cat_id,
                day_id=state["day_id"],
                slot_start_id=slot_start_id,
                slot_end_id=slot_end_id,
                title=title,
                max_participants=max_part,
            )
            popup.dismiss()
            self.build_grid()

        btn_create = JpButton(
            text="作成",
            size_hint_y=None,
            height=dp(40),
        )
        btn_create.bind(on_press=on_create)

        btn_cancel = JpButton(
            text="キャンセル",
            size_hint_y=None,
            height=dp(40),
            on_press=lambda *_: popup.dismiss(),
        )

        content.add_widget(btn_create)
        content.add_widget(btn_cancel)

        popup.open()

# ---------- 募集検索画面 ----------

class SearchScreen(Screen):
    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo

        self.selected_category_ids: Set[str] = set()
        self.selected_day_ids: Set[str] = set()
        self.selected_slot_ids: Set[str] = set()
        self.only_my_free_slots: bool = False

        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))
        self.add_widget(root)

        # カテゴリ
        root.add_widget(JpLabel(text="カテゴリ（複数選択可）", size_hint_y=None, height=dp(24)))
        cat_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        root.add_widget(cat_box)

        def on_cat_toggle(btn):
            cat_id = btn.cat_id
            if btn.state == 'down':
                self.selected_category_ids.add(cat_id)
            else:
                self.selected_category_ids.discard(cat_id)
            self.refresh_results()

        for cat in CATEGORIES:
            b = CategoryToggleButton(
                icon_text=cat.icon,
                label_text=cat.label,
                width=dp(70),
            )
            b.cat_id = cat.id
            b.bind(on_press=on_cat_toggle)
            cat_box.add_widget(b)


        # 曜日
        root.add_widget(JpLabel(text="曜日", size_hint_y=None, height=dp(24)))
        day_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(4))
        root.add_widget(day_box)

        def on_day_toggle(btn):
            day_id = btn.day_id
            if btn.state == 'down':
                self.selected_day_ids.add(day_id)
            else:
                self.selected_day_ids.discard(day_id)
            self.refresh_results()

        for day_id, day_label in DAYS:
            b = GreenToggleButton(
                text=day_label,
                size_hint_x=None,
                width=dp(60),
            )
            b.day_id = day_id
            b.bind(on_press=on_day_toggle)
            day_box.add_widget(b)

        # コマ / 昼休み
        root.add_widget(JpLabel(text="コマ / 昼休み", size_hint_y=None, height=dp(24)))
        slot_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(32), spacing=dp(4))
        root.add_widget(slot_box)

        def on_slot_toggle(btn):
            slot_id = btn.slot_id
            if btn.state == 'down':
                self.selected_slot_ids.add(slot_id)
            else:
                self.selected_slot_ids.discard(slot_id)
            self.refresh_results()

        for slot_id, slot_label in SLOTS:
            b = GreenToggleButton(
                text=slot_label,
                size_hint_x=None,
                width=dp(70),
            )
            b.slot_id = slot_id
            b.bind(on_press=on_slot_toggle)
            slot_box.add_widget(b)

        # 「自分が空いているコマだけ表示」
        cb_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(32),
            spacing=dp(4),
        )
        cb = CheckBox()
        lbl = JpLabel(text="自分が空いているコマだけ表示")
        cb_box.add_widget(cb)
        cb_box.add_widget(lbl)
        root.add_widget(cb_box)

        def on_checkbox_active(instance, value):
            self.only_my_free_slots = bool(value)
            self.refresh_results()

        cb.bind(active=on_checkbox_active)

        # 结果区域
        root.add_widget(JpLabel(text="検索結果", size_hint_y=None, height=dp(24)))

        self.result_scroll = ScrollView()
        self.result_box = BoxLayout(
            orientation='vertical', size_hint_y=None, spacing=dp(4)
        )
        self.result_box.bind(minimum_height=self.result_box.setter('height'))
        self.result_scroll.add_widget(self.result_box)

        root.add_widget(self.result_scroll)

        self.refresh_results()

    def refresh_results(self):
        res = self.repo.search_events(
            category_ids=self.selected_category_ids,
            day_ids=self.selected_day_ids,
            slot_ids=self.selected_slot_ids,
            only_my_free_slots=self.only_my_free_slots,
        )
        self.result_box.clear_widgets()

        if not res:
            self.result_box.add_widget(
                JpLabel(text="該当する募集がありません。", size_hint_y=None, height=dp(30))
            )
            return

        for e in res:
            cat = get_category_by_id(e.category_id)
            day_label = next(l for i, l in DAYS if i == e.day_id)
            slot_start = next(l for i, l in SLOTS if i == e.slot_start_id)
            slot_end = next(l for i, l in SLOTS if i == e.slot_end_id)
            text = (
                f"{cat.icon} {e.title}\n"
                f"{day_label} {slot_start}〜{slot_end}  "
                f"参加: {e.participants_count}/{e.max_participants}"
            )
            lbl = JpLabel(
                text=text,
                size_hint_y=None,
                height=dp(50),
            )
            self.result_box.add_widget(lbl)

class UserScreen(Screen):
    """ユーザー登録 / 表示画面"""

    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo

        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        self.add_widget(root)

        # 当前用户
        self.lbl_current = JpLabel(
            text=f"現在のユーザー名: {self.repo.user_name}",
            size_hint_y=None,
            height=dp(30),
        )
        root.add_widget(self.lbl_current)

        root.add_widget(
            JpLabel(
                text="ユーザー名を登録してください",
                size_hint_y=None,
                height=dp(24),
            )
        )

        # 输入框（如果已经有名字就预填）
        init_text = "" if self.repo.user_name == "ゲスト" else self.repo.user_name
        self.ti_name = JpTextInput(
            text=init_text,
            multiline=False,
            size_hint_y=None,
            height=dp(36),
        )
        root.add_widget(self.ti_name)

        btn_save = JpButton(
            text="登録",
            size_hint_y=None,
            height=dp(40),
        )
        root.add_widget(btn_save)

        self.info_label = JpLabel(
            text="",
            size_hint_y=None,
            height=dp(24),
        )
        root.add_widget(self.info_label)

        btn_save.bind(on_press=self.on_save)

    def on_save(self, *_):
        name = self.ti_name.text.strip()
        if not name:
            self.info_label.text = "ユーザー名を入力してください。"
            return
        self.repo.set_user(name)
        self.lbl_current.text = f"現在のユーザー名: {self.repo.user_name}"
        self.info_label.text = "登録しました。"

# ---------- Root & App ----------

class RootWidget(BoxLayout):
    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.repo = repo

        # 顶部 tab
        tab_bar = BoxLayout(
            orientation='horizontal', size_hint_y=None, height=dp(40)
        )
        self.add_widget(tab_bar)

        common_kwargs = dict(
            background_normal="",
            background_down="",
            color=(1, 1, 1, 1),
        )

        self.btn_timetable = JpButton(text="時間割", **common_kwargs)
        self.btn_search = JpButton(text="募集検索", **common_kwargs)
        self.btn_user = JpButton(text="ユーザー", **common_kwargs)

        tab_bar.add_widget(self.btn_timetable)
        tab_bar.add_widget(self.btn_search)
        tab_bar.add_widget(self.btn_user)

        # ScreenManager
        self.sm = ScreenManager()
        self.add_widget(self.sm)

        self.timetable_screen = TimetableScreen(name="timetable", repo=self.repo)
        self.search_screen = SearchScreen(name="search", repo=self.repo)
        self.user_screen = UserScreen(name="user", repo=self.repo)

        self.sm.add_widget(self.timetable_screen)
        self.sm.add_widget(self.search_screen)
        self.sm.add_widget(self.user_screen)

        self.btn_timetable.bind(on_press=lambda *_: self.switch_to("timetable"))
        self.btn_search.bind(on_press=lambda *_: self.switch_to("search"))
        self.btn_user.bind(on_press=lambda *_: self.switch_to("user"))

        self.switch_to("timetable")

    def switch_to(self, name: str):
        self.sm.current = name
        active = [0.2, 0.6, 0.9, 1]
        inactive = [0.3, 0.3, 0.3, 1]

        self.btn_timetable.background_color = active if name == "timetable" else inactive
        self.btn_search.background_color = active if name == "search" else inactive
        self.btn_user.background_color = active if name == "user" else inactive

class ComaLinkApp(App):
    def build(self):
        self.title = "Coma-Link (Python/Kivy)"
        repo = ComaLinkRepository()
        return RootWidget(repo=repo)


if __name__ == "__main__":
    ComaLinkApp().run()
