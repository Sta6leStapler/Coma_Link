package com.example.coma_link.data

import com.example.coma_link.data.model.User
import kotlinx.coroutines.delay
import java.time.Instant

/**
 * フェイク実装。バックエンド未準備でも UI 開発を進めるためのローカルデータ。
 */
class FakeUserRepository : UserRepository {

    override suspend fun getUser(): User {
        delay(250) // ネットワーク遅延の疑似表現
        return User(
            id = "user-demo",
            name = "デモユーザー",
            email = "demo@example.com",
            avatarUrl = "https://example.invalid/avatar.png",
            updatedAt = Instant.now().toString(),
        )
    }
}

