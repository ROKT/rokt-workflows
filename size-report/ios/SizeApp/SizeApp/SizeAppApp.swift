import SwiftUI
import SizeTarget

// The starting app. Every package is linked through SizeTarget, whose entry point is generated
// per run, so the baseline and the measured build differ only by that package.
@main
struct SizeAppApp: App {
    init() {
        SizeEntry.start()
    }

    var body: some Scene {
        WindowGroup {
            VStack {
                Text("Hello, world!")
                SizeEntry.content()
            }
            .padding()
        }
    }
}
