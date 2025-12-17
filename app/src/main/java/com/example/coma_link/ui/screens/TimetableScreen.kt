package com.example.coma_link.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.coma_link.data.ComaRepository
import com.example.coma_link.data.model.ClassInfo
import com.example.coma_link.data.model.DAYS
import com.example.coma_link.data.model.Event
import com.example.coma_link.data.model.EventCategory
import com.example.coma_link.data.model.SLOT_IDS
import com.example.coma_link.data.model.SLOTS
import com.example.coma_link.data.model.dayLabel
import com.example.coma_link.data.model.slotLabel

@Composable
fun TimetableScreen(repo: ComaRepository, tick: Int, onChanged: () -> Unit) {
    val openState = remember { mutableStateOf<Pair<String, String>?>(null) }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Card(
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
        ) {
            Column(
                modifier = Modifier.padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(text = "時間割", style = MaterialTheme.typography.titleMedium)
                TimeTableHeader()
                SLOTS.forEach { (slotId, label) ->
                    TimeTableRow(
                        repo = repo,
                        slotId = slotId,
                        slotLabel = label,
                        onOpen = { day -> openState.value = day to slotId }
                    )
                }
            }
        }
    }

    openState.value?.let { (dayId, slotId) ->
        SlotDialog(repo = repo, dayId = dayId, slotId = slotId, onDismiss = {
            openState.value = null
            onChanged()
        })
    }
}

@Composable
private fun TimeTableHeader() {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(text = "時限", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
        DAYS.forEach { (id, label) ->
            Text(
                text = label,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun TimeTableRow(
    repo: ComaRepository,
    slotId: String,
    slotLabel: String,
    onOpen: (String) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            text = slotLabel,
            modifier = Modifier
                .weight(1f)
                .padding(end = 4.dp),
            maxLines = 1,
        )
        DAYS.forEach { (dayId, _) ->
            val slotEvents = repo.getEventsForSlot(dayId, slotId)
            SlotCell(
                events = slotEvents,
                classInfo = repo.getClassInfo(dayId, slotId),
                isMyFree = repo.isMySlotFree(dayId, slotId),
                modifier = Modifier
                    .weight(1f)
                    .clickable { onOpen(dayId) }
            )
        }
    }
}

@Composable
private fun SlotCell(
    events: List<Event>,
    classInfo: ClassInfo?,
    isMyFree: Boolean,
    modifier: Modifier = Modifier
) {
    val hasEvents = events.isNotEmpty()
    val first = events.firstOrNull()
    Box(
        modifier = modifier
            .padding(horizontal = 4.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(
                when {
                    !isMyFree -> MaterialTheme.colorScheme.error.copy(alpha = 0.08f)
                    hasEvents -> MaterialTheme.colorScheme.primary.copy(alpha = 0.12f)
                    else -> MaterialTheme.colorScheme.surface
                }
            )
            .padding(8.dp)
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            val title = when {
                hasEvents -> "${first?.category()?.icon ?: ""} ${first?.title ?: "未設定"}"
                classInfo != null -> classInfo.title.ifBlank { "授業" }
                else -> "空き"
            }
            Text(
                text = title,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            if (hasEvents) {
                Text(
                    text = "${events.size} 件の募集",
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            } else if (classInfo != null && classInfo.classroom.isNotBlank()) {
                Text(
                    text = classInfo.classroom,
                    fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun SlotDialog(repo: ComaRepository, dayId: String, slotId: String, onDismiss: () -> Unit) {
    val events = repo.getEventsForSlot(dayId, slotId)
    val classInfo = repo.getClassInfo(dayId, slotId)
    val dayLabel = dayLabel(dayId)
    val slotLabel = slotLabel(slotId)
    val isLoggedIn = repo.isLoggedIn

    val showCreate = remember { mutableStateOf(false) }
    val showClassEdit = remember { mutableStateOf(false) }
    val selectedEvent = remember { mutableStateOf<Event?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        confirmButton = {},
        title = { Text(text = "$dayLabel $slotLabel") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (events.isEmpty()) {
                    Text(text = "このコマには募集がありません。")
                } else {
                    events.forEach { ev ->
                        EventRow(ev) { selectedEvent.value = ev }
                    }
                }
                HorizontalDivider()
                Text(text = "授業")
                if (classInfo != null) {
                    Text(text = "${classInfo.title.ifBlank { "授業" }} ${if (classInfo.classroom.isNotBlank()) "(${classInfo.classroom})" else ""}")
                } else {
                    Text(text = "未登録")
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        if (isLoggedIn) showCreate.value = true else selectedEvent.value = null
                    }) { Text(text = if (isLoggedIn) "募集を作成" else "ログインしてください") }
                    OutlinedButton(onClick = {
                        if (isLoggedIn) showClassEdit.value = true
                    }, enabled = isLoggedIn) { Text(text = "授業を編集") }
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(text = "閉じる") }
        }
    )

    if (showCreate.value) {
        CreateEventDialog(
            repo = repo,
            dayId = dayId,
            slotId = slotId,
            onCreated = {
                showCreate.value = false
                onDismiss()
            },
            onCancel = { showCreate.value = false }
        )
    }

    if (showClassEdit.value) {
        ClassEditDialog(
            repo = repo,
            dayId = dayId,
            slotId = slotId,
            classInfo = classInfo,
            onSaved = {
                showClassEdit.value = false
                onDismiss()
            },
            onCancel = { showClassEdit.value = false }
        )
    }

    selectedEvent.value?.let { ev ->
        EventDetailDialog(
            repo = repo,
            event = ev,
            onChanged = {
                selectedEvent.value = null
                onDismiss()
            },
            onCancel = { selectedEvent.value = null }
        )
    }
}

@Composable
private fun EventRow(ev: Event, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
    ) {
        Column(modifier = Modifier.padding(8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            val cat = ev.category()
            Text(text = "${cat?.icon ?: ""} ${ev.title}", fontWeight = FontWeight.Medium)
            Text(
                text = "参加 ${ev.participantsCount}/${ev.maxParticipants}",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onPrimaryContainer
            )
        }
    }
}

@Composable
private fun EventDetailDialog(
    repo: ComaRepository,
    event: Event,
    onChanged: () -> Unit,
    onCancel: () -> Unit
) {
    val isOwner = repo.currentUserId == event.ownerUserId
    val participants = repo.getParticipants(event.id)
    val pending = repo.getPending(event.id)
    val msg = remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onCancel,
        confirmButton = {},
        title = { Text(text = "募集詳細") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                val cat = event.category()
                Text(text = "${cat?.icon ?: ""} ${event.title}", fontWeight = FontWeight.Bold)
                Text(text = "参加 ${event.participantsCount}/${event.maxParticipants}")
                Text(text = "参加者: ${participants.joinToString("、").ifBlank { "なし" }}")
                if (isOwner) {
                    Text(text = "承認待ち: ${pending.joinToString("、").ifBlank { "なし" }}")
                }
                if (msg.value.isNotBlank()) {
                    Text(text = msg.value, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (isOwner && pending.isNotEmpty()) {
                    Button(onClick = {
                        val target = pending.first()
                        when (repo.approve(event.id, target)) {
                            "ok" -> msg.value = "承認しました"
                            "full" -> msg.value = "満席です"
                            else -> msg.value = "承認に失敗"
                        }
                        onChanged()
                    }) { Text("1件承認") }
                    OutlinedButton(onClick = {
                        val target = pending.first()
                        repo.reject(event.id, target)
                        msg.value = "却下しました"
                        onChanged()
                    }) { Text("1件却下") }
                } else if (!isOwner) {
                    Button(onClick = {
                        msg.value = when (repo.joinEvent(event.id)) {
                            "pending" -> "参加申請を送りました"
                            "full" -> "満席です"
                            "owner" -> "主催者です"
                            "login_required" -> "ログインしてください"
                            else -> "申請失敗"
                        }
                        onChanged()
                    }) { Text("参加申請") }
                }
                TextButton(onClick = onCancel) { Text("閉じる") }
            }
        }
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CreateEventDialog(
    repo: ComaRepository,
    dayId: String,
    slotId: String,
    onCreated: () -> Unit,
    onCancel: () -> Unit,
) {
    val title = remember { mutableStateOf("") }
    val max = remember { mutableStateOf("4") }
    val cat = remember { mutableStateOf(EventCategory.Meal) }
    val endSlot = remember { mutableStateOf(slotId) }
    val msg = remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onCancel,
        confirmButton = {},
        title = { Text(text = "募集を作成") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(text = "カテゴリ")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    EventCategory.entries.forEach { c ->
                        OutlinedButton(
                            onClick = { cat.value = c },
                            border = ButtonDefaults.outlinedButtonBorder(enabled = true).takeIf { cat.value == c },
                        ) { Text(text = "${c.icon} ${c.label}") }
                    }
                }
                OutlinedTextField(
                    value = title.value,
                    onValueChange = { title.value = it },
                    label = { Text("タイトル") },
                    singleLine = true
                )
                OutlinedTextField(
                    value = max.value,
                    onValueChange = { max.value = it.filter { ch -> ch.isDigit() } },
                    label = { Text("最大人数") },
                    singleLine = true
                )
                Text(text = "開始 $slotId / 終了 コマ")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    SLOT_IDS.forEach { sid ->
                        OutlinedButton(
                            onClick = { endSlot.value = sid },
                            border = if (endSlot.value == sid) ButtonDefaults.outlinedButtonBorder(enabled = true) else null,
                            modifier = Modifier.padding(vertical = 2.dp)
                        ) { Text(text = slotLabel(sid)) }
                    }
                }
                if (msg.value.isNotBlank()) Text(text = msg.value, color = MaterialTheme.colorScheme.error)
            }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val maxNum = max.value.toIntOrNull() ?: 4
                    val result = repo.createEvent(
                        categoryId = cat.value.id,
                        dayId = dayId,
                        slotStartId = slotId,
                        slotEndId = endSlot.value,
                        title = title.value.ifBlank { cat.value.label },
                        maxParticipants = maxNum
                    )
                    if (result.isSuccess) {
                        msg.value = "作成しました"
                        onCreated()
                    } else {
                        msg.value = result.exceptionOrNull()?.message ?: "失敗しました"
                    }
                }) { Text("作成") }
                TextButton(onClick = onCancel) { Text("キャンセル") }
            }
        }
    )
}

@Composable
private fun ClassEditDialog(
    repo: ComaRepository,
    dayId: String,
    slotId: String,
    classInfo: ClassInfo?,
    onSaved: () -> Unit,
    onCancel: () -> Unit,
) {
    val title = remember { mutableStateOf(classInfo?.title ?: "") }
    val room = remember { mutableStateOf(classInfo?.classroom ?: "") }
    val msg = remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onCancel,
        confirmButton = {},
        title = { Text(text = "授業を編集") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = title.value, onValueChange = { title.value = it }, label = { Text("授業名") })
                OutlinedTextField(value = room.value, onValueChange = { room.value = it }, label = { Text("教室") })
                if (msg.value.isNotBlank()) Text(text = msg.value, color = MaterialTheme.colorScheme.error)
            }
        },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    try {
                        repo.addBusySlot(dayId, slotId, title.value, room.value)
                        msg.value = "保存しました"
                        onSaved()
                    } catch (e: Exception) {
                        msg.value = e.message ?: "失敗しました"
                    }
                }) { Text("保存") }
                OutlinedButton(onClick = {
                    try {
                        repo.removeBusySlot(dayId, slotId)
                        msg.value = "削除しました"
                        onSaved()
                    } catch (e: Exception) {
                        msg.value = e.message ?: "失敗しました"
                    }
                }, enabled = classInfo != null) { Text("削除") }
                TextButton(onClick = onCancel) { Text("閉じる") }
            }
        }
    )
}

private fun Event.category(): EventCategory? =
    EventCategory.entries.firstOrNull { it.id == categoryId }

