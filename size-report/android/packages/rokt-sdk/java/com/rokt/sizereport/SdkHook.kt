package com.rokt.sizereport

import android.app.Activity
import androidx.compose.runtime.Composable
import com.rokt.roktsdk.Rokt

object SdkHook {
    fun init(activity: Activity) {
        Rokt.init("0000000000000000", "1.0", activity)
        // eventCollector picks the Unit-returning overload; without it the call is ambiguous.
        Rokt.selectPlacements(
            identifier = "RoktExperience",
            attributes = mapOf("email" to "size-report@example.com"),
            eventCollector = null,
        )
    }

    @Composable
    fun Content() {}
}
