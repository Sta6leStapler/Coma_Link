package com.example.coma_link.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.coma_link.data.ComaRepository
import com.example.coma_link.data.model.DAYS
import com.example.coma_link.data.model.Event
import com.example.coma_link.data.model.EventCategory
import com.example.coma_link.data.model.SLOT_IDS
import com.example.coma_link.data.model.SLOTS
import com.example.coma_link.data.model.dayLabel
import com.example.coma_link.data.model.slotLabel

@Composable
fun SearchScreen(repo: ComaRepository, tick: Int, onChanged: () -> Unit) {
    val selectedCats = remember { mutableStateOf(setOf<String>()) }
    val selectedDays = remember { mutableStateOf(setOf<String>()) }
    val selectedSlots = remember { mutableStateOf(setOf<String>()) }
    val onlyFree = remember { mutableStateOf(false) }
    val results = remember(tick, selectedCats.value, selectedDays.value, selectedSlots.value, onlyFree.value) {
        repo.searchEvents(selectedCats.value, selectedDays.value, selectedSlots.value, onlyFree.value)
    }

    Column(
        modifier = Modifier.padding(8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Text(text = "募集検索", fontWeight = FontWeight.Bold)

        Text(text = "カテゴリ")
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            EventCategory.entries.forEach { cat ->
                val selected = selectedCats.value.contains(cat.id)
                OutlinedButton(onClick = {
                    selectedCats.value = if (selected) selectedCats.value - cat.id else selectedCats.value + cat.id
                }) { Text("${cat.icon} ${cat.label}") }
            }
        }

        Text(text = "曜日")
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            DAYS.forEach { (id, label) ->
                val selected = selectedDays.value.contains(id)
                OutlinedButton(onClick = {
                    selectedDays.value = if (selected) selectedDays.value - id else selectedDays.value + id
                }) { Text(label) }
            }
        }

        Text(text = "コマ / 昼休み")
        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            SLOTS.forEach { (id, label) ->
                val selected = selectedSlots.value.contains(id)
                OutlinedButton(onClick = {
                    selectedSlots.value = if (selected) selectedSlots.value - id else selectedSlots.value + id
                }) { Text(label) }
            }
        }

        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Checkbox(checked = onlyFree.value, onCheckedChange = { onlyFree.value = it })
            Text(text = "自分の空きコマのみ表示")
        }

        Text(text = "結果 (${results.size} 件)")
        if (results.isEmpty()) {
            Text(text = "該当なし")
        } else {
            results.forEach { ev ->
                SearchItem(ev, repo)
            }
        }
    }
}

@Composable
private fun SearchItem(ev: Event, repo: ComaRepository) {
    val cat = EventCategory.entries.firstOrNull { it.id == ev.categoryId }
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = CardDefaults.cardColors().containerColor)
    ) {
        Column(modifier = Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(text = "${cat?.icon ?: ""} ${ev.title}", fontWeight = FontWeight.Medium)
            Text(text = "${dayLabel(ev.dayId)} ${slotLabel(ev.slotStartId)}〜${slotLabel(ev.slotEndId)}")
            Text(text = "参加 ${ev.participantsCount}/${ev.maxParticipants}")
        }
    }
}

