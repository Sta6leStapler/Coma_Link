package com.example.coma_link.data

import com.example.coma_link.data.model.User

/**
 * UI が依存するユーザー取得用リポジトリインターフェース。
 * データソース（フェイク/本番）を隠蔽する。
 */
interface UserRepository {
    suspend fun getUser(): User
}

