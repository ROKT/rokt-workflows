package com.rokt.sizereport

import android.app.Activity
import androidx.compose.runtime.Composable
import com.mparticle.MParticle
import com.mparticle.MParticleOptions

object SdkHook {
    fun init(activity: Activity) {
        MParticle.start(
            MParticleOptions.builder(activity.applicationContext)
                // Placeholders: anything shaped like `xx1-<32 hex>` trips secret scanners.
                .credentials("REPLACE WITH YOUR MPARTICLE API KEY", "REPLACE WITH YOUR MPARTICLE API SECRET")
                .build(),
        )
    }

    @Composable
    fun Content() {}
}
