package com.example.coma_link.data.model

enum class EventCategory(val id: String, val icon: String, val label: String) {
    Meal("meal", "🍚", "食事"),
    Study("study", "📚", "勉強"),
    Work("work", "💻", "作業"),
    Play("play", "🎮", "遊び"),
    Chat("chat", "🗣", "雑談");
}

data class Event(
    val id: String,
    val title: String,
    val categoryId: String,
    val dayId: String,
    val slotStartId: String,
    val slotEndId: String,
    val ownerUserId: String,
    val participantsCount: Int,
    val maxParticipants: Int,
)

data class ClassInfo(
    val dayId: String,
    val slotId: String,
    val title: String = "",
    val classroom: String = "",
)

data class TimeSlotSummary(
    val dayId: String,
    val slotId: String,
    val eventsCount: Int,
    val categories: Set<String>,
)

const val DAY_MON = "MON"
const val DAY_TUE = "TUE"
const val DAY_WED = "WED"
const val DAY_THU = "THU"
const val DAY_FRI = "FRI"

val DAYS: List<Pair<String, String>> = listOf(
    DAY_MON to "月",
    DAY_TUE to "火",
    DAY_WED to "水",
    DAY_THU to "木",
    DAY_FRI to "金",
)

val SLOTS: List<Pair<String, String>> = listOf(
    "1" to "1限",
    "2" to "2限",
    "LUNCH" to "昼休み",
    "3" to "3限",
    "4" to "4限",
    "5" to "5限",
)

val SLOT_IDS: List<String> = SLOTS.map { it.first }

fun slotLabel(slotId: String): String = SLOTS.firstOrNull { it.first == slotId }?.second ?: slotId
fun dayLabel(dayId: String): String = DAYS.firstOrNull { it.first == dayId }?.second ?: dayId

