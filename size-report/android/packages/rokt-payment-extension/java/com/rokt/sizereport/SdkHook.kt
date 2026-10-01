package com.rokt.sizereport

import android.app.Activity
import androidx.compose.runtime.Composable
import com.rokt.payment.extension.RoktGooglePayEnvironment
import com.rokt.payment.extension.RoktPaymentExtension
import com.rokt.roktsdk.Rokt

object SdkHook {
    fun init(activity: Activity) {
        Rokt.init("0000000000000000", "1.0", activity)
        Rokt.registerPaymentExtension(
            RoktPaymentExtension(
                googlePayEnvironment = RoktGooglePayEnvironment.TEST,
                merchantCountryCode = "US",
                merchantName = "Rokt Size Report",
            ),
            mapOf("stripePublishableKey" to "pk_test_00000000000000000000000000"),
        )
        Rokt.selectShoppableAds(identifier = "RoktExperience")
    }

    @Composable
    fun Content() {}
}
