import SwiftUI
import mParticle_Apple_SDK

// Integration guide steps 1-2: start the SDK with an identify request.
public enum SizeEntry {
    public static func start() {
        let options = MParticleOptions(key: "test-key", secret: "test-secret")
        options.environment = .development
        let identifyRequest = MPIdentityApiRequest.withEmptyUser()
        identifyRequest.email = "test@example.com"
        options.identifyRequest = identifyRequest
        MParticle.sharedInstance().start(with: options)
    }

    public static func content() -> AnyView {
        AnyView(EmptyView())
    }
}
