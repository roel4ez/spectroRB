import Foundation

/// Decoded newline-delimited JSON events emitted by the Python core.
enum CoreEvent {
    case csvLoaded(rows: Int, skipped: Int, verdicts: [String: Int])
    case databaseFound(path: String, source: String, modified: String)
    case backupCreated(directory: String, bytes: Int)
    case collectionLoaded(tracks: Int)
    case planReady(summary: Summary)
    case applying(applied: Int, total: Int)
    case applied(applied: Int)
    case result(SyncResult)
    case failure(kind: String, message: String)
    case unknown(String)
}

struct Summary: Decodable {
    var collectionSize: Int = 0
    var csvRows: Int = 0
    var verdictCounts: [String: Int] = [:]
    var matched: Int = 0
    var changes: Int = 0
    var alreadyCorrect: Int = 0
    var overwritesExistingColor: Int = 0
    var unmatched: Int = 0
    var ambiguous: Int = 0
    var skippedRows: Int = 0

    enum CodingKeys: String, CodingKey {
        case collectionSize = "collection_size"
        case csvRows = "csv_rows"
        case verdictCounts = "verdict_counts"
        case matched
        case changes
        case alreadyCorrect = "already_correct"
        case overwritesExistingColor = "overwrites_existing_color"
        case unmatched
        case ambiguous
        case skippedRows = "skipped_rows"
    }
}

struct DatabaseInfo: Decodable {
    let path: String
    let source: String
    let version: String?
    let size: Int
    let modified: String
}

struct BackupInfo: Decodable {
    let directory: String
    let files: [String]
    let bytes: Int
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case directory, files, bytes
        case createdAt = "created_at"
    }
}

struct TrackChange: Decodable, Identifiable {
    let contentId: String
    let title: String
    let artist: String
    let path: String
    let verdict: String
    let oldColor: String
    let newColor: String
    let matchKind: String

    var id: String { contentId }

    enum CodingKeys: String, CodingKey {
        case contentId = "content_id"
        case title, artist, path, verdict
        case oldColor = "old_color"
        case newColor = "new_color"
        case matchKind = "match_kind"
    }
}

struct UnmatchedRow: Decodable, Identifiable {
    let path: String
    let filename: String
    let verdict: String
    var id: String { path }
}

struct SyncResult: Decodable {
    let database: DatabaseInfo
    let csv: String
    let dryRun: Bool
    let applied: Int
    let backup: BackupInfo?
    let summary: Summary
    let changes: [TrackChange]
    let unmatched: [UnmatchedRow]

    enum CodingKeys: String, CodingKey {
        case database, csv, applied, backup, summary, changes, unmatched
        case dryRun = "dry_run"
    }
}

struct DoctorReport: Decodable {
    let version: String
    let databases: [DatabaseInfo]
    let rekordboxProcesses: [String]
    let backups: [String]

    enum CodingKeys: String, CodingKey {
        case version, databases, backups
        case rekordboxProcesses = "rekordbox_processes"
    }
}

enum Verdict: String, CaseIterable {
    case lossless = "LOSSLESS"
    case medium = "MEDIUM"
    case fake = "FAKE"

    var symbol: String {
        switch self {
        case .lossless: return "🟢"
        case .medium: return "🟡"
        case .fake: return "🔴"
        }
    }

    var colorName: String {
        switch self {
        case .lossless: return "Green"
        case .medium: return "Yellow"
        case .fake: return "Red"
        }
    }
}
