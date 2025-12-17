package com.example.coma_link.data.model

/**
 * ユーザードメインモデル。時刻は ISO 8601（タイムゾーン付き）を利用。
 */
data class User(
    val id: String,
    val name: String,
    val email: String,
    val avatarUrl: String? = null,
    val updatedAt: String? = null,
)

