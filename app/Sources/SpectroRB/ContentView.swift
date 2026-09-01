import AppKit
import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject private var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            Divider()
            sourceSection
            mappingSection
            Divider()
            actionBar
            resultsSection
        }
        .padding(22)
        .frame(minWidth: 720, minHeight: 620)
        .onAppear { state.refreshEnvironment() }
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Spectro → Rekordbox")
                    .font(.system(size: 22, weight: .semibold))
                Text("Colours only. Ratings, cues, grids, comments and playlists are never touched.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            statusBadge
        }
    }

    private var statusBadge: some View {
        Group {
            if state.rekordboxIsRunning {
                Label("Rekordbox is open", systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.orange)
            } else {
                Label("Rekordbox closed", systemImage: "checkmark.seal.fill")
                    .foregroundStyle(.green)
            }
        }
        .font(.callout)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(.quaternary, in: RoundedRectangle(cornerRadius: 8))
    }

    private var sourceSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            fileRow(
                icon: "doc.text",
                title: "Spectro CSV",
                value: state.csvURL?.path ?? "No file chosen",
                buttonTitle: "Choose…",
                action: chooseCSV
            )
            fileRow(
                icon: "internaldrive",
                title: "Rekordbox database",
                value: state.databaseInUse,
                buttonTitle: state.databaseOverride == nil ? "Override…" : "Reset",
                action: {
                    if state.databaseOverride == nil {
                        chooseDatabase()
                    } else {
                        state.databaseOverride = nil
                    }
                }
            )
            if state.databaseOverride == nil, let database = state.detectedDatabase {
                Text("Detected automatically via \(database.source) · modified \(database.modified)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.leading, 28)
            }
        }
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            guard let provider = providers.first else { return false }
            _ = provider.loadObject(ofClass: URL.self) { url, _ in
                guard let url, url.pathExtension.lowercased() == "csv" else { return }
                DispatchQueue.main.async { state.csvURL = url }
            }
            return true
        }
    }

    private func fileRow(
        icon: String,
        title: String,
        value: String,
        buttonTitle: String,
        action: @escaping () -> Void
    ) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .frame(width: 18)
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 1) {
                Text(title).font(.subheadline).bold()
                Text(value)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                    .truncationMode(.head)
            }
            Spacer()
            Button(buttonTitle, action: action)
        }
    }

    private var mappingSection: some View {
        HStack(spacing: 18) {
            ForEach(Verdict.allCases, id: \.self) { verdict in
                HStack(spacing: 6) {
                    Text(verdict.symbol)
                    Text(verdict.rawValue).font(.caption).bold()
                    Image(systemName: "arrow.right").font(.caption2).foregroundStyle(.secondary)
                    Text(verdict.colorName).font(.caption).foregroundStyle(.secondary)
                    if let count = state.result?.summary.verdictCounts[verdict.rawValue] {
                        Text("(\(count.formatted()))").font(.caption).foregroundStyle(.tertiary)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(.quaternary.opacity(0.5), in: Capsule())
            }
            Spacer()
        }
    }

    private var actionBar: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                Button("Dry run") { state.run(dryRun: true) }
                    .disabled(!state.canSync)
                Button("Sync colours") { state.run(dryRun: false) }
                    .keyboardShortcut(.defaultAction)
                    .disabled(!state.canSync || state.rekordboxIsRunning)
                if state.isRunning {
                    Button("Cancel") { state.cancel() }
                    ProgressView(value: state.progress)
                        .progressViewStyle(.linear)
                        .frame(width: 160)
                }
                Spacer()
                Text(state.statusLine).font(.caption).foregroundStyle(.secondary)
            }
            if state.rekordboxIsRunning {
                Text("Quit Rekordbox to enable syncing. A dry run is always safe.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
            if let error = state.errorMessage {
                Label(error, systemImage: "xmark.octagon.fill")
                    .font(.caption)
                    .foregroundStyle(.red)
                    .textSelection(.enabled)
            }
        }
    }

    @ViewBuilder
    private var resultsSection: some View {
        if let result = state.result {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 14) {
                    statTile("Tracks", result.summary.collectionSize)
                    statTile("Matched", result.summary.matched)
                    statTile(result.dryRun ? "Would change" : "Changed",
                             result.dryRun ? result.summary.changes : result.applied)
                    statTile("Already correct", result.summary.alreadyCorrect)
                    statTile("Unmatched", result.summary.unmatched)
                }
                if let backup = result.backup {
                    Label("Backup: \(backup.directory)", systemImage: "shield.lefthalf.filled")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }
                if result.summary.overwritesExistingColor > 0 {
                    Label(
                        "\(result.summary.overwritesExistingColor.formatted()) tracks already had a different colour and \(result.dryRun ? "would be" : "were") recoloured.",
                        systemImage: "paintpalette"
                    )
                    .font(.caption)
                    .foregroundStyle(.secondary)
                }
                changesTable(result.changes)
            }
        } else {
            Spacer()
        }
    }

    private func statTile(_ label: String, _ value: Int) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value.formatted()).font(.title3).bold().monospacedDigit()
            Text(label).font(.caption2).foregroundStyle(.secondary)
        }
        .frame(minWidth: 84, alignment: .leading)
        .padding(10)
        .background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 8))
    }

    private func changesTable(_ changes: [TrackChange]) -> some View {
        Table(changes) {
            TableColumn("") { change in
                Text(Verdict(rawValue: change.verdict)?.symbol ?? "•")
            }
            .width(24)
            TableColumn("Artist") { Text($0.artist) }
            TableColumn("Title") { Text($0.title) }
            TableColumn("Colour") { change in
                Text("\(change.oldColor) → \(change.newColor)").monospacedDigit()
            }
            TableColumn("Match") { Text($0.matchKind.replacingOccurrences(of: "_", with: " ")) }
        }
        .frame(minHeight: 200)
    }

    private func chooseCSV() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [UTType.commaSeparatedText, UTType.plainText]
        panel.allowsMultipleSelection = false
        panel.message = "Choose your Spectro CSV export"
        if panel.runModal() == .OK { state.csvURL = panel.url }
    }

    private func chooseDatabase() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.message = "Choose a Rekordbox master.db"
        panel.directoryURL = URL(fileURLWithPath: NSHomeDirectory() + "/Library/Pioneer")
        if panel.runModal() == .OK { state.databaseOverride = panel.url }
    }
}
