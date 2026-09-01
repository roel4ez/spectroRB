// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "SpectroRB",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "SpectroRB",
            path: "Sources/SpectroRB"
        )
    ]
)
