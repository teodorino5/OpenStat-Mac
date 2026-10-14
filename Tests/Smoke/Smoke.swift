import EngineClient
import Foundation
import OpenStatCore

/// A contributor check for CLT-only machines; it does not replace XCTest or UI tests.
@main
struct Smoke {
  static func expect(_ condition: Bool, _ message: String) throws {
    if !condition {
      throw NSError(
        domain: "OpenStatSmoke", code: 1,
        userInfo: [NSLocalizedDescriptionKey: message])
    }
  }
  static func main() async throws {
    let precise = JSONValue.number(1.2345678901234567)
    let preciseText = precise.display(locale: Locale(identifier: "cs_CZ"))
    try expect(
      try CellParser.parse(preciseText, storage: "float64", locale: Locale(identifier: "cs_CZ"))
        == precise,
      "Editing display lost significant digits")
    let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    let source = root.appendingPathComponent("engine/src")
    let python = root.appendingPathComponent("engine/.venv/bin/python")
    let connection = try EngineConnection(python: python, engineSource: source)
    defer { connection.close() }

    let hello = try await connection.call("engine.hello")
    try expect(hello.object["protocol_major"]?.int == 1, "Handshake failed")
    try expect(hello.object["analysis_methods"]?.array.isEmpty == true, "Premature analysis claim")
    let fields = JSONValue.array([
      .object([
        "id": .string("measurement"), "name": .string("Original measurement"),
        "storage": .string("float64"), "measurement": .string("continuous"),
      ]),
      .object([
        "id": .string("group"), "name": .string("Original group"),
        "storage": .string("string"), "measurement": .string("nominal"),
      ]),
    ])
    let created = try await connection.call(
      "dataset.create",
      [
        "name": .string("Original study"), "fields": fields,
        "rows": .array([
          .array([.number(2.5), .string("blue")]),
          .array([.null, .string("red")]),
        ]), "context": .string("sample"),
      ])
    let revision = created.object["revision"]!.string
    let edited = try await connection.call(
      "dataset.edit",
      [
        "revision": .string(revision), "row": .integer(0),
        "field": .string("measurement"), "value": .number(7.25),
      ])
    let newRevision = edited.object["revision"]!.string
    let oldPage = try await connection.call("dataset.page", ["revision": .string(revision)])
    try expect(
      oldPage.object["rows"]?.array.first?.array.first == .number(2.5), "Edit mutated old revision")
    let descriptor = try JSONDecoder().decode(Dataset.self, from: JSONEncoder().encode(edited))
    let page = try await connection.page(dataset: descriptor, offset: 0, limit: 128)
    try expect(page.rows[0][0] == .number(7.25), "Arrow edit not visible")
    let cache = URL(fileURLWithPath: hello.object["artifact_directory"]!.string)
    try expect(
      try FileManager.default.contentsOfDirectory(atPath: cache.path).allSatisfy {
        !$0.hasSuffix(".arrow")
      }, "Arrow artifact was not released")
    try ArrowSmoke.run(root: root)
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    defer { try? FileManager.default.removeItem(at: directory) }
    let project = directory.appendingPathComponent("Original česky.openstat")
    _ = try await connection.call(
      "project.save", ["revision": .string(newRevision), "path": .string(project.path)])
    let opened = try await connection.call("project.open", ["path": .string(project.path)])
    try expect(opened.object["revision"]?.string == newRevision, "Save/open changed revision")
    let reopenedPage = try await connection.call("dataset.page", ["revision": .string(newRevision)])
    try expect(
      reopenedPage.object["rows"]?.array.map(\.array) == page.rows, "Save/open changed cell values")

    let extended = try await connection.call(
      "dataset.extend",
      [
        "revision": .string(newRevision), "rows": .integer(1),
        "fields": .array([
          .object([
            "id": .string("flag"), "name": .string("Original flag"),
            "storage": .string("bool"), "measurement": .string("binary"),
          ])
        ]),
      ])
    let extendedDataset = try JSONDecoder().decode(
      Dataset.self, from: JSONEncoder().encode(extended))
    let extendedPage = try await connection.page(dataset: extendedDataset, offset: 0, limit: 128)
    try expect(
      extendedDataset.rowCount == 3 && extendedDataset.fields.count == 3,
      "Appending cases/variables changed descriptor")
    try expect(
      extendedPage.rows[0] == [.number(7.25), .string("blue"), .null]
        && extendedPage.rows[2] == [.null, .null, .null],
      "Appending cases/variables changed old values")

    let negativeZero = try await connection.call(
      "dataset.edit",
      [
        "revision": .string(extendedDataset.revision), "row": .integer(0),
        "field": .string("measurement"), "value": .number(-0.0),
      ])
    let zeroDataset = try JSONDecoder().decode(
      Dataset.self, from: JSONEncoder().encode(negativeZero))
    let zeroPage = try await connection.page(dataset: zeroDataset, offset: 0, limit: 128)
    guard case .number(let zero) = zeroPage.rows[0][0] else { throw ArrowPageError.invalid }
    try expect(zero.bitPattern == 0x8000_0000_0000_0000, "JSON-RPC lost negative zero")

    let started = try await connection.call(
      "jobs.submit",
      [
        "method": .string("dataset.filter"),
        "parameters": .object([
          "revision": .string(extendedDataset.revision),
          "condition": .object(["op": .string("is_null"), "field": .string("measurement")]),
        ]),
      ])
    let job = started.object["job"]!.string
    var completed: JSONValue?
    for _ in 0..<100 {
      let status = try await connection.call("jobs.status", ["job": .string(job)])
      if status.object["state"]?.string == "succeeded" {
        completed = status.object["result"]
        break
      }
      if status.object["state"]?.string == "failed" { throw RPCError.protocolFailure }
      try await Task.sleep(nanoseconds: 20_000_000)
    }
    guard let completed else { throw RPCError.timeout }
    let subset = try JSONDecoder().decode(Dataset.self, from: JSONEncoder().encode(completed))
    let subsetPage = try await connection.page(dataset: subset, offset: 0, limit: 128)
    try expect(subsetPage.rowIDs == [1, 2], "Filtered Arrow case identities changed")
    for format in ["json", "parquet", "sqlite", "xlsx"] {
      let path = directory.appendingPathComponent("Original-interchange.\(format)")
      _ = try await connection.call(
        "dataset.export_\(format)",
        ["revision": .string(subset.revision), "path": .string(path.path)])
      let imported = try await connection.call(
        "dataset.import_\(format)", ["path": .string(path.path)])
      let importedDataset = try JSONDecoder().decode(
        Dataset.self, from: JSONEncoder().encode(imported))
      let importedPage = try await connection.page(dataset: importedDataset, offset: 0, limit: 128)
      try expect(
        importedPage.rowIDs == subsetPage.rowIDs && importedPage.rows == subsetPage.rows,
        "\(format) roundtrip changed values or case IDs")
    }

    let unicode = JSONValue.object(["label": .string("česky")])
    var decoder = FrameDecoder()
    var decoded: [Data] = []
    for byte in try RPCFrame.encode(unicode) { decoded += try decoder.append(Data([byte])) }
    try expect(decoded.count == 1, "Partial frame handling failed")
    try expect(
      try JSONDecoder().decode(JSONValue.self, from: decoded[0]) == unicode,
      "Unicode framing failed")
    let integer = JSONValue.integer(9_007_199_254_740_993)
    try expect(
      try JSONDecoder().decode(JSONValue.self, from: JSONEncoder().encode(integer)) == integer,
      "Integer precision lost")
    let localized = try CellParser.parse(
      "1,25", storage: "float64", locale: Locale(identifier: "cs_CZ"))
    try expect(localized == .number(1.25), "Czech decimal parsing failed")
    do {
      _ = try await connection.call("dataset.page", ["revision": .string("unknown")])
      throw NSError(domain: "OpenStatSmoke", code: 2)
    } catch RPCError.engine(let key) {
      try expect(key == "error.stale_revision", "Domain error mismatch")
    }
    _ = try await connection.call("engine.shutdown")
    print(
      "PASS: Arrow IPC types/precision/corruption, artifact cleanup, Swift/Python RPC, Unicode framing, typed cells, immutable edits, Czech decimals and project save/reopen."
    )
  }
}
