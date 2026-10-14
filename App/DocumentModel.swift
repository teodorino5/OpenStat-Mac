import AppKit
import EngineClient
import OpenStatCore
import SwiftUI
import UniformTypeIdentifiers

@MainActor
final class DocumentModel: ObservableObject {
  @Published var dataset: Dataset?
  @Published var pages: [Int: DataPage] = [:]
  @Published var busy = false
  @Published var errorKey: String?
  @Published var selectedField = ""
  @Published var importSource: URL?
  @Published var showingNewVariable = false
  @Published var showingClassification = false
  @Published var showingColumns = false
  @Published var showingCases = false
  @Published var showingCodebook = false
  @Published var showingOutliers = false
  @Published var showingExport = false
  @Published var summary: JSONValue?
  @Published var jobProgress: Double?
  @Published var selectedRowIDs = Set<Int>()
  private var activeJob: String?
  weak var document: OpenStatDocument?
  private var engine: EngineConnection?
  private var loading = Set<Int>()
  let pageSize = 128

  func bootstrap(opening url: URL?) async {
    busy = true
    defer { busy = false }
    do {
      let configURL = Bundle.main.resourceURL?.appendingPathComponent("development-runtime.json")
      let config: [String: String]
      if let configURL, let data = try? Data(contentsOf: configURL) {
        config = try JSONDecoder().decode([String: String].self, from: data)
      } else {
        let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        config = [
          "python": root.appendingPathComponent("engine/.venv/bin/python").path,
          "source": root.appendingPathComponent("engine/src").path,
        ]
      }
      guard let python = config["python"], let source = config["source"],
        FileManager.default.isExecutableFile(atPath: python)
      else { throw RPCError.unavailable }
      engine = try EngineConnection(
        python: URL(fileURLWithPath: python),
        engineSource: URL(fileURLWithPath: source))
      _ = try await engine!.call("engine.hello")
      if let url {
        let value = try await execute("project.open", ["path": .string(url.path)])
        try accept(value)
      } else {
        let names = [
          L.text("default.observation"), L.text("default.measurement"), L.text("default.group"),
        ]
        let fields: [JSONValue] = [
          .object([
            "id": .string(UUID().uuidString), "name": .string(names[0]),
            "storage": .string("string"), "measurement": .string("nominal"),
            "role": .string("identifier"),
          ]),
          .object([
            "id": .string(UUID().uuidString), "name": .string(names[1]),
            "storage": .string("float64"), "measurement": .string("continuous"),
          ]),
          .object([
            "id": .string(UUID().uuidString), "name": .string(names[2]),
            "storage": .string("string"), "measurement": .string("nominal"),
          ]),
        ]
        let rows = (0..<50).map { _ in JSONValue.array([.null, .null, .null]) }
        try accept(
          try await execute(
            "dataset.create",
            [
              "name": .string(L.text("dataset.untitled")), "fields": .array(fields),
              "rows": .array(rows),
            ]))
      }
      await loadPage(0)
    } catch { report(error) }
  }

  private func execute(_ method: String, _ parameters: [String: JSONValue]) async throws
    -> JSONValue
  {
    guard let engine else { throw RPCError.unavailable }
    jobProgress = nil
    let started = try await engine.call(
      "jobs.submit", ["method": .string(method), "parameters": .object(parameters)])
    guard let identifier = started.object["job"]?.string, !identifier.isEmpty else {
      throw RPCError.protocolFailure
    }
    activeJob = identifier
    defer {
      activeJob = nil
      jobProgress = nil
    }
    do {
      while !Task.isCancelled {
        let response = try await engine.call("jobs.status", ["job": .string(identifier)])
        let progress = response.object["progress"]?.object ?? [:]
        if (progress["total"]?.int ?? 0) > 0 {
          if case .number(let value) = progress["fraction"] {
            jobProgress = value
          } else if case .integer(let value) = progress["fraction"] {
            jobProgress = Double(value)
          }
        } else {
          jobProgress = nil
        }
        switch response.object["state"]?.string {
        case "succeeded":
          guard let result = response.object["result"] else { throw RPCError.protocolFailure }
          return result
        case "failed", "cancelled":
          throw RPCError.engine(
            response.object["error"]?.object["key"]?.string ?? "error.engine_internal")
        case "queued", "running": break
        default: throw RPCError.protocolFailure
        }
        try await Task.sleep(nanoseconds: 80_000_000)
      }
      throw CancellationError()
    } catch {
      if error is CancellationError {
        _ = try? await engine.call("jobs.cancel", ["job": .string(identifier)])
      }
      throw error
    }
  }

  func cancelOperation() {
    guard let engine, let activeJob else { return }
    Task {
      do { _ = try await engine.call("jobs.cancel", ["job": .string(activeJob)]) } catch {
        report(error)
      }
    }
  }

  private func accept(_ value: JSONValue) throws {
    dataset = try JSONDecoder().decode(Dataset.self, from: JSONEncoder().encode(value))
    pages.removeAll()
    summary = nil
    selectedRowIDs.removeAll()
    loading.removeAll()
    if dataset?.fields.contains(where: { $0.id == selectedField }) != true {
      selectedField = dataset?.fields.first?.id ?? ""
    }
  }

  func loadPage(_ row: Int) async {
    guard let dataset, let engine else { return }
    let offset = row / pageSize * pageSize
    guard pages[offset] == nil, !loading.contains(offset) else { return }
    let revision = dataset.revision
    loading.insert(offset)
    defer { loading.remove(offset) }
    do {
      let page = try await engine.page(dataset: dataset, offset: offset, limit: pageSize)
      guard self.dataset?.revision == revision else { return }
      // Bounded viewport cache: at most eight pages, never one object per source row.
      if pages.count >= 8, let oldest = pages.keys.max(by: { abs($0 - offset) < abs($1 - offset) })
      {
        pages.removeValue(forKey: oldest)
      }
      pages[offset] = page
    } catch { report(error) }
  }

  func value(row: Int, column: Int) -> JSONValue? {
    let offset = row / pageSize * pageSize
    guard let page = pages[offset], row - offset < page.rows.count,
      column < page.rows[row - offset].count
    else { return nil }
    return page.rows[row - offset][column]
  }

  func rowID(for row: Int) -> Int? {
    let offset = row / pageSize * pageSize
    guard let page = pages[offset], row >= offset, row - offset < page.rowIDs.count else {
      return nil
    }
    return page.rowIDs[row - offset]
  }

  func edit(row: Int, column: Int, text: String) {
    guard !busy, let old = dataset, engine != nil, column < old.fields.count,
      let identifier = rowID(for: row)
    else { return }
    do {
      guard text != self.value(row: row, column: column)?.display() else { return }
      let value = try CellParser.parse(text, storage: old.fields[column].storage, locale: .current)
      let previous = self.value(row: row, column: column)
      if case .number(let proposed) = value, case .number(let existing) = previous {
        guard proposed.bitPattern != existing.bitPattern else { return }
      } else {
        guard value != previous else { return }
      }
      runChange(old: old) {
        try await self.execute(
          "dataset.edit",
          [
            "revision": .string(old.revision),
            "row": .integer(Int64(identifier)), "field": .string(old.fields[column].id),
            "value": value,
          ])
      }
    } catch {
      report(error)
      pages = pages
    }
  }

  func transform(method: String, parameters: [String: JSONValue]) {
    guard !busy, let old = dataset, engine != nil else { return }
    var arguments = parameters
    arguments["revision"] = .string(old.revision)
    runChange(old: old) { try await self.execute(method, arguments) }
  }

  func inspect(method: String, parameters: [String: JSONValue]) {
    guard !busy, let dataset, engine != nil else { return }
    busy = true
    summary = nil
    Task {
      defer { busy = false }
      do {
        var arguments = parameters
        arguments["revision"] = .string(dataset.revision)
        let result = try await execute(method, arguments)
        guard self.dataset?.revision == dataset.revision else { return }
        summary = result
      } catch { report(error) }
    }
  }

  func updateField(_ index: Int, key: String, value: String) {
    guard !busy, var proposed = dataset, engine != nil else { return }
    guard index >= 0, index < proposed.fields.count else { return }
    switch key {
    case "name": proposed.fields[index].name = value
    case "role": proposed.fields[index].role = value
    case "measurement": proposed.fields[index].measurement = value
    default: return
    }
    updateMetadata(proposed)
  }

  func updateCodebook(
    fieldID: String, levels: [String], missingCodes: [String], labels: [String: String]
  ) {
    guard !busy, var proposed = dataset, engine != nil,
      let index = proposed.fields.firstIndex(where: { $0.id == fieldID })
    else { return }
    proposed.fields[index].levels = levels
    proposed.fields[index].missingCodes = missingCodes
    proposed.fields[index].valueLabels = labels
    updateMetadata(proposed)
  }

  func updateContext(_ value: String) {
    guard !busy, var proposed = dataset, engine != nil else { return }
    proposed.context = value
    updateMetadata(proposed)
  }

  func updateUnit(_ value: String) {
    guard !busy, var proposed = dataset, engine != nil else { return }
    proposed.observationUnit = value
    updateMetadata(proposed)
  }

  private func updateMetadata(_ proposed: Dataset) {
    guard let old = dataset else { return }
    let fields =
      (try? JSONDecoder().decode(JSONValue.self, from: JSONEncoder().encode(proposed.fields)))
      ?? .array([])
    runChange(old: old) {
      try await self.execute(
        "dataset.metadata",
        [
          "revision": .string(old.revision),
          "fields": fields, "context": .string(proposed.context),
          "observation_unit": .string(proposed.observationUnit),
        ])
    }
  }

  private func runChange(old: Dataset, operation: @escaping () async throws -> JSONValue) {
    busy = true
    Task {
      defer { busy = false }
      do {
        try accept(try await operation())
        if let undoManager = document?.undoManager {
          undoManager.beginUndoGrouping()
          undoManager.registerUndo(withTarget: self) { target in target.restore(old) }
          undoManager.setActionName(L.text("action.edit"))
          undoManager.endUndoGrouping()
        }
        document?.updateChangeCount(.changeDone)
        await loadPage(0)
      } catch { report(error) }
    }
  }

  private func restore(_ old: Dataset) {
    guard let current = dataset else { return }
    document?.undoManager?.registerUndo(withTarget: self) { target in target.restore(current) }
    dataset = old
    summary = nil
    selectedRowIDs.removeAll()
    if !old.fields.contains(where: { $0.id == selectedField }) {
      selectedField = old.fields.first?.id ?? ""
    }
    loading.removeAll()
    pages.removeAll()
    document?.updateChangeCount(.changeDone)
    Task { await loadPage(0) }
  }

  func importCSV() {
    let panel = NSOpenPanel()
    panel.allowedContentTypes = [
      .commaSeparatedText, .tabSeparatedText, .plainText,
      .json, UTType(filenameExtension: "parquet") ?? .data,
      UTType(filenameExtension: "sqlite") ?? .database,
      UTType(filenameExtension: "xlsx") ?? .spreadsheet,
      UTType(filenameExtension: "sav") ?? .data,
      UTType(filenameExtension: "dta") ?? .data,
      UTType(filenameExtension: "sas7bdat") ?? .data,
    ]
    panel.canChooseDirectories = false
    guard panel.runModal() == .OK, let url = panel.url, dataset != nil, engine != nil, !busy else {
      return
    }
    let formats = [
      "json": "json", "parquet": "parquet", "sqlite": "sqlite", "db": "sqlite", "xlsx": "xlsx",
      "sav": "sav", "dta": "dta", "sas7bdat": "sas7bdat",
    ]
    if let format = formats[url.pathExtension.lowercased()], let old = dataset {
      runChange(old: old) {
        try await self.execute("dataset.import_\(format)", ["path": .string(url.path)])
      }
    } else {
      importSource = url
    }
  }

  func performImport(url: URL, delimiter: String, decimalPoint: String) {
    guard !busy, let old = dataset, engine != nil else { return }
    importSource = nil
    runChange(old: old) {
      try await self.execute(
        "dataset.importCSV",
        [
          "path": .string(url.path), "delimiter": .string(delimiter),
          "decimal_point": .string(decimalPoint),
        ])
    }
  }

  func exportData(format: String, delimiter: String, decimalPoint: String) {
    guard !busy, let dataset, engine != nil,
      ["csv", "tsv", "json", "parquet", "sqlite", "xlsx", "sav", "dta"].contains(format)
    else { return }
    let panel = NSSavePanel()
    panel.canCreateDirectories = true
    panel.allowedContentTypes = [UTType(filenameExtension: format) ?? .data]
    panel.nameFieldStringValue =
      "\(dataset.name.replacingOccurrences(of: "/", with: "-" )).\(format)"
    guard panel.runModal() == .OK, let url = panel.url else { return }
    busy = true
    summary = nil
    Task {
      defer { busy = false }
      do {
        var parameters: [String: JSONValue] = [
          "revision": .string(dataset.revision), "path": .string(url.path),
          "overwrite": .bool(true),
        ]
        let method = format == "tsv" ? "csv" : format
        if method == "csv" {
          parameters["delimiter"] = .string(format == "tsv" ? "\t" : delimiter)
          parameters["decimal_point"] = .string(decimalPoint)
        }
        summary = try await execute("dataset.export_\(method)", parameters)
      } catch { report(error) }
    }
  }

  func deleteSelectedCases() {
    guard !selectedRowIDs.isEmpty else { return }
    transform(
      method: "dataset.delete_cases",
      parameters: ["row_ids": .array(selectedRowIDs.sorted().map { .integer(Int64($0)) })])
  }

  func dropSelectedVariable() {
    guard let dataset, dataset.fields.count > 1, !selectedField.isEmpty else { return }
    transform(
      method: "dataset.drop_fields", parameters: ["fields": .array([.string(selectedField)])])
  }

  func appendCase() {
    guard !busy, let old = dataset, engine != nil else { return }
    runChange(old: old) {
      try await self.execute(
        "dataset.extend", ["revision": .string(old.revision), "rows": .integer(1)])
    }
  }

  func appendVariable(name: String, storage: String) {
    guard !busy, let old = dataset, engine != nil else { return }
    let measurement: String
    switch storage {
    case "float64": measurement = "continuous"
    case "int64": measurement = "discrete"
    case "bool": measurement = "binary"
    case "multiple_response": measurement = "multiple_response"
    default: measurement = "nominal"
    }
    showingNewVariable = false
    runChange(old: old) {
      try await self.execute(
        "dataset.extend",
        [
          "revision": .string(old.revision),
          "fields": .array([
            .object([
              "id": .string(UUID().uuidString), "name": .string(name),
              "storage": .string(storage), "measurement": .string(measurement),
            ])
          ]),
        ])
    }
  }

  func save(to url: URL) async throws {
    guard !busy, let dataset, engine != nil else { throw RPCError.engine("error.busy") }
    _ = try await execute(
      "project.save", ["revision": .string(dataset.revision), "path": .string(url.path)])
  }
  func report(_ error: Error) {
    if let key = (error as? LocalizedError)?.errorDescription, key.hasPrefix("error.") {
      errorKey = key
    } else if error is CocoaError {
      errorKey = "error.file_io"
    } else {
      errorKey = "error.value_type"
    }
  }
  func close() { engine?.close() }
}
