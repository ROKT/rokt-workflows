import SwiftUI
import RoktUXHelper

// Same call as rokt-ux-helper-ios's Tests/SizeReport: the rendering entry point, so the layout
// pipeline is linked. The empty response is handled internally.
public enum SizeEntry {
    private static let roktUX = RoktUX()

    public static func start() {
        roktUX.loadLayout(
            experienceResponse: "",
            onRoktUXEvent: { event in print("RoktUX event: \(event)") },
            onRoktPlatformEvent: { _ in },
            onEmbeddedSizeChange: { _, _ in }
        )
    }

    public static func content() -> AnyView {
        AnyView(EmptyView())
    }
}
