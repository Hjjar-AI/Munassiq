import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}
if (file("google-services.json").exists()) apply(plugin = "com.google.gms.google-services")
val deployment = Properties().apply {
    val config = rootProject.file("app/src/deployment/server.properties")
    require(config.exists()) { "Run python3 operations/scripts/prepare_android.py first. See docs/android.md." }
    config.inputStream().use(::load)
}
// Signing secrets come only from the user's build process; never BuildConfig/source.
val releaseRequested = gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) }
val signingValues = listOf("MUNASSIQ_KEYSTORE_FILE", "MUNASSIQ_STORE_PASSWORD", "MUNASSIQ_KEY_ALIAS", "MUNASSIQ_KEY_PASSWORD")
    .map { providers.environmentVariable(it).orNull }
if (releaseRequested) {
    require(deployment.getProperty("validation", "false") != "true") { "Release requires real server configuration, not --validation." }
    require(signingValues.all { !it.isNullOrBlank() }) { "Set all four MUNASSIQ signing environment variables. See docs/release.md." }
    require(file(signingValues[0]!!).isFile) { "Configured release keystore is missing." }
}
fun quoted(value: String) = "\"" + value.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
android {
    namespace = "org.munassiq.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "org.munassiq.app"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
        manifestPlaceholders["serverHost"] = deployment.getProperty("server.host")
        manifestPlaceholders["verifyAppLinks"] = deployment.getProperty("verify.links", "false")
        buildConfigField("String", "SERVER_ORIGIN", quoted(deployment.getProperty("server.origin")))
        buildConfigField("String", "MAP_TILES", quoted(deployment.getProperty("maps.tiles", "")))
        buildConfigField("boolean", "IS_VALIDATION", deployment.getProperty("validation", "false"))
    }
    sourceSets["main"].res.srcDir("src/deployment/res")
    buildFeatures { compose = true; buildConfig = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }
    kotlinOptions { jvmTarget = "17" }
    if (releaseRequested) {
        signingConfigs {
            create("release") {
                storeFile = file(signingValues[0]!!)
                storePassword = signingValues[1]
                keyAlias = signingValues[2]
                keyPassword = signingValues[3]
            }
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            if (releaseRequested) signingConfig = signingConfigs.getByName("release")
        }
    }
}
dependencies {
    implementation(platform("androidx.compose:compose-bom:2025.04.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.1")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.1")
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.room:room-runtime:2.7.1")
    implementation("androidx.room:room-ktx:2.7.1")
    ksp("androidx.room:room-compiler:2.7.1")
    implementation("androidx.work:work-runtime-ktx:2.10.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.1")
    implementation(platform("com.google.firebase:firebase-bom:33.13.0"))
    implementation("com.google.firebase:firebase-messaging")
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.5")
}
