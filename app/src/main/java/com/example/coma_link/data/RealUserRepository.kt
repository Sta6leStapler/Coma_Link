package com.example.coma_link.data

import com.example.coma_link.BuildConfig
import com.example.coma_link.data.model.User
import com.example.coma_link.network.UserApi
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

/**
 * 本番用のネットワーク実装。Retrofit 経由でサーバーを呼び出す。
 */
class RealUserRepository(
    private val api: UserApi,
) : UserRepository {

    override suspend fun getUser(): User {
        val resp = api.getCurrentUser()
        if (resp.isSuccess && resp.data != null) {
            return resp.data
        }
        throw IllegalStateException(resp.message.ifBlank { "ユーザー情報の取得に失敗しました" })
    }

    companion object {
        fun create(
            baseUrl: String = BuildConfig.BASE_URL,
            enableLog: Boolean = BuildConfig.DEBUG,
        ): RealUserRepository {
            val logging = HttpLoggingInterceptor().apply {
                level = if (enableLog) HttpLoggingInterceptor.Level.BASIC else HttpLoggingInterceptor.Level.NONE
            }
            val client = OkHttpClient.Builder()
                .addInterceptor(logging)
                .build()

            val retrofit = Retrofit.Builder()
                .baseUrl(baseUrl.ensureTrailingSlash())
                .client(client)
                .addConverterFactory(MoshiConverterFactory.create())
                .build()

            return RealUserRepository(retrofit.create(UserApi::class.java))
        }

        private fun String.ensureTrailingSlash(): String =
            if (endsWith("/")) this else "$this/"
    }
}

