package com.example.coma_link.data

import com.example.coma_link.BuildConfig

/**
 * リポジトリの簡易プロバイダ。Fake/Real の切替を UI から隠蔽する。
 */
object UserRepositoryProvider {

    @Volatile
    private var cached: UserRepository? = null

    /**
     * @param useFake true ならフェイク実装で UI を先行開発、false なら実ネットワーク
     */
    fun provide(
        useFake: Boolean = true,
        baseUrl: String = BuildConfig.BASE_URL,
    ): UserRepository {
        return cached ?: synchronized(this) {
            cached ?: buildRepository(useFake, baseUrl).also { cached = it }
        }
    }

    fun override(repository: UserRepository?) {
        cached = repository
    }

    private fun buildRepository(useFake: Boolean, baseUrl: String): UserRepository {
        return if (useFake) {
            FakeUserRepository()
        } else {
            RealUserRepository.create(baseUrl)
        }
    }
}

