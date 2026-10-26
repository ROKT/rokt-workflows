package com.rokt.sizereport

import android.app.Activity
import android.util.Log
import androidx.compose.runtime.Composable
import com.rokt.roktux.RoktLayout
import com.rokt.roktux.RoktUxConfig

object SdkHook {
    fun init(activity: Activity) {}

    // The rendering entry point, so R8 keeps the layout pipeline a partner integration keeps.
    @Composable
    fun Content() {
        RoktLayout(
            experienceResponse = "",
            location = "",
            roktUxConfig = RoktUxConfig.builder().build(),
            onUxEvent = { Log.d("SizeReport", "$it") },
            onPlatformEvent = {},
        )
    }
}
