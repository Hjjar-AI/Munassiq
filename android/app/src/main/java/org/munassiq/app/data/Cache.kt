package org.munassiq.app.data

import androidx.room.*

@Entity(tableName = "responses", primaryKeys = ["owner", "path"])
data class CachedResponse(val owner: String, val path: String, val body: String, val savedAt: Long)

@Dao interface CacheDao {
    @Query("SELECT * FROM responses WHERE owner = :owner AND path = :path LIMIT 1")
    suspend fun read(owner: String, path: String): CachedResponse?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun put(row: CachedResponse)
    @Query("DELETE FROM responses") suspend fun clear()
    @Query("DELETE FROM responses WHERE savedAt < :cutoff") suspend fun expire(cutoff: Long)
    @Query("DELETE FROM responses WHERE rowid NOT IN (SELECT rowid FROM responses ORDER BY savedAt DESC LIMIT 250)") suspend fun trim()
}

@Database(entities = [CachedResponse::class], version = 1, exportSchema = false)
abstract class CacheDatabase : RoomDatabase() { abstract fun responses(): CacheDao }
