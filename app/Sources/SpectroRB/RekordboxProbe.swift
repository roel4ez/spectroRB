import AppKit
import Foundation

/// One-shot check for a running Rekordbox. Cheap and synchronous, so it can be
/// run at the moment the user asks for a sync.
enum RekordboxProbe {
    /// Matched as a prefix, so this app ("Spectro to Rekordbox") never matches itself.
    private static func matches(_ value: String) -> Bool {
        value.lowercased().hasPrefix("rekordbox")
    }

    static func runningProcesses() -> [String] {
        var found = Set<String>()
        let selfPID = ProcessInfo.processInfo.processIdentifier

        for app in NSWorkspace.shared.runningApplications where app.processIdentifier != selfPID {
            let identifier = (app.bundleIdentifier ?? "").lowercased()
            let name = app.localizedName ?? ""
            // e.g. com.pioneerdj.rekordbox / com.alphatheta.rekordbox
            let identifierMatches = identifier.split(separator: ".").contains(where: {
                matches(String($0))
            })
            if identifierMatches || matches(name) {
                found.insert(name.isEmpty ? (app.bundleIdentifier ?? "rekordbox") : name)
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
                if matches(name) {
                    found.insert(name)
                }
            }
        }

        return found.sorted()
    }
}
