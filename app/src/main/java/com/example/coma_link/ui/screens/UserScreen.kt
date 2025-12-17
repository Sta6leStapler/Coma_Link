package com.example.coma_link.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.example.coma_link.data.ComaRepository

@Composable
fun UserScreen(repo: ComaRepository, tick: Int, onChanged: () -> Unit) {
    val loginUser = remember { mutableStateOf("") }
    val loginPass = remember { mutableStateOf("") }
    val regUser = remember { mutableStateOf("") }
    val regPass = remember { mutableStateOf("") }
    val regDisplay = remember { mutableStateOf("") }
    val info = remember { mutableStateOf("") }

    val pending = if (repo.isLoggedIn) repo.getOwnerPendingEvents(repo.currentUserId ?: "") else emptyList()

    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(text = "現在のユーザー: ${repo.currentDisplayName()}", fontWeight = FontWeight.Medium)
                Text(text = if (pending.isNotEmpty()) "承認待ち: ${pending.size} 件" else "承認待ちはありません")
                if (repo.isLoggedIn) {
                    OutlinedButton(onClick = { repo.logout(); info.value = "ログアウトしました"; onChanged() }) {
                        Text("ログアウト")
                    }
                }
            }
        }

        Text(text = "ログイン", fontWeight = FontWeight.Bold)
        Card {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = loginUser.value, onValueChange = { loginUser.value = it }, label = { Text("ユーザー名") })
                OutlinedTextField(value = loginPass.value, onValueChange = { loginPass.value = it }, label = { Text("パスワード") })
                Button(onClick = {
                    val res = repo.login(loginUser.value, loginPass.value)
                    info.value = res.getOrElse { it.message ?: "失敗" }
                    onChanged()
                }) { Text("ログイン") }
            }
        }

        Text(text = "新規登録", fontWeight = FontWeight.Bold)
        Card {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = regDisplay.value, onValueChange = { regDisplay.value = it }, label = { Text("表示名") })
                OutlinedTextField(value = regUser.value, onValueChange = { regUser.value = it }, label = { Text("ユーザー名") })
                OutlinedTextField(value = regPass.value, onValueChange = { regPass.value = it }, label = { Text("パスワード") })
                Button(onClick = {
                    val res = repo.registerUser(regUser.value, regPass.value, regDisplay.value)
                    info.value = res.getOrElse { it.message ?: "失敗" }
                    onChanged()
                }) { Text("登録") }
            }
        }

        if (info.value.isNotBlank()) {
            Text(text = info.value, color = MaterialTheme.colorScheme.primary)
        }
    }
}

