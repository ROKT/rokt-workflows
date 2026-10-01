import SwiftUI
import Rokt_Widget
import RoktPaymentExtension

// The payment extension README's direct integration: init, register, Shoppable Ads.
public enum SizeEntry {
    public static func start() {
        Rokt.initWith(roktTagId: "222")
        if let paymentExtension = RoktPaymentExtension(applePayMerchantId: "merchant.com.example", urlScheme: "sizeapp") {
            Rokt.registerPaymentExtension(paymentExtension, config: ["stripeKey": "pk_test_size_report"])
        }
        Rokt.selectShoppableAds(identifier: "ConfirmationPage", attributes: ["email": "test@example.com"], onEvent: { _ in })
    }

    public static func content() -> AnyView {
        AnyView(EmptyView())
    }
}
