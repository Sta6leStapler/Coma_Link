package com.example.coma_link.data

import com.example.coma_link.data.model.ClassInfo
import com.example.coma_link.data.model.DAYS
import com.example.coma_link.data.model.Event
import com.example.coma_link.data.model.EventCategory
import com.example.coma_link.data.model.SLOT_IDS
import com.example.coma_link.data.model.SLOTS
import com.example.coma_link.data.model.TimeSlotSummary
import kotlin.math.max

/**
 * main4.py のロジックを簡易移植したインメモリリポジトリ。
 * 永続化は行わず、UI 開発を優先。
 */
class ComaRepository(
    currentUserId: String? = null
): UserRepository {

    private var _currentUserId: String? = currentUserId
    val currentUserId: String? get() = _currentUserId
    val isLoggedIn: Boolean get() = _currentUserId != null

    // ユーザー: username -> password/plain と表示名
    private val users: MutableMap<String, Pair<String, String>> = mutableMapOf(
        "user_a" to ("pass_a" to "ユーザーA"),
        "user_b" to ("pass_b" to "ユーザーB"),
    )

    private val events: MutableList<Event> = mutableListOf(
        Event(
            id = "1",
            title = "水曜ランチ会",
            categoryId = EventCategory.Meal.id,
            dayId = "WED",
            slotStartId = "LUNCH",
            slotEndId = "LUNCH",
            ownerUserId = "user_a",
            participantsCount = 3,
            maxParticipants = 5,
        ),
        Event(
            id = "2",
            title = "金曜3-4限 自習会",
            categoryId = EventCategory.Study.id,
            dayId = "FRI",
            slotStartId = "3",
            slotEndId = "4",
            ownerUserId = "user_b",
            participantsCount = 2,
            maxParticipants = 6,
        ),
    )

    private val eventParticipants: MutableMap<String, MutableSet<String>> = mutableMapOf(
        "1" to mutableSetOf("user_a", "user_x", "user_y"),
        "2" to mutableSetOf("user_b", "user_c"),
    )
    private val eventPending: MutableMap<String, MutableSet<String>> = mutableMapOf(
        "2" to mutableSetOf("user_a")
    )

    private val classScheduleByUser: MutableMap<String, MutableMap<Pair<String, String>, ClassInfo>> =
        mutableMapOf()

    // ---------------- 認証 ----------------
    fun registerUser(username: String, password: String, displayName: String): Result<String> {
        val u = username.trim()
        val p = password.trim()
        if (u.isEmpty() || p.isEmpty()) return Result.failure(IllegalArgumentException("ユーザー名とパスワードを入力してください"))
        if (users.containsKey(u)) return Result.failure(IllegalStateException("このユーザー名は既に存在します"))
        users[u] = p to displayName.ifBlank { u }
        _currentUserId = u
        return Result.success("登録しました")
    }

    fun login(username: String, password: String): Result<String> {
        val info = users[username.trim()] ?: return Result.failure(IllegalArgumentException("ユーザー名またはパスワードが違います"))
        if (info.first != password.trim()) return Result.failure(IllegalArgumentException("ユーザー名またはパスワードが違います"))
        _currentUserId = username.trim()
        return Result.success("ログインしました")
    }

    fun logout() {
        _currentUserId = null
    }

    fun currentDisplayName(): String =
        _currentUserId?.let { users[it]?.second } ?: "未ログイン"

    // ---------------- ユーザー取得 (UserRepository) ----------------
    override suspend fun getUser(): com.example.coma_link.data.model.User {
        val uid = _currentUserId ?: "guest"
        return com.example.coma_link.data.model.User(
            id = uid,
            name = users[uid]?.second ?: "ゲスト",
            email = "$uid@example.com",
            avatarUrl = null,
            updatedAt = null,
        )
    }

    // ---------------- イベント ----------------
    fun getEventsForSlot(dayId: String, slotId: String): List<Event> =
        events.filter { it.dayId == dayId && slotRangeOverlap(it.slotStartId, it.slotEndId, slotId) }

    fun getEventById(id: String): Event? = events.firstOrNull { it.id == id }

    fun createEvent(
        categoryId: String,
        dayId: String,
        slotStartId: String,
        slotEndId: String,
        title: String,
        maxParticipants: Int,
    ): Result<Event> {
        val uid = _currentUserId ?: return Result.failure(IllegalStateException("login_required"))
        val newId = (events.size + 1).toString()
        val e = Event(
            id = newId,
            title = title.ifBlank { "未設定" },
            categoryId = categoryId,
            dayId = dayId,
            slotStartId = slotStartId,
            slotEndId = slotEndId,
            ownerUserId = uid,
            participantsCount = 1,
            maxParticipants = maxParticipants,
        )
        events.add(e)
        eventParticipants[newId] = mutableSetOf(uid)
        eventPending[newId] = mutableSetOf()
        return Result.success(e)
    }

    fun joinEvent(eventId: String): String {
        val uid = _currentUserId ?: return "login_required"
        val ev = getEventById(eventId) ?: return "not_found"
        if (ev.ownerUserId == uid) return "owner"
        val participants = eventParticipants.getOrPut(eventId) { mutableSetOf() }
        val pending = eventPending.getOrPut(eventId) { mutableSetOf() }
        if (participants.size >= ev.maxParticipants) return "full"
        pending.add(uid)
        return "pending"
    }

    fun approve(eventId: String, targetUser: String): String {
        val uid = _currentUserId ?: return "login_required"
        val ev = getEventById(eventId) ?: return "not_found"
        if (ev.ownerUserId != uid) return "forbidden"
        val pending = eventPending.getOrPut(eventId) { mutableSetOf() }
        if (!pending.contains(targetUser)) return "missing"
        val participants = eventParticipants.getOrPut(eventId) { mutableSetOf() }
        if (participants.size >= ev.maxParticipants) return "full"
        pending.remove(targetUser)
        participants.add(targetUser)
        updateParticipantsCount(ev.id, participants.size)
        return "ok"
    }

    fun reject(eventId: String, targetUser: String): String {
        val uid = _currentUserId ?: return "login_required"
        val ev = getEventById(eventId) ?: return "not_found"
        if (ev.ownerUserId != uid) return "forbidden"
        val pending = eventPending.getOrPut(eventId) { mutableSetOf() }
        if (!pending.remove(targetUser)) return "missing"
        return "ok"
    }

    private fun updateParticipantsCount(eventId: String, count: Int) {
        val idx = events.indexOfFirst { it.id == eventId }
        if (idx >= 0) {
            val ev = events[idx]
            events[idx] = ev.copy(participantsCount = max(count, ev.participantsCount))
        }
    }

    fun getParticipants(eventId: String): List<String> =
        eventParticipants[eventId]?.toList().orEmpty()

    fun getPending(eventId: String): List<String> =
        eventPending[eventId]?.toList().orEmpty()

    fun getOwnerPendingEvents(ownerId: String): List<Event> =
        events.filter { it.ownerUserId == ownerId && getPending(it.id).isNotEmpty() }

    // ---------------- 授業（busy slots） ----------------
    fun getClassInfo(dayId: String, slotId: String): ClassInfo? =
        classScheduleByUser[_currentUserId]?.get(dayId to slotId)

    fun addBusySlot(dayId: String, slotId: String, title: String, classroom: String) {
        val uid = _currentUserId ?: throw IllegalStateException("login_required")
        val schedule = classScheduleByUser.getOrPut(uid) { mutableMapOf() }
        schedule[dayId to slotId] = ClassInfo(dayId, slotId, title.trim(), classroom.trim())
    }

    fun removeBusySlot(dayId: String, slotId: String) {
        val uid = _currentUserId ?: throw IllegalStateException("login_required")
        classScheduleByUser[uid]?.remove(dayId to slotId)
    }

    fun isMySlotFree(dayId: String, slotId: String): Boolean =
        classScheduleByUser[_currentUserId]?.containsKey(dayId to slotId) != true

    // ---------------- 検索 ----------------
    fun searchEvents(
        categoryIds: Set<String>,
        dayIds: Set<String>,
        slotIds: Set<String>,
        onlyMyFree: Boolean,
    ): List<Event> {
        return events.filter { e ->
            (categoryIds.isEmpty() || categoryIds.contains(e.categoryId)) &&
                (dayIds.isEmpty() || dayIds.contains(e.dayId)) &&
                (slotIds.isEmpty() || slotIds.any { sid -> slotRangeOverlap(e.slotStartId, e.slotEndId, sid) }) &&
                (!onlyMyFree || isMyEventFree(e))
        }
    }

    private fun isMyEventFree(event: Event): Boolean {
        val schedule = classScheduleByUser[_currentUserId] ?: return true
        val range = slotRange(event.slotStartId, event.slotEndId)
        return range.none { slot -> schedule.containsKey(event.dayId to slot) }
    }

    private fun slotRange(startId: String, endId: String): List<String> {
        val s = SLOT_IDS.indexOf(startId)
        val e = SLOT_IDS.indexOf(endId)
        if (s == -1 || e == -1) return emptyList()
        val (a, b) = if (s <= e) s to e else e to s
        return SLOT_IDS.subList(a, b + 1)
    }

    fun getTimeTableSummaries(): List<TimeSlotSummary> {
        val res = mutableListOf<TimeSlotSummary>()
        for ((dayId, _) in DAYS) {
            for ((slotId, _) in SLOTS) {
                val evs = events.filter { it.dayId == dayId && slotRangeOverlap(it.slotStartId, it.slotEndId, slotId) }
                res += TimeSlotSummary(
                    dayId = dayId,
                    slotId = slotId,
                    eventsCount = evs.size,
                    categories = evs.map { it.categoryId }.toSet()
                )
            }
        }
        return res
    }

    companion object {
        fun slotRangeOverlap(startId: String, endId: String, targetId: String): Boolean {
            val s = SLOT_IDS.indexOf(startId)
            val e = SLOT_IDS.indexOf(endId)
            val t = SLOT_IDS.indexOf(targetId)
            if (s == -1 || e == -1 || t == -1) return false
            val (a, b) = if (s <= e) s to e else e to s
            return t in a..b
        }
    }
}

