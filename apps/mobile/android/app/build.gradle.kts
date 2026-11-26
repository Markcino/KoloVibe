plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.kolovibe.kolovibe"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "com.kolovibe.kolovibe"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        // Owner decision SIM-02: shared video links (https://<host>/open/videos/<id>) open this app.
        // <host> is the Gateway's KOLOVIBE_APP_LINK_ORIGIN host, passed as -Pkolovibe.appLinkHost=<host>.
        // The default is a reserved name that never verifies, so no real domain is claimed by accident.
        val appLinkHost = (project.findProperty("kolovibe.appLinkHost") as String?) ?: "app-links.invalid"
        if (!Regex("^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
                .matches(appLinkHost)) {
            throw GradleException("Invalid kolovibe.appLinkHost")
        }
        manifestPlaceholders["appLinkHost"] = appLinkHost
    }

    buildTypes {
        release {
            // Release signing is deliberately unconfigured until release review.
            // Never distribute a release signed with development keys.
        }
    }
}

flutter {
    source = "../.."
}
