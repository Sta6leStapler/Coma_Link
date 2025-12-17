package com.example.coma_link.ui.model

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

enum class EventCategory(val id: String, val icon: String, val label: String) {
    Meal("meal", "🍚", "食事"),
    Study("study", "📚", "勉強"),
    Work("work", "💻", "作業"),
    Play("play", "🎮", "遊び"),
    Chat("chat", "🗣", "雑談");
}

enum class TimeTableDay(val id: String, val label: String) {
    MON("MON", "月"),
    TUE("TUE", "火"),
    WED("WED", "水"),
    THU("THU", "木"),
    FRI("FRI", "金"),
}

val DAYS: List<Pair<String, String>> = TimeTableDay.entries.map { it.id to it.label }

val SLOTS: List<Pair<String, String>> = listOf(
    "1" to "1限",
    "2" to "2限",
    "LUNCH" to "昼休み",
    "3" to "3限",
    "4" to "4限",
    "5" to "5限",
)

val SLOT_IDS = SLOTS.map { it.first }

fun dayLabel(dayId: String): String = DAYS.firstOrNull { it.first == dayId }?.second ?: dayId
fun slotLabel(slotId: String): String = SLOTS.firstOrNull { it.first == slotId }?.second ?: slotId

