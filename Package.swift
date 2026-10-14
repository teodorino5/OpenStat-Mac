// swift-tools-version: 5.9
import PackageDescription

let package = Package(
  name: "OpenStatMac",
  platforms: [.macOS(.v14)],
  products: [
    .executable(name: "OpenStatMac", targets: ["OpenStatApp"]),
    .executable(name: "OpenStatSmoke", targets: ["OpenStatSmoke"]),
    .library(name: "OpenStatCore", targets: ["OpenStatCore"]),
    .library(name: "EngineClient", targets: ["EngineClient"]),
  ],
  targets: [
    .target(name: "OpenStatCore"),
    .target(name: "EngineClient", dependencies: ["OpenStatCore"]),
    .executableTarget(
      name: "OpenStatApp", dependencies: ["OpenStatCore", "EngineClient"],
      path: "App", resources: [.copy("Resources")]),
    .executableTarget(
      name: "OpenStatSmoke", dependencies: ["OpenStatCore", "EngineClient"],
      path: "Tests/Smoke"),
    .testTarget(name: "OpenStatCoreTests", dependencies: ["OpenStatCore"]),
    .testTarget(name: "EngineClientTests", dependencies: ["EngineClient", "OpenStatCore"]),
  ]
)
