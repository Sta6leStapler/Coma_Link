package com.example.coma_link.data.model

/**
 * サーバーと取り決める共通レスポンス形式。
 *
 * - code: 0/200 で成功、それ以外はビジネス/システムエラー
 * - message: 人間向けのエラーメッセージ
 * - data: 実データ。null の場合あり
 */
data class ApiResponse<T>(
    val code: Int,
    val message: String,
    val data: T?,
) {
    val isSuccess: Boolean
        get() = code == 0 || code == 200
}

