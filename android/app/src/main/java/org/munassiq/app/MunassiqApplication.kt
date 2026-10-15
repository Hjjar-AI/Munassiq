package org.munassiq.app

import android.app.Application
import androidx.room.Room
import org.munassiq.app.data.*

class MunassiqApplication : Application() {
    lateinit var repository: Repository
        private set
    override fun onCreate() {
        super.onCreate()
        val vault = SessionVault(this)
        val database = Room.databaseBuilder(this, CacheDatabase::class.java, "recent.db").build()
        repository = Repository(this, ApiClient(vault), vault, database.responses())
    }
}
