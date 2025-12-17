package com.example.coma_link.network

import com.example.coma_link.data.model.ApiResponse
import com.example.coma_link.data.model.User
import retrofit2.http.GET

/**
 * Retrofit で定義するユーザー系エンドポイント。
 */
interface UserApi {

    @GET("user/me")
    suspend fun getCurrentUser(): ApiResponse<User>
}

