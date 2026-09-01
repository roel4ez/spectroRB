import AppKit
import Foundation

/// One-shot check for a running Rekordbox. Cheap and synchronous, so it can be
/// run at the moment the user asks for a sync.
enum RekordboxProbe {
    private static let hints = ["rekordbox", "rekordboxagent"]

    static func runningProcesses() -> [String] {
        var found = Set<String>()

        for app in NSWorkspace.shared.runningApplications {
            let identifier = (app.bundleIdentifier ?? "").lowercased()
            let name = (app.localizedName ?? "").lowercased()
            if hints.contains(where: { identifier.contains($0) || name.contains($0) }) {
                found.insert(app.localizedName ?? app.bundleIdentifier ?? "rekordbox")
            }
        }

        // rekordboxAgent is not a normal GUI app, so also look at the process list.
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/ps")
        process.arguments = ["-Ao", "comm="]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()
        if (try? process.run()) != nil {
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            let text = String(data: data, encoding: .utf8) ?? ""
            for line in text.split(separator: "\n") {
                let name = String(line.split(separator: "/").last ?? "")
                if hints.contains(where: { name.lowercased().contains($0) }) {
                    found.insert(name)
                }
            }
        }

        return found.sorted()
    }
}
