package com.example.coma_link.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.foundation.BorderStroke
import com.example.coma_link.data.ComaRepository
import com.example.coma_link.ui.screens.SearchScreen
import com.example.coma_link.ui.screens.TimetableScreen
import com.example.coma_link.ui.screens.UserScreen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ComaLinkApp() {
    val repo = remember { ComaRepository() }
    var tick by remember { mutableStateOf(0) }

    fun refresh() { tick++ }

    Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
        Column {
            TopAppBar(
                title = {
                    Text(
                        text = "Coma Link",
                        style = MaterialTheme.typography.titleLarge,
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                ),
                actions = {
                    val label = repo.currentDisplayName()
                    Text(
                        text = label,
                        modifier = Modifier
                            .padding(end = 12.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        fontSize = 14.sp,
                    )
                }
            )

            TabHost(repo = repo, tick = tick, onChanged = { refresh() })
        }
    }
}

private enum class MainTab(val label: String) { Timetable("時間割"), Search("募集検索"), User("ユーザー") }

@Composable
private fun TabHost(repo: ComaRepository, tick: Int, onChanged: () -> Unit) {
    var tab by remember { mutableStateOf(MainTab.Timetable) }
    Column(
        modifier = Modifier
            .verticalScroll(rememberScrollState())
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            MainTab.values().forEach { t ->
                val selected = t == tab
                OutlinedButton(
                    onClick = { tab = t },
                    colors = ButtonDefaults.outlinedButtonColors(
                        containerColor = if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.12f) else Color.Transparent
                    ),
                    border = if (selected) BorderStroke(1.dp, MaterialTheme.colorScheme.primary) else null,
                    modifier = Modifier.weight(1f)
                ) {
                    Text(text = t.label)
                }
            }
        }

        when (tab) {
            MainTab.Timetable -> TimetableScreen(repo = repo, tick = tick, onChanged = onChanged)
            MainTab.Search -> SearchScreen(repo = repo, tick = tick, onChanged = onChanged)
            MainTab.User -> UserScreen(repo = repo, tick = tick, onChanged = onChanged)
        }
    }
}

