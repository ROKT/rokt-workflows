package com.rokt.sizereport

import android.app.Activity
import androidx.compose.runtime.Composable
import com.mparticle.MParticle
import com.mparticle.MParticleOptions
import com.mparticle.kits.MParticleRokt

// Same entry point as mparticle-rokt-kit on purpose: SDK+ has no API of its own, and the payment
// extension it adds is kept by proguard-rules.pro, so the two differ only by the artifact.
object SdkHook {
    fun init(activity: Activity) {
        MParticle.start(
            MParticleOptions.builder(activity.applicationContext)
                // Placeholders: anything shaped like `xx1-<32 hex>` trips secret scanners.
                .credentials("REPLACE WITH YOUR MPARTICLE API KEY", "REPLACE WITH YOUR MPARTICLE API SECRET")
                .build(),
        )
        MParticleRokt.Rokt().selectPlacements(
            identifier = "RoktExperience",
            attributes = mapOf("email" to "size-report@example.com"),
        )
    }

    @Composable
    fun Content() {}
}
