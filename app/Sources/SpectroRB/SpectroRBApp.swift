import SwiftUI

@main
struct SpectroRBApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup("Spectro → Rekordbox") {
            ContentView()
                .environmentObject(state)
        }
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .newItem) {}
            CommandGroup(after: .appInfo) {
                Button("Re-check Rekordbox…") { state.refreshEnvironment() }
                    .keyboardShortcut("r")
            }
        }
    }
}
