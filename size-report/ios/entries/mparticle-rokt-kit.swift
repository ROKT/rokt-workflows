import SwiftUI
import mParticle_Apple_SDK
import mParticle_Rokt_Swift

// Core start, an overlay placement through the kit, and the kit's embedded SwiftUI layout.
public enum SizeEntry {
    public static func start() {
        let options = MParticleOptions(key: "test-key", secret: "test-secret")
        options.environment = .development
        let identifyRequest = MPIdentityApiRequest.withEmptyUser()
        identifyRequest.email = "test@example.com"
        options.identifyRequest = identifyRequest
        MParticle.sharedInstance().start(with: options)
        MParticle.sharedInstance().rokt.selectPlacements("size_test", attributes: ["email": "test@example.com"])
    }

    public static func content() -> AnyView {
        AnyView(EmbeddedLayout())
    }
}

private struct EmbeddedLayout: View {
    @State private var sdkTriggered = true

    var body: some View {
        MPRoktLayout(sdkTriggered: $sdkTriggered, identifier: "size_test", attributes: ["email": "test@example.com"])
            .roktLayout
    }
}
