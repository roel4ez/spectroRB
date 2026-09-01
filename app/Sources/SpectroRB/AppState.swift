import Foundation
import SwiftUI

@MainActor
final class AppState: ObservableObject {
    @Published var csvURL: URL?
    @Published var databaseOverride: URL?
    @Published var detectedDatabase: DatabaseInfo?
    @Published var rekordboxProcesses: [String] = []
    @Published var backups: [String] = []
    @Published var coreVersion: String = ""
    @Published var coreAvailable: Bool = true

    @Published var isRunning = false
    @Published var statusLine = "Ready."
    @Published var progress: Double?
    @Published var result: SyncResult?
    @Published var errorMessage: String?
    @Published var lastRunWasDryRun = true
    @Published var overwriteExisting = true

    private let runner = CoreRunner()

    var databaseInUse: String {
        databaseOverride?.path ?? detectedDatabase?.path ?? "Not found"
    }

    var rekordboxIsRunning: Bool { !rekordboxProcesses.isEmpty }

    var canSync: Bool { csvURL != nil && !isRunning && coreAvailable }

    func refreshEnvironment() {
        rekordboxProcesses = RekordboxProbe.runningProcesses()
        guard CoreRunner.locateExecutable() != nil else {
            coreAvailable = false
            errorMessage = "The bundled spectro-rb core could not be found."
            return
        }
        coreAvailable = true
        Task.detached(priority: .utility) {
            do {
                let report = try CoreRunner.doctor()
                await MainActor.run {
                    self.coreVersion = report.version
                    self.detectedDatabase = report.databases.first
                    self.backups = report.backups
                    if report.databases.isEmpty {
                        self.errorMessage = "No Rekordbox database found. Choose one manually."
                    }
                }
            } catch {
                await MainActor.run { self.errorMessage = error.localizedDescription }
            }
        }
    }

    func run(dryRun: Bool) {
        guard let csv = csvURL else { return }

        // Checked at the moment of the click, so opening Rekordbox after the app
        // started still blocks. The core re-checks again before writing.
        rekordboxProcesses = RekordboxProbe.runningProcesses()
        if rekordboxIsRunning {
            errorMessage =
                "Rekordbox is running (\(rekordboxProcesses.joined(separator: ", "))). "
                + "Quit it completely and try again — nothing was read or written."
            statusLine = "Blocked."
            result = nil
            return
        }
        isRunning = true
        errorMessage = nil
        result = nil
        progress = nil
        lastRunWasDryRun = dryRun
        statusLine = dryRun ? "Analysing…" : "Syncing…"

        runner.sync(
            csv: csv,
            databaseOverride: databaseOverride,
            dryRun: dryRun,
            skipBackup: false,
            overwriteExisting: overwriteExisting,
            onEvent: { [weak self] event in
                guard let self else { return }
                switch event {
                case let .csvLoaded(rows, _, _):
                    self.statusLine = "Read \(rows.formatted()) Spectro rows."
                case let .databaseFound(path, _, _):
                    self.statusLine = "Using \((path as NSString).lastPathComponent)…"
                case let .backupCreated(directory, _):
                    self.statusLine = "Backed up to \((directory as NSString).lastPathComponent)."
                case let .collectionLoaded(tracks):
                    self.statusLine = "Scanned \(tracks.formatted()) Rekordbox tracks."
                case let .planReady(summary):
                    self.statusLine = "\(summary.changes.formatted()) colour changes planned."
                case let .applying(applied, total):
                    self.progress = total > 0 ? Double(applied) / Double(total) : nil
                    self.statusLine = "Writing \(applied.formatted()) of \(total.formatted())…"
                case let .applied(applied):
                    self.progress = 1
                    self.statusLine = "Wrote \(applied.formatted()) colours."
                case let .result(result):
                    self.result = result
                case let .failure(_, message):
                    self.errorMessage = message
                case .unknown:
                    break
                }
            },
            onFinish: { [weak self] outcome in
                guard let self else { return }
                self.isRunning = false
                self.progress = nil
                switch outcome {
                case .success:
                    if self.errorMessage == nil {
                        self.statusLine = dryRun ? "Dry run complete — nothing written." : "Done."
                    }
                case let .failure(error):
                    if self.errorMessage == nil {
                        self.errorMessage = error.localizedDescription
                    }
                    self.statusLine = "Failed."
                }
                self.refreshEnvironment()
            }
        )
    }

    func cancel() {
        runner.cancel()
        isRunning = false
        statusLine = "Cancelled."
    }
}
