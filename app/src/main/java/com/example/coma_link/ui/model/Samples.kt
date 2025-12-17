package com.example.coma_link.ui.model

fun sampleEvents(): List<Event> = listOf(
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
    Event(
        id = "3",
        title = "火曜ゲームタイム",
        categoryId = EventCategory.Play.id,
        dayId = "TUE",
        slotStartId = "4",
        slotEndId = "5",
        ownerUserId = "user_c",
        participantsCount = 4,
        maxParticipants = 8,
    )
)

