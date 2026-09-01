import Foundation

/// Runs the bundled Python core and streams its newline-delimited JSON events.
final class CoreRunner {
    enum RunnerError: LocalizedError {
        case executableMissing
        case failed(code: Int32, message: String)

        var errorDescription: String? {
            switch self {
            case .executableMissing:
                return "The bundled spectro-rb core is missing from the app bundle."
            case let .failed(code, message):
                return message.isEmpty ? "The sync process failed (exit code \(code))." : message
            }
        }
    }

    /// Bundled runtime first, then a developer virtualenv, then $PATH.
    static func locateExecutable() -> URL? {
        if let resources = Bundle.main.resourceURL {
            let bundled = resources.appendingPathComponent("python/bin/spectro-rb")
            if FileManager.default.isExecutableFile(atPath: bundled.path) { return bundled }
        }
        let devPaths = [
            FileManager.default.currentDirectoryPath + "/.venv/bin/spectro-rb",
            NSHomeDirectory() + "/sources/music-filter/spectro-rb-sync/.venv/bin/spectro-rb",
            "/usr/local/bin/spectro-rb",
            "/opt/homebrew/bin/spectro-rb",
        ]
        for path in devPaths where FileManager.default.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
        return nil
    }

    private var process: Process?

    var isRunning: Bool { process?.isRunning ?? false }

    func cancel() {
        process?.terminate()
        process = nil
    }

    func doctor() throws -> DoctorReport {
        guard let executable = Self.locateExecutable() else { throw RunnerError.executableMissing }
        let process = Process()
        process.executableURL = executable
        process.arguments = ["doctor", "--json"]
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = Pipe()
        try process.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        return try JSONDecoder().decode(DoctorReport.self, from: data)
    }

    /// Runs a sync, calling `onEvent` on the main queue for every event.
    func sync(
        csv: URL,
        databaseOverride: URL?,
        dryRun: Bool,
        skipBackup: Bool,
        onEvent: @escaping (CoreEvent) -> Void,
        onFinish: @escaping (Result<Void, Error>) -> Void
    ) {
        guard let executable = Self.locateExecutable() else {
            onFinish(.failure(RunnerError.executableMissing))
            return
        }

        var arguments = ["sync", csv.path, "--json"]
        if dryRun { arguments.append("--dry-run") }
        if skipBackup { arguments.append("--no-backup") }
        if let database = databaseOverride {
            arguments.append(contentsOf: ["--db", database.path])
        }

        let process = Process()
        process.executableURL = executable
        process.arguments = arguments
        process.environment = ProcessInfo.processInfo.environment.merging(
            ["PYTHONUNBUFFERED": "1", "NO_COLOR": "1"], uniquingKeysWith: { _, new in new }
        )

        let outPipe = Pipe()
        let errPipe = Pipe()
        process.standardOutput = outPipe
        process.standardError = errPipe
        self.process = process

        var buffer = Data()
        var stderrText = ""

        outPipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            guard !chunk.isEmpty else { return }
            buffer.append(chunk)
            while let range = buffer.range(of: Data("\n".utf8)) {
                let line = buffer.subdata(in: buffer.startIndex..<range.lowerBound)
                buffer.removeSubrange(buffer.startIndex..<range.upperBound)
                guard !line.isEmpty, let event = Self.decode(line: line) else { continue }
                DispatchQueue.main.async { onEvent(event) }
            }
        }
        errPipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            guard !chunk.isEmpty, let text = String(data: chunk, encoding: .utf8) else { return }
            stderrText += text
        }

        process.terminationHandler = { proc in
            outPipe.fileHandleForReading.readabilityHandler = nil
            errPipe.fileHandleForReading.readabilityHandler = nil
            DispatchQueue.main.async {
                self.process = nil
                if proc.terminationStatus == 0 {
                    onFinish(.success(()))
                } else {
                    let message = stderrText
                        .replacingOccurrences(of: "Error: ", with: "")
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    onFinish(.failure(RunnerError.failed(code: proc.terminationStatus, message: message)))
                }
            }
        }

        do {
            try process.run()
        } catch {
            self.process = nil
            onFinish(.failure(error))
        }
    }

    private static func decode(line: Data) -> CoreEvent? {
        guard
            let object = try? JSONSerialization.jsonObject(with: line) as? [String: Any],
            let name = object["event"] as? String
        else { return nil }

        let decoder = JSONDecoder()
        switch name {
        case "csv_loaded":
            return .csvLoaded(
                rows: object["rows"] as? Int ?? 0,
                skipped: object["skipped"] as? Int ?? 0,
                verdicts: object["verdict_counts"] as? [String: Int] ?? [:]
            )
        case "database_found":
            return .databaseFound(
                path: object["path"] as? String ?? "",
                source: object["source"] as? String ?? "",
                modified: object["modified"] as? String ?? ""
            )
        case "backup_created":
            return .backupCreated(
                directory: object["directory"] as? String ?? "",
                bytes: object["bytes"] as? Int ?? 0
            )
        case "collection_loaded":
            return .collectionLoaded(tracks: object["tracks"] as? Int ?? 0)
        case "plan_ready":
            guard let summary = try? decoder.decode(Summary.self, from: line) else { return nil }
            return .planReady(summary: summary)
        case "applying":
            return .applying(
                applied: object["applied"] as? Int ?? 0,
                total: object["total"] as? Int ?? 0
            )
        case "applied":
            return .applied(applied: object["applied"] as? Int ?? 0)
        case "result":
            guard let result = try? decoder.decode(SyncResult.self, from: line) else { return nil }
            return .result(result)
        case "error":
            return .failure(
                kind: object["kind"] as? String ?? "unknown",
                message: object["message"] as? String ?? "Unknown error"
            )
        default:
            return .unknown(name)
        }
    }
}
