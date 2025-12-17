# -*- coding: utf-8 -*-
from dataclasses import dataclass, asdict
from typing import List, Set, Dict, Tuple, Optional
from datetime import datetime
import base64
import json
import os
import re
import threading
import hashlib
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
from kivy.uix.behaviors import ToggleButtonBehavior, ButtonBehavior
from kivy.core.text import LabelBase
from kivy.resources import resource_add_path
from kivy.clock import Clock
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.widget import Widget

try:
    import requests
except ImportError:
    requests = None

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
            self.bg_color.rgba = (0.9, 1.0, 0.9, 1)  # 緑
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
    ("LUNCH", "昼休み"),
    ("3", "3限"),
    ("4", "4限"),
    ("5", "5限"),
]
SLOT_IDS = [s[0] for s in SLOTS]
DAY_IDS = [d[0] for d in DAYS]


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


@dataclass
class ClassInfo:
    day_id: str
    slot_id: str
    title: str = ""
    classroom: str = ""


class DoubaoVisionClientError(Exception):
    """専用の例外"""


class DoubaoVisionClient:
    """
    マルチモーダルAPIを叩いて画像から授業コマを抽出する簡易クライアント。

    実際のエンドポイントやモデル名は環境に合わせて `DOUBAO_VISION_ENDPOINT`
    `DOUBAO_VISION_MODEL` で上書きできる。
    """

    DEFAULT_ENDPOINT = "https://api.doubao.com/v1/vision/chat/completions"
    DEFAULT_MODEL = "doubao-vision-pro"

    SYSTEM_PROMPT = (
        "あなたは日本の大学時間割画像を解析し、授業のあるコマをJSONで返すアシスタントです。"
        "各コマには day_id（MON〜FRI）、slot_ids（1〜5, LUNCH）、授業タイトル（title）、"
        "教室名（classroom、分かれば）を含めてください。JSON以外の文字は出力しないでください。"
    )

    USER_PROMPT = (
        "次の画像は大学の時間割です。授業が入っているコマを抽出し、"
        "以下の形式で返答してください:\n"
        "{\n"
        '  "busy_slots": [\n'
        '    {"day_id": "MON", "slot_ids": ["1","2"], "title": "経済学", "classroom": "A101"},\n'
        '    {"day_id": "TUE", "slot_ids": ["3"], "title": "ゼミ"}\n'
        "  ]\n"
        "}\n"
        "title/classroom が不明な場合は空文字にしてください。"
    )

    _ZENKAKU_TABLE = str.maketrans("０１２３４５", "012345")

    DAY_KEYWORDS = {
        "mon": "MON",
        "monday": "MON",
        "月": "MON",
        "tue": "TUE",
        "tuesday": "TUE",
        "火": "TUE",
        "wed": "WED",
        "wednesday": "WED",
        "水": "WED",
        "thu": "THU",
        "thursday": "THU",
        "木": "THU",
        "fri": "FRI",
        "friday": "FRI",
        "金": "FRI",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if requests is None:
            raise DoubaoVisionClientError("requestsライブラリが必要です。pip install requests を実行してください。")

        self.api_key = api_key or os.getenv("DOUBAO_API_KEY")
        if not self.api_key:
            raise DoubaoVisionClientError("APIキーが設定されていません。環境変数 DOUBAO_API_KEY を指定するかポップアップで入力してください。")

        self.endpoint = endpoint or os.getenv("DOUBAO_VISION_ENDPOINT", self.DEFAULT_ENDPOINT)
        self.model = model or os.getenv("DOUBAO_VISION_MODEL", self.DEFAULT_MODEL)

    def recognize_timetable(self, image_path: str) -> List[Dict[str, str]]:
        image_b64 = self._encode_image(image_path)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": [{"type": "text", "text": self.SYSTEM_PROMPT}]},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.USER_PROMPT},
                        {"type": "input_image", "image_base64": image_b64},
                    ],
                },
            ],
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=90)
        except requests.RequestException as exc:
            raise DoubaoVisionClientError(f"APIへの接続に失敗しました: {exc}") from exc

        if response.status_code >= 400:
            raise DoubaoVisionClientError(f"APIエラー: {response.status_code} {response.text}")

        try:
            data = response.json()
        except ValueError as exc:
            raise DoubaoVisionClientError("APIの応答をJSONとして解析できません。") from exc

        raw_text = self._extract_text(data)
        struct = self._extract_struct(raw_text)
        busy_slots = self._collect_busy_slots(struct)
        if not busy_slots:
            raise DoubaoVisionClientError("AIが授業コマを返しませんでした。画像やプロンプトを確認してください。")
        return busy_slots

    def _encode_image(self, image_path: str) -> str:
        if not os.path.exists(image_path):
            raise DoubaoVisionClientError("選択した画像ファイルが見つかりません。")
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except OSError as exc:
            raise DoubaoVisionClientError(f"画像ファイルの読み込みに失敗しました: {exc}") from exc

    def _extract_text(self, data: Dict) -> str:
        texts: List[str] = []
        choices = data.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                message = choice.get("message") if isinstance(choice, dict) else {}
                content = message.get("content") if isinstance(message, dict) else None
                if isinstance(content, list):
                    for chunk in content:
                        if isinstance(chunk, dict) and chunk.get("type") == "text":
                            texts.append(chunk.get("text", ""))
                elif isinstance(content, str):
                    texts.append(content)
        if not texts and "output_text" in data:
            texts.append(str(data["output_text"]))
        if not texts:
            raise DoubaoVisionClientError("AIから解析テキストが取得できませんでした。")
        return "\n".join(t for t in texts if t).strip()

    def _extract_struct(self, raw_text: str):
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        raise DoubaoVisionClientError("AIの応答からJSONを抽出できません。")

    def _collect_busy_slots(self, struct) -> List[Dict[str, str]]:
        busy: Dict[Tuple[str, str], Dict[str, str]] = {}
        entries = None
        if isinstance(struct, dict):
            for key in ("busy_slots", "classes", "lessons"):
                value = struct.get(key)
                if isinstance(value, list):
                    entries = value
                    break
            if entries is None:
                entries = [{ "day_id": key, "slot_ids": value } for key, value in struct.items()]
        elif isinstance(struct, list):
            entries = struct
        else:
            return busy

        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            day_id = entry.get("day_id") or entry.get("day") or entry.get("weekday")
            slot_values = entry.get("slot_ids") or entry.get("slots") or entry.get("periods") or []
            norm_day = self._normalize_day(day_id)
            if not norm_day:
                continue
            if isinstance(slot_values, str):
                slot_values = [slot_values]
            title = entry.get("title") or entry.get("course") or entry.get("name") or entry.get("subject")
            classroom = entry.get("classroom") or entry.get("room") or entry.get("location")
            for slot in slot_values:
                norm_slot = self._normalize_slot(slot)
                if norm_slot:
                    busy[(norm_day, norm_slot)] = {
                        "day_id": norm_day,
                        "slot_id": norm_slot,
                        "title": title or "",
                        "classroom": classroom or "",
                    }
        return list(busy.values())

    def _normalize_day(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        key = str(value).strip().lower()
        for alias, day in self.DAY_KEYWORDS.items():
            if alias in key:
                return day
        return None

    def _normalize_slot(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        slot = str(value).strip().lower()
        slot = slot.translate(self._ZENKAKU_TABLE)
        slot = slot.replace("限", "").replace("コマ", "").replace("時限", "")
        slot = slot.replace("period", "").replace("時", "")
        slot = slot.replace("〜", "-").replace("～", "-")
        if "lunch" in slot or "昼" in slot or "休" in slot:
            return "LUNCH"
        digits = re.findall(r"[1-5]", slot)
        if digits:
            return digits[0]
        return None


DATA_FILE = "coma_data.json"  
class ComaLinkRepository:
    def __init__(self, current_user_id: Optional[str] = None):
        self.user_name: str = "未ログイン"
        self.current_user_id: Optional[str] = None
        self.initial_user_hint: Optional[str] = current_user_id
        self.events: List[Event] = []
        self.class_schedule_by_user: Dict[str, Dict[Tuple[str, str], ClassInfo]] = {}
        self.event_participants: Dict[str, Set[str]] = {}
        self.event_pending: Dict[str, Set[str]] = {}
        self.users: Dict[str, Dict[str, str]] = {}

        self.load()

        if not self.events and not self.class_schedule_by_user:
            # ここではデフォルトデータを生成せず、完全に空の状態で開始する
            self.save()

    # ----------------- デフォルト初期データ -----------------
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

        # デフォルトデータは生成しない（空状態で開始）
        self.class_schedule_by_user = {}
        self.event_participants = {}
        self.event_pending = {}
        if not self.users:
            self.users = {}
        self.current_user_id = None
        self.user_name = "未ログイン"

    def _ensure_default_user(self):
        if not self.users:
            self.users = {}

    def _hash_password(self, username: str, password: str) -> str:
        salted = f"{username}:{password}"
        return hashlib.sha256(salted.encode("utf-8")).hexdigest()

    def register_user(self, username: str, password: str, display_name: str) -> Tuple[bool, str]:
        username = username.strip()
        display_name = display_name.strip() or username
        if not username or not password:
            return False, "ユーザー名とパスワードを入力してください。"
        if username in self.users:
            return False, "このユーザー名は既に登録されています。"
        self.users[username] = {
            "password_hash": self._hash_password(username, password),
            "display_name": display_name,
        }
        self.current_user_id = username
        self.user_name = display_name
        self.save()
        return True, "登録しました。"

    def login_user(self, username: str, password: str) -> Tuple[bool, str]:
        username = username.strip()
        info = self.users.get(username)
        if not info or not info.get("password_hash"):
            return False, "ユーザー名またはパスワードが違います。"
        if info["password_hash"] != self._hash_password(username, password):
            return False, "ユーザー名またはパスワードが違います。"
        self.current_user_id = username
        self.user_name = info.get("display_name", username)
        self.save()
        return True, f"{self.user_name} としてログインしました。"

    def logout_user(self):
        self.current_user_id = None
        self.user_name = "未ログイン"
        self.save()

    def is_logged_in(self) -> bool:
        return bool(self.current_user_id)

    def get_user_display_name(self, user_id: str) -> str:
        info = self.users.get(user_id)
        if not info:
            return user_id
        return info.get("display_name", user_id)

    # ----------------- 永続化（JSON） -----------------
    def load(self):
        """JSON ファイルから events / 授業コマ を読み込む"""
        if not os.path.exists(DATA_FILE):
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # 読み込みに失敗したら、デフォルト初期化を使う
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
        ep_raw = data.get("event_participants", {})
        self.event_participants = {
            eid: set(uids) for eid, uids in ep_raw.items()
        }

        pending_raw = data.get("event_pending", {})
        self.event_pending = {
            eid: set(uids) for eid, uids in pending_raw.items()
        }

        users_raw = data.get("users", {})
        if isinstance(users_raw, dict):
            parsed_users: Dict[str, Dict[str, str]] = {}
            for username, info in users_raw.items():
                if not isinstance(info, dict):
                    continue
                password_hash = info.get("password_hash", "")
                display_name = info.get("display_name", username)
                parsed_users[username] = {
                    "password_hash": password_hash,
                    "display_name": display_name,
                }
            self.users = parsed_users
        else:
            self.users = {}

        if not self.users:
            self._ensure_default_user()
        if "guest" in self.users and not self.users["guest"].get("password_hash"):
            self.users.pop("guest", None)

        saved_user = data.get("current_user_id")
        if saved_user in self.users:
            self.current_user_id = saved_user
        elif self.initial_user_hint and self.initial_user_hint in self.users:
            self.current_user_id = self.initial_user_hint
        else:
            self.current_user_id = None

        if self.current_user_id:
            self.user_name = self.users.get(self.current_user_id, {}).get("display_name", "未ログイン")
        else:
            self.user_name = "未ログイン"


        self.class_schedule_by_user = {}
        cs_raw = data.get("class_schedule_by_user")
        if isinstance(cs_raw, dict):
            for uid, items in cs_raw.items():
                schedule: Dict[Tuple[str, str], ClassInfo] = {}
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        day_id = item.get("day_id")
                        slot_id = item.get("slot_id")
                        if day_id not in DAY_IDS or slot_id not in SLOT_IDS:
                            continue
                        title = item.get("title", "")
                        classroom = item.get("classroom", "")
                        schedule[(day_id, slot_id)] = ClassInfo(
                            day_id=day_id,
                            slot_id=slot_id,
                            title=title,
                            classroom=classroom,
                        )
                if schedule:
                    self.class_schedule_by_user[uid] = schedule

        # migrate legacy my_classes / my_busy_slots into current user
        classes_raw = data.get("my_classes")
        if isinstance(classes_raw, list):
            schedule: Dict[Tuple[str, str], ClassInfo] = {}
            for item in classes_raw:
                if not isinstance(item, dict):
                    continue
                day_id = item.get("day_id")
                slot_id = item.get("slot_id")
                if day_id not in DAY_IDS or slot_id not in SLOT_IDS:
                    continue
                title = item.get("title", "")
                classroom = item.get("classroom", "")
                schedule[(day_id, slot_id)] = ClassInfo(
                    day_id=day_id,
                    slot_id=slot_id,
                    title=title,
                    classroom=classroom,
                )
            if schedule:
                target_uid = self.current_user_id or saved_user or self.initial_user_hint or "user_me"
                self.class_schedule_by_user[target_uid] = schedule
        elif "my_busy_slots" in data:
            slots = data.get("my_busy_slots", [])
            schedule: Dict[Tuple[str, str], ClassInfo] = {
                (day, slot): ClassInfo(day, slot)
                for day, slot in slots
                if day in DAY_IDS and slot in SLOT_IDS
            }
            if schedule:
                target_uid = self.current_user_id or saved_user or self.initial_user_hint or "user_me"
                self.class_schedule_by_user[target_uid] = schedule

        for e in self.events:
            self.event_participants.setdefault(e.id, {e.owner_user_id})
            self.event_pending.setdefault(e.id, set())
            e.participants_count = max(e.participants_count, len(self.event_participants[e.id]))

    def join_event(self, event_id: str) -> str:
        if not self.is_logged_in():
            return "login_required"

        event = self.get_event_by_id(event_id)
        if not event:
            return "not_found"
        if event.owner_user_id == self.current_user_id:
            return "owner"

        participants = self.event_participants.setdefault(event_id, set())
        pending = self.event_pending.setdefault(event_id, set())
        if len(participants) >= event.max_participants:
            return "full"

        pending.add(self.current_user_id)
        self.save()
        return "pending"

    def approve_event_application(self, event_id: str, user_id: str) -> str:
        event = self.get_event_by_id(event_id)
        if not event:
            return "not_found"
        if event.owner_user_id != self.current_user_id:
            return "forbidden"
        pending = self.event_pending.setdefault(event_id, set())
        if user_id not in pending:
            return "missing"
        participants = self.event_participants.setdefault(event_id, set())
        if len(participants) >= event.max_participants:
            return "full"
        pending.remove(user_id)
        participants.add(user_id)
        event.participants_count = len(participants)
        self.save()
        return "ok"

    def reject_event_application(self, event_id: str, user_id: str) -> str:
        event = self.get_event_by_id(event_id)
        if not event:
            return "not_found"
        if event.owner_user_id != self.current_user_id:
            return "forbidden"
        pending = self.event_pending.setdefault(event_id, set())
        if user_id not in pending:
            return "missing"
        pending.remove(user_id)
        self.save()
        return "ok"

    def save(self):
        """現在のデータを JSON ファイルに書き込む"""
        data = {
            "events": [e.__dict__ for e in self.events],
            "class_schedule_by_user": {
                uid: [
                    {
                        "day_id": info.day_id,
                        "slot_id": info.slot_id,
                        "title": info.title,
                        "classroom": info.classroom,
                    }
                    for info in schedule.values()
                ]
                for uid, schedule in self.class_schedule_by_user.items()
            },
            "user_name": self.user_name,
            "current_user_id": self.current_user_id,
            # ✅ 报名名单，set 转 list
            "event_participants": {
                eid: list(uids) for eid, uids in self.event_participants.items()
            },
            "event_pending": {
                eid: list(uids) for eid, uids in self.event_pending.items()
            },
            "users": self.users,
        }
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("データ保存失敗:", e)

    # ----------------- ビジネスロジック -----------------
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

    def get_event_by_id(self, event_id: str) -> Optional[Event]:
        for e in self.events:
            if e.id == event_id:
                return e
        return None

    def get_event_participants(self, event_id: str) -> Set[str]:
        return self.event_participants.get(event_id, set())

    def get_event_pending(self, event_id: str) -> Set[str]:
        return self.event_pending.get(event_id, set())

    def get_owner_pending_events(self, owner_id: str) -> List[Event]:
        if not owner_id:
            return []
        return [
            e
            for e in self.events
            if e.owner_user_id == owner_id and self.event_pending.get(e.id)
        ]

    def _current_schedule(self) -> Dict[Tuple[str, str], ClassInfo]:
        if self.current_user_id and self.current_user_id in self.class_schedule_by_user:
            return self.class_schedule_by_user[self.current_user_id]
        return {}

    def is_my_slot_free(self, day_id: str, slot_id: str) -> bool:
        return (day_id, slot_id) not in self._current_schedule()

    def _event_is_free_for_me(self, event: Event) -> bool:
        try:
            start_idx = SLOT_IDS.index(event.slot_start_id)
            end_idx = SLOT_IDS.index(event.slot_end_id)
        except ValueError:
            return False
        for i in range(start_idx, end_idx + 1):
            slot_id = SLOT_IDS[i]
            if (event.day_id, slot_id) in self._current_schedule():
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
        key = f"{day_id}-{slot_start_id}-{slot_end_id}-{len(self.events)}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        value = int(digest[:4], 16)
        return 5 + (value % 18)

    def create_event(
        self,
        category_id: str,
        day_id: str,
        slot_start_id: str,
        slot_end_id: str,
        title: str,
        max_participants: int,
    ) -> Event:
        if not self.is_logged_in():
            raise ValueError("login_required")
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
        self.event_participants[new_id] = {self.current_user_id}
        self.event_pending[new_id] = set()
        self.save()
        return ev

    def get_class_info(self, day_id: str, slot_id: str) -> Optional[ClassInfo]:
        return self._current_schedule().get((day_id, slot_id))

    def add_busy_slot(self, day_id: str, slot_id: str, title: str = "", classroom: str = ""):
        """指定コマを『授業』として登録 or 更新"""
        if not self.is_logged_in():
            raise ValueError("login_required")
        schedule = self.class_schedule_by_user.setdefault(self.current_user_id, {})
        schedule[(day_id, slot_id)] = ClassInfo(
            day_id=day_id,
            slot_id=slot_id,
            title=title.strip(),
            classroom=classroom.strip(),
        )
        self.save()

    def remove_busy_slot(self, day_id: str, slot_id: str):
        """指定コマの『授業』登録を解除"""
        if not self.is_logged_in():
            raise ValueError("login_required")
        schedule = self.class_schedule_by_user.get(self.current_user_id)
        if schedule:
            schedule.pop((day_id, slot_id), None)
        self.save()

    def apply_busy_slots(self, busy_slots: List[Dict[str, str]], merge: bool = False) -> int:
        """AIなどから受け取った授業コマを一括で登録"""
        if not self.is_logged_in():
            raise ValueError("login_required")
        valid_days = set(DAY_IDS)
        valid_slots = set(SLOT_IDS)
        normalized: Dict[Tuple[str, str], ClassInfo] = {}
        for item in busy_slots:
            if not isinstance(item, dict):
                continue
            day = item.get("day_id")
            slot = item.get("slot_id")
            if day not in valid_days or slot not in valid_slots:
                continue
            title = item.get("title", "")
            classroom = item.get("classroom", "")
            normalized[(day, slot)] = ClassInfo(
                day_id=day,
                slot_id=slot,
                title=title,
                classroom=classroom,
            )
        if not normalized:
            raise ValueError("有効な授業コマが見つかりませんでした。")
        schedule = self.class_schedule_by_user.setdefault(self.current_user_id, {})
        if merge:
            schedule.update(normalized)
        else:
            self.class_schedule_by_user[self.current_user_id] = dict(normalized)
        self.save()
        return len(normalized)
# ---------- UI コンポーネント ----------

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
    """表頭：薄い灰色の背景 + 緑の枠"""

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


class MarqueeBox(BoxLayout):
    """
    近接コマ向けの横スクロールテキスト。
    ScrollView を使い、一定速度で scroll_x を進める簡易マルチライン。
    """

    def __init__(self, text: str, speed: float = 40.0, **kwargs):
        kwargs.setdefault("orientation", "horizontal")
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(24))
        kwargs.setdefault("padding", (dp(2), 0))
        super().__init__(**kwargs)

        self.speed = speed
        self._offset = 0.0
        self._scroll = ScrollView(
            do_scroll_x=True,
            do_scroll_y=False,
            bar_width=0,
            size_hint=(1, 1),
        )
        self.add_widget(self._scroll)

        self.label = JpLabel(
            text=text,
            halign="left",
            valign="middle",
            size_hint=(None, 1),
            font_size=dp(13),
        )
        self.label.bind(texture_size=self._update_label_width)
        self._scroll.add_widget(self.label)

        self._ev = Clock.schedule_interval(self._step, 1 / 30)

    def _update_label_width(self, instance, size):
        instance.width = size[0] + dp(8)
        instance.text_size = (None, None)

    def _step(self, dt):
        if not self.parent:
            return False
        if self.label.width <= self._scroll.width:
            self._scroll.scroll_x = 0
            return True

        distance = max(1.0, self.label.width - self._scroll.width)
        self._offset = (self._offset + self.speed * dt) % (distance + self._scroll.width)
        self._scroll.scroll_x = min(1.0, self._offset / distance)
        return True


class AvailabilityBar(Widget):
    """
    空き量を濃淡で表現する横バー。文字は出さない。
    free_users が多いほど薄く（空き多）、少ないほど濃く（残りわずか）。
    """

    def __init__(self, free_users: int, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(10))
        super().__init__(**kwargs)
        self.free_users = free_users
        with self.canvas:
            self.bg_color = Color(0.9, 0.95, 1.0, 1)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            self.fill_color = Color(0.35, 0.6, 0.95, 0.9)
            self.fill_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)
        self._update_rect()

    def _update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

        # free_users: 5〜22 想定。空き多 -> fill を少なく、残りわずか -> fill を大きく。
        normalized_free = max(0.0, min(1.0, (self.free_users - 5) / 17.0))
        fill_ratio = 1.0 - normalized_free  # 残りわずかほど 1.0 に近づく
        fill_ratio = max(0.1, min(1.0, fill_ratio))
        self.fill_rect.pos = self.pos
        self.fill_rect.size = (self.width * fill_ratio, self.height)


class SlotCard(ButtonBehavior, BoxLayout):
    """
    グリッド内の1コマ表示。近いコマのみタイトルが横スクロール。
    自分の空き枠はアウトライン色で区別し、空き量はバーの濃淡で示す。
    """

    def __init__(
        self,
        day_id: str,
        slot_id: str,
        slot_label: str,
        events: List[Event],
        free_users: int,
        class_info: Optional[ClassInfo],
        is_my_free: bool,
        is_near: bool,
        **kwargs,
    ):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", (dp(6), dp(6)))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)
        self.day_id = day_id
        self.slot_id = slot_id

        has_events = len(events) > 0
        first_title = events[0].title if has_events else (class_info.title if class_info else "")
        cat_icon = get_category_by_id(events[0].category_id).icon if has_events else ""

        header = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(18))
        header.add_widget(
            JpLabel(
                text=slot_label,
                bold=True,
                font_size=dp(12),
                halign="left",
                valign="middle",
            )
        )
        badge_text = f"{len(events)}件" if has_events else "募集中なし"
        header.add_widget(
            JpLabel(
                text=badge_text,
                font_size=dp(11),
                color=(0.25, 0.35, 0.5, 1),
                halign="right",
                valign="middle",
            )
        )
        self.add_widget(header)

        title_row = (
            MarqueeBox(text=f"{cat_icon} {first_title}") if (is_near and first_title) else JpLabel(
                text=f"{cat_icon} {first_title}" if first_title else "（タイトル未設定）",
                font_size=dp(13),
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(24),
            )
        )
        if isinstance(title_row, JpLabel):
            title_row.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(title_row)

        self.add_widget(AvailabilityBar(free_users))

        # 状態サブ行（授業/承認待ちなど最小限の文字）
        sub_texts: List[str] = []
        if class_info and (class_info.title or class_info.classroom):
            sub_texts.append(class_info.title or "授業")
        sub_line = JpLabel(
            text=" / ".join(sub_texts) if sub_texts else "",
            font_size=dp(11),
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None,
            height=dp(16),
            halign="left",
            valign="middle",
        )
        sub_line.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        self.add_widget(sub_line)

        # 背景・枠線
        outline = (0.30, 0.60, 1.0, 1) if is_my_free else (0.80, 0.85, 0.90, 1)
        bg = (0.95, 0.98, 1.0, 1) if is_near else ((0.95, 0.97, 1.0, 1) if has_events else (1, 1, 1, 1))
        with self.canvas.before:
            self.bg_color = Color(*bg)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
            Color(*outline)
            self.border_line = Line(rectangle=(self.x, self.y, self.width, self.height), width=1.2)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border_line.rectangle = (self.x, self.y, self.width, self.height)


# ---------- 時間割画面 ----------

class TimetableScreen(Screen):
    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo
        self.selected_day_id = None
        self.selected_slot_id = None
        self._import_thread_active = False
        self._slot_start_minutes = {
            "1": 9 * 60,
            "2": 10 * 60 + 40,
            "LUNCH": 12 * 60 + 20,
            "3": 13 * 60 + 10,
            "4": 14 * 60 + 50,
            "5": 16 * 60 + 30,
        }

        root = BoxLayout(orientation='vertical', padding=dp(4), spacing=dp(4))
        self.add_widget(root)

        action_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(4))
        self.btn_import_image = JpButton(
            text="画像から授業を取り込む",
            size_hint_x=None,
            width=dp(240),
        )
        self.btn_import_image.bind(on_press=self.open_import_popup)
        action_bar.add_widget(self.btn_import_image)
        action_bar.add_widget(Widget())
        root.add_widget(action_bar)

        scroll = ScrollView()
        root.add_widget(scroll)

        self.grid = GridLayout(
            cols=len(DAYS) + 1,
            size_hint_y=None,
            row_default_height=dp(110),
            row_force_default=True,
        )
        self.grid.bind(minimum_height=self.grid.setter('height'))
        scroll.add_widget(self.grid)

        self.build_grid()

    def open_import_popup(self, *_):
        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        instructions = JpLabel(
            text="AIに時間割画像を送信して授業コマを自動登録します。\n"
                 "※ APIキーは環境変数 DOUBAO_API_KEY でも設定できます。",
            size_hint_y=None,
            height=dp(60),
            halign="left",
            valign="middle",
        )
        instructions.bind(
            size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None))
        )
        content.add_widget(instructions)

        chooser = FileChooserListView(
            path=os.getcwd(),
            size_hint=(1, 0.55),
            filters=["*.png", "*.jpg", "*.jpeg", "*.webp"],
        )
        chooser.multiselect = False
        content.add_widget(chooser)

        selection_label = JpLabel(
            text="選択中: なし",
            size_hint_y=None,
            height=dp(24),
            halign="left",
            valign="middle",
        )
        selection_label.bind(
            size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None))
        )

        def on_selection(_instance, selection):
            if selection:
                selection_label.text = f"選択中: {os.path.basename(selection[0])}"
            else:
                selection_label.text = "選択中: なし"

        chooser.bind(selection=on_selection)
        content.add_widget(selection_label)

        api_input = JpTextInput(
            hint_text="API Key（省略時は DOUBAO_API_KEY を使用）",
            multiline=False,
            password=True,
            size_hint_y=None,
            height=dp(38),
        )
        content.add_widget(api_input)

        merge_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28), spacing=dp(4))
        merge_checkbox = CheckBox(active=False)
        merge_label = JpLabel(
            text="既存の授業に追加（未チェックは上書き）",
            halign="left",
            valign="middle",
        )
        merge_label.bind(
            size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None))
        )
        merge_box.add_widget(merge_checkbox)
        merge_box.add_widget(merge_label)
        content.add_widget(merge_box)

        status_label = JpLabel(
            text="",
            size_hint_y=None,
            height=dp(40),
            halign="left",
            valign="middle",
        )
        status_label.bind(
            size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None))
        )
        content.add_widget(status_label)

        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        run_btn = JpButton(text="解析")
        cancel_btn = JpButton(text="閉じる")
        btn_box.add_widget(run_btn)
        btn_box.add_widget(cancel_btn)
        content.add_widget(btn_box)

        popup = Popup(
            title="画像から授業を登録",
            content=content,
            size_hint=(0.9, 0.9),
        )
        popup.title_font = "JP"
        popup.title_color = (0, 0, 0, 1)
        popup.separator_color = (0.2, 0.6, 0.9, 1)

        cancel_btn.bind(on_press=lambda *_: popup.dismiss())
        run_btn.bind(
            on_press=lambda *_: self.start_ai_import(
                chooser,
                api_input,
                merge_checkbox,
                status_label,
                run_btn,
                popup,
            )
        )

        popup.open()

    def start_ai_import(
        self,
        chooser: FileChooserListView,
        api_input: JpTextInput,
        merge_checkbox: CheckBox,
        status_label: JpLabel,
        run_btn: JpButton,
        popup: Popup,
    ):
        if not self.repo.is_logged_in():
            status_label.text = "ログインしてから授業を取り込んでください。"
            return
        if self._import_thread_active:
            status_label.text = "現在解析中です。完了までお待ちください。"
            return
        if not chooser.selection:
            status_label.text = "先に画像ファイルを選択してください。"
            return

        image_path = chooser.selection[0]
        api_key = api_input.text.strip() or None
        merge = bool(merge_checkbox.active)

        status_label.text = "送信中..."
        run_btn.disabled = True
        self._import_thread_active = True

        thread = threading.Thread(
            target=self._run_ai_import,
            args=(image_path, api_key, merge, status_label, run_btn, popup),
            daemon=True,
        )
        thread.start()

    def _run_ai_import(
        self,
        image_path: str,
        api_key: Optional[str],
        merge: bool,
        status_label: JpLabel,
        run_btn: JpButton,
        popup: Popup,
    ):
        try:
            client = DoubaoVisionClient(api_key=api_key)
            busy_slots = client.recognize_timetable(image_path)
            applied = self.repo.apply_busy_slots(busy_slots, merge=merge)
            Clock.schedule_once(
                lambda *_: self._on_import_success(applied, status_label, run_btn, popup),
                0,
            )
        except (DoubaoVisionClientError, ValueError) as exc:
            Clock.schedule_once(
                lambda *_: self._on_import_failed(str(exc), status_label, run_btn),
                0,
            )
        except Exception as exc:
            Clock.schedule_once(
                lambda *_: self._on_import_failed(f"解析に失敗しました: {exc}", status_label, run_btn),
                0,
            )
        finally:
            self._import_thread_active = False

    def _on_import_success(
        self,
        applied_count: int,
        status_label: JpLabel,
        run_btn: JpButton,
        popup: Popup,
    ):
        status_label.text = f"解析成功: {applied_count}コマを登録しました。"
        run_btn.disabled = False
        self.build_grid()
        Clock.schedule_once(lambda *_: popup.dismiss(), 0.8)

    def _on_import_failed(
        self,
        message: str,
        status_label: JpLabel,
        run_btn: JpButton,
    ):
        status_label.text = message
        run_btn.disabled = False

    def _is_near_slot(self, day_id: str, slot_id: str) -> bool:
        """現在時刻から近いコマかどうかを判定（同じ曜日かつ±90分以内）。"""
        now = datetime.now()
        weekday = now.weekday()
        if weekday >= len(DAY_IDS):
            return False
        today_id = DAY_IDS[weekday]
        if day_id != today_id:
            return False
        start_min = self._slot_start_minutes.get(slot_id)
        if start_min is None:
            return False
        now_min = now.hour * 60 + now.minute
        return abs(start_min - now_min) <= 90

    def build_grid(self):
        self.grid.clear_widgets()
        self.grid.add_widget(HeaderLabel(text="", size_hint_x=None, width=dp(50)))
        for day_id, day_label in DAYS:
            self.grid.add_widget(HeaderLabel(text=day_label, bold=True))

        # 各コマ
        for slot_id, slot_label in SLOTS:
            self.grid.add_widget(HeaderLabel(text=slot_label, size_hint_x=None, width=dp(50)))

            for day_id, _ in DAYS:
                events = self.repo.get_events_for_slot(day_id, slot_id)
                card = SlotCard(
                    day_id=day_id,
                    slot_id=slot_id,
                    slot_label=slot_label,
                    events=events,
                    free_users=self.repo.get_free_user_info(day_id, slot_id, slot_id),
                    class_info=self.repo.get_class_info(day_id, slot_id),
                    is_my_free=self.repo.is_my_slot_free(day_id, slot_id),
                    is_near=self._is_near_slot(day_id, slot_id),
                )
                card.bind(on_press=self.on_slot_pressed)
                self.grid.add_widget(card)

    def on_slot_pressed(self, btn):
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
        free_users = self.repo.get_free_user_info(self.selected_day_id, self.selected_slot_id, self.selected_slot_id)
        class_info = self.repo.get_class_info(self.selected_day_id, self.selected_slot_id)
        logged_in = self.repo.is_logged_in()

        # ---- 内容領域：白地 + 縦方向 ----
        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))

        with content.canvas.before:
            Color(1, 1, 1, 1)  # 純白
            content.bg_rect = Rectangle(pos=content.pos, size=content.size)

        def _update_content_bg(instance, *args):
            content.bg_rect.pos = instance.pos
            content.bg_rect.size = instance.size

        content.bind(pos=_update_content_bg, size=_update_content_bg)

        title_lbl = JpLabel(
            text=f"{day_label} {slot_label}",
            size_hint_y=None,
            height=dp(32),
        )
        content.add_widget(title_lbl)

        content.add_widget(
            JpLabel(
                text="募集タイトルをタップすると詳細ウィンドウが開きます。",
                size_hint_y=None,
                height=dp(26),
            )
        )

        if not events:
            content.add_widget(
                JpLabel(
                    text="このコマにはまだ募集がありません。",
                    size_hint_y=None,
                    height=dp(40),
                )
            )
        else:
            sv = ScrollView(size_hint=(1, 0.55))
            box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
            box.bind(minimum_height=box.setter('height'))
            sv.add_widget(box)

            for e in events:
                cat = get_category_by_id(e.category_id)
                btn = JpButton(
                    text=f"{cat.icon} {e.title}\n参加: {e.participants_count}/{e.max_participants}",
                    size_hint_y=None,
                    height=dp(48),
                )
                btn.halign = "left"
                btn.valign = "middle"
                btn.padding = (dp(6), dp(6))

                def _update_text_size(instance, *_):
                    instance.text_size = (instance.width - dp(12), None)

                btn.bind(size=_update_text_size)
                _update_text_size(btn)
                btn.bind(on_press=lambda _btn, ev=e: self.show_event_detail_popup(ev))
                box.add_widget(btn)

            content.add_widget(sv)

        class_section = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(120), spacing=dp(4))
        class_section.add_widget(JpLabel(text="授業情報", size_hint_y=None, height=dp(20)))
        if class_info:
            detail_lines = [f"タイトル: {class_info.title or '（未設定）'}"]
            if class_info.classroom:
                detail_lines.append(f"教室: {class_info.classroom}")
            class_section.add_widget(
                JpLabel(
                    text="\n".join(detail_lines),
                    size_hint_y=None,
                    height=dp(40),
                )
            )
        else:
            class_section.add_widget(
                JpLabel(
                    text="このコマにはまだ授業情報が登録されていません。",
                    size_hint_y=None,
                    height=dp(40),
                )
            )
        if not logged_in:
            class_section.add_widget(
                JpLabel(
                    text="ログインすると授業を登録できます。",
                    size_hint_y=None,
                    height=dp(24),
                )
            )

        class_btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(6))
        btn_edit_class = JpButton(text="授業情報を編集" if is_busy else "授業を追加")
        btn_edit_class.disabled = not logged_in
        class_btn_box.add_widget(btn_edit_class)
        clear_btn = None
        if is_busy and logged_in:
            btn_clear_class = JpButton(text="授業を削除")
            class_btn_box.add_widget(btn_clear_class)
            clear_btn = btn_clear_class
        else:
            class_btn_box.add_widget(Widget())
        class_section.add_widget(class_btn_box)
        content.add_widget(class_section)

        # 募集作成
        buttons_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        btn_create = JpButton(text="募集を作成" if logged_in else "ログインして募集作成")
        btn_create.disabled = not logged_in
        btn_close = JpButton(text="閉じる")
        buttons_box.add_widget(btn_create)
        buttons_box.add_widget(btn_close)
        content.add_widget(buttons_box)

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

        # ---- ロジック----
        def on_create_pressed(_btn):
            popup.dismiss()
            self.show_create_popup()

        if logged_in:
            btn_create.bind(on_press=on_create_pressed)
        btn_close.bind(on_press=lambda *_: popup.dismiss())

        if logged_in:
            btn_edit_class.bind(
                on_press=lambda *_: self.open_class_edit_popup(
                    popup,
                    self.selected_day_id,
                    self.selected_slot_id,
                    class_info,
                )
            )

        if clear_btn:
            def on_clear_class(_btn):
                self.repo.remove_busy_slot(self.selected_day_id, self.selected_slot_id)
                popup.dismiss()
                self.build_grid()
            clear_btn.bind(on_press=on_clear_class)

        popup.open()

    def open_class_edit_popup(
        self,
        parent_popup: Popup,
        day_id: str,
        slot_id: str,
        class_info: Optional[ClassInfo],
    ):
        if not self.repo.is_logged_in():
            info = Popup(
                title="ログインが必要です",
                content=JpLabel(
                    text="授業を登録・編集するにはログインしてください。",
                    size_hint_y=None,
                    height=dp(40),
                ),
                size_hint=(0.6, 0.4),
            )
            info.open()
            return
        day_label = next(l for i, l in DAYS if i == day_id)
        slot_label = next(l for i, l in SLOTS if i == slot_id)

        content = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(4))
        content.add_widget(
            JpLabel(
                text=f"{day_label} {slot_label} の授業情報",
                size_hint_y=None,
                height=dp(30),
            )
        )

        ti_title = JpTextInput(
            text=class_info.title if class_info else "",
            hint_text="授業名",
            multiline=False,
            size_hint_y=None,
            height=dp(36),
        )
        ti_room = JpTextInput(
            text=class_info.classroom if class_info else "",
            hint_text="教室（任意）",
            multiline=False,
            size_hint_y=None,
            height=dp(36),
        )
        content.add_widget(ti_title)
        content.add_widget(ti_room)

        info_lbl = JpLabel(text="", size_hint_y=None, height=dp(24))
        content.add_widget(info_lbl)

        btn_save = JpButton(text="保存", size_hint_y=None, height=dp(38))
        btn_cancel = JpButton(text="キャンセル", size_hint_y=None, height=dp(38))
        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        btn_box.add_widget(btn_save)
        btn_box.add_widget(btn_cancel)
        content.add_widget(btn_box)

        popup = Popup(
            title="授業情報の編集",
            content=content,
            size_hint=(0.8, 0.5),
        )
        popup.title_font = "JP"
        popup.title_color = (0, 0, 0, 1)

        def on_save(_btn):
            title = ti_title.text.strip()
            classroom = ti_room.text.strip()
            self.repo.add_busy_slot(day_id, slot_id, title, classroom)
            popup.dismiss()
            parent_popup.dismiss()
            self.build_grid()
            Clock.schedule_once(lambda *_: self.show_slot_popup(), 0)

        btn_save.bind(on_press=on_save)
        btn_cancel.bind(on_press=lambda *_: popup.dismiss())
        popup.open()

    def show_event_detail_popup(self, event: Event):
        cat = get_category_by_id(event.category_id)
        day_label = next(l for i, l in DAYS if i == event.day_id)
        slot_start = next(l for i, l in SLOTS if i == event.slot_start_id)
        slot_end = next(l for i, l in SLOTS if i == event.slot_end_id)
        is_owner = event.owner_user_id == self.repo.current_user_id

        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        lbl_title = JpLabel(
            text=f"{cat.icon} {event.title}",
                size_hint_y=None,
                height=dp(36),
            bold=True,
            )
        content.add_widget(lbl_title)

        meta = JpLabel(
            text=f"カテゴリ: {cat.label}\n時間: {day_label} {slot_start}〜{slot_end}",
            size_hint_y=None,
            height=dp(48),
        )
        content.add_widget(meta)

        participants_lbl = JpLabel(
            text=f"参加状況: {event.participants_count}/{event.max_participants}",
            size_hint_y=None,
            height=dp(28),
        )
        content.add_widget(participants_lbl)

        participants_list_lbl = JpLabel(
            text="",
            size_hint_y=None,
            height=dp(40),
        )
        content.add_widget(participants_list_lbl)

        status_lbl = JpLabel(
            text="",
            size_hint_y=None,
            height=dp(40),
        )
        content.add_widget(status_lbl)

        btn_join = JpButton(text="参加申請を送る", size_hint_y=None, height=dp(40))
        btn_close = JpButton(text="閉じる", size_hint_y=None, height=dp(40))

        btn_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(8))
        btn_box.add_widget(btn_join)
        btn_box.add_widget(btn_close)
        content.add_widget(btn_box)

        if is_owner:
            btn_join.disabled = True
            btn_join.text = "主催者"
        elif not self.repo.is_logged_in():
            btn_join.disabled = True
            btn_join.text = "ログインしてください"
            status_lbl.text = "ログインすると参加申請できます。"

        pending_section = None
        pending_container = None
        if is_owner:
            pending_section = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4), padding=(0, dp(4)))
            pending_section.bind(minimum_height=pending_section.setter("height"))
            pending_section.add_widget(JpLabel(text="承認待ち", size_hint_y=None, height=dp(24)))
            pending_container = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
            pending_container.bind(minimum_height=pending_container.setter("height"))
            pending_section.add_widget(pending_container)
            content.add_widget(pending_section)

        popup = Popup(
            title="募集詳細",
            content=content,
            size_hint=(0.85, 0.75),
        )
        popup.title_font = "JP"
        popup.title_color = (0, 0, 0, 1)

        def refresh_participants():
            names = [
                self.repo.get_user_display_name(uid)
                for uid in sorted(self.repo.get_event_participants(event.id))
            ]
            participants_lbl.text = f"参加状況: {event.participants_count}/{event.max_participants}"
            participants_list_lbl.text = "、".join(names) if names else "（参加者なし）"

        def refresh_pending_list():
            if not pending_container:
                return
            pending_container.clear_widgets()
            pending_users = sorted(self.repo.get_event_pending(event.id))
            if not pending_users:
                pending_container.add_widget(
                    JpLabel(text="承認待ちはありません。", size_hint_y=None, height=dp(24))
                )
                return
            for user_id in pending_users:
                row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(34), spacing=dp(4))
                row.add_widget(JpLabel(text=self.repo.get_user_display_name(user_id), halign="left", valign="middle"))
                btn_ok = JpButton(text="承認", size_hint_x=None, width=dp(70), height=dp(30))
                btn_ng = JpButton(text="却下", size_hint_x=None, width=dp(70), height=dp(30))

                def on_ok(_btn, target=user_id):
                    result = self.repo.approve_event_application(event.id, target)
                    if result == "ok":
                        status_lbl.text = f"{self.repo.get_user_display_name(target)} を承認しました。"
                        refresh_participants()
                        refresh_pending_list()
                        self.build_grid()
                    elif result == "full":
                        status_lbl.text = "満席のため承認できません。"
                    else:
                        status_lbl.text = "承認に失敗しました。"

                def on_ng(_btn, target=user_id):
                    result = self.repo.reject_event_application(event.id, target)
                    if result == "ok":
                        status_lbl.text = f"{self.repo.get_user_display_name(target)} を却下しました。"
                        refresh_pending_list()
                        self.build_grid()
                    else:
                        status_lbl.text = "却下に失敗しました。"

                btn_ok.bind(on_press=on_ok)
                btn_ng.bind(on_press=on_ng)
                row.add_widget(btn_ok)
                row.add_widget(btn_ng)
                pending_container.add_widget(row)

        def on_join(_btn):
            status = self.repo.join_event(event.id)
            if status == "pending":
                status_lbl.text = "参加申請を送信しました。承認をお待ちください。"
                refresh_pending_list()
            elif status == "duplicate":
                status_lbl.text = "すでに参加しています。"
            elif status == "full":
                status_lbl.text = "この募集は満席です。"
            elif status == "login_required":
                status_lbl.text = "ログインすると参加申請できます。"
            elif status == "owner":
                status_lbl.text = "主催者は申請できません。"
            else:
                status_lbl.text = "参加申請に失敗しました。"

        btn_join.bind(on_press=on_join)
        btn_close.bind(on_press=lambda *_: popup.dismiss())
        refresh_participants()
        refresh_pending_list()
        popup.open()


    def show_create_popup(self):
        """募集"""
        if not self.selected_day_id or not self.selected_slot_id:
            return
        if not self.repo.is_logged_in():
            info = Popup(
                title="ログインが必要です",
                content=JpLabel(
                    text="募集を作成するにはログインしてください。",
                    size_hint_y=None,
                    height=dp(40),
                ),
                size_hint=(0.6, 0.4),
            )
            info.open()
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

        cat_buttons: List[CategoryToggleButton] = []

        def on_cat_btn_press(btn):
            for other in cat_buttons:
                if other is not btn:
                    other.state = "normal"
            btn.state = "down"
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
            cat_buttons.append(b)
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
            update_free_label()

        def on_end_btn_press(btn):
            state["slot_end_id"] = btn.slot_id
            update_free_label()

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
        lbl_free = JpLabel(
            text="",
            size_hint_y=None,
            height=dp(24),
        )
        content.add_widget(lbl_free)

        def update_free_label(*_):
            free_count = self.repo.get_free_user_info(
                state["day_id"], state["slot_start_id"], state["slot_end_id"]
            )
            lbl_free.text = f"この時間帯の空きコマユーザー（推定）: {free_count}人"

        update_free_label()

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
    """ユーザー登録 / ログイン"""

    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo

        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8))
        self.add_widget(root)

        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(8))
        self.lbl_current = JpLabel(text="", size_hint_y=None, height=dp(40), halign="left", valign="middle")
        self.lbl_current.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
        header.add_widget(self.lbl_current)
        self.btn_logout = JpButton(text="ログアウト", size_hint_x=None, width=dp(100))
        self.btn_logout.bind(on_press=self.on_logout)
        header.add_widget(self.btn_logout)
        root.add_widget(header)

        self.lbl_pending = JpLabel(text="", size_hint_y=None, height=dp(24))
        root.add_widget(self.lbl_pending)

        # Login section
        root.add_widget(JpLabel(text="ログイン", size_hint_y=None, height=dp(24)))
        login_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4), padding=(0, 0, 0, dp(4)))
        login_box.bind(minimum_height=login_box.setter("height"))
        self.ti_login_user = JpTextInput(hint_text="ユーザー名", multiline=False, size_hint_y=None, height=dp(36))
        self.ti_login_pass = JpTextInput(hint_text="パスワード", multiline=False, password=True, size_hint_y=None, height=dp(36))
        btn_login = JpButton(text="ログイン", size_hint_y=None, height=dp(36))
        btn_login.bind(on_press=self.on_login)
        self.lbl_login_info = JpLabel(text="", size_hint_y=None, height=dp(24))
        login_box.add_widget(self.ti_login_user)
        login_box.add_widget(self.ti_login_pass)
        login_box.add_widget(btn_login)
        login_box.add_widget(self.lbl_login_info)
        root.add_widget(login_box)

        # Register section
        root.add_widget(JpLabel(text="新規登録", size_hint_y=None, height=dp(24)))
        register_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(4))
        register_box.bind(minimum_height=register_box.setter("height"))
        self.ti_reg_display = JpTextInput(hint_text="表示名（任意）", multiline=False, size_hint_y=None, height=dp(36))
        self.ti_reg_user = JpTextInput(hint_text="ユーザー名", multiline=False, size_hint_y=None, height=dp(36))
        self.ti_reg_pass = JpTextInput(hint_text="パスワード", multiline=False, password=True, size_hint_y=None, height=dp(36))
        btn_register = JpButton(text="登録する", size_hint_y=None, height=dp(36))
        btn_register.bind(on_press=self.on_register)
        self.lbl_register_info = JpLabel(text="", size_hint_y=None, height=dp(24))
        register_box.add_widget(self.ti_reg_display)
        register_box.add_widget(self.ti_reg_user)
        register_box.add_widget(self.ti_reg_pass)
        register_box.add_widget(btn_register)
        register_box.add_widget(self.lbl_register_info)
        root.add_widget(register_box)

        self.refresh_state()

    def refresh_state(self):
        if self.repo.is_logged_in():
            self.lbl_current.text = f"現在のユーザー: {self.repo.user_name}"
        else:
            self.lbl_current.text = "現在のユーザー: （未ログイン）"
        self.btn_logout.disabled = not self.repo.is_logged_in()
        if self.repo.is_logged_in():
            pendings = self.repo.get_owner_pending_events(self.repo.current_user_id)
        else:
            pendings = []
        if pendings:
            self.lbl_pending.text = f"承認待ちの募集: {len(pendings)}件"
        elif self.repo.is_logged_in():
            self.lbl_pending.text = "承認待ちの募集はありません。"
        else:
            self.lbl_pending.text = "ログインすると承認待ちの募集を確認できます。"

    def on_login(self, *_):
        username = self.ti_login_user.text.strip()
        password = self.ti_login_pass.text
        ok, msg = self.repo.login_user(username, password)
        self.lbl_login_info.text = msg
        if ok:
            self.ti_login_pass.text = ""
            self.refresh_state()
            self.notify_user_change()
            self.show_pending_popup()

    def on_logout(self, *_):
        self.repo.logout_user()
        self.refresh_state()
        self.notify_user_change()

    def on_register(self, *_):
        username = self.ti_reg_user.text.strip()
        password = self.ti_reg_pass.text
        display_name = self.ti_reg_display.text.strip()
        ok, msg = self.repo.register_user(username, password, display_name)
        self.lbl_register_info.text = msg
        if ok:
            self.ti_reg_pass.text = ""
            self.ti_reg_user.text = ""
            self.ti_reg_display.text = ""
            self.refresh_state()
            self.notify_user_change()
            self.show_pending_popup()

    def notify_user_change(self):
        if not self.manager:
            return
        try:
            self.manager.get_screen("timetable").build_grid()
        except Exception:
            pass
        try:
            self.manager.get_screen("search").refresh_results()
        except Exception:
            pass

    def show_pending_popup(self):
        if not self.repo.is_logged_in():
            return
        pendings = self.repo.get_owner_pending_events(self.repo.current_user_id)
        if not pendings:
            return
        box = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))
        box.add_widget(JpLabel(text="承認待ちの募集があります。", size_hint_y=None, height=dp(30)))
        for ev in pendings[:5]:
            box.add_widget(
                JpLabel(
                    text=f"{get_category_by_id(ev.category_id).icon} {ev.title} ({ev.participants_count}/{ev.max_participants})",
                    size_hint_y=None,
                    height=dp(24),
                )
            )
        if len(pendings) > 5:
            box.add_widget(JpLabel(text=f"…ほか {len(pendings)-5} 件", size_hint_y=None, height=dp(24)))
        btn = JpButton(text="OK", size_hint_y=None, height=dp(36))
        popup = Popup(title="承認待ち", content=box, size_hint=(0.7, 0.5))
        btn.bind(on_press=lambda *_: popup.dismiss())
        box.add_widget(btn)
        popup.open()

# ---------- Root & App ----------

class RootWidget(BoxLayout):
    def __init__(self, repo: ComaLinkRepository, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        self.repo = repo

        # 上部タブバー
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

        if self.repo.is_logged_in():
            self.switch_to("timetable")
        else:
            self.switch_to("user")

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
