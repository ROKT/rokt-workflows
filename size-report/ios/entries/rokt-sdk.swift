import SwiftUI
import Rokt_Widget

// Same calls as rokt-sdk-ios's Tests/SizeReport: init, then an overlay placement.
public enum SizeEntry {
    public static func start() {
        Rokt.initWith(roktTagId: "222")
        Rokt.selectPlacements(
            identifier: "RoktExperience",
            attributes: ["email": "test@example.com"],
            onEvent: { event in print("Rokt event: \(event)") }
        )
    }

    public static func content() -> AnyView {
        AnyView(EmptyView())
    }
}
