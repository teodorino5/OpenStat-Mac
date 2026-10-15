import AppKit
import OpenStatCore

/// Exercises real NSDocument windows without claiming a full accessibility or XCTest UI audit.
@MainActor
enum NativeSmoke {
  static func wait(line: UInt = #line, _ predicate: () -> Bool) async throws {
    for _ in 0..<150 {
      if predicate() { return }
      try await Task.sleep(nanoseconds: 100_000_000)
    }
    throw NSError(
      domain: "OpenStatNativeSmoke", code: 1,
      userInfo: [NSLocalizedDescriptionKey: "Wait timed out at line \(line)"])
  }
  static func run(controller: NSDocumentController, report: URL) async {
    var result: [String: Any] = ["passed": false]
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    defer {
      try? FileManager.default.removeItem(at: directory)
      let data = try? JSONSerialization.data(
        withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
      try? data?.write(to: report, options: .atomic)
      NSApp.terminate(nil)
    }
    do {
      guard let document = controller.documents.first as? OpenStatDocument else {
        throw NSError(domain: "OpenStatNativeSmoke", code: 2)
      }
      let model = document.model
      try await wait { model.dataset != nil && !model.busy && model.pages[0] != nil }
      guard model.errorKey == nil, model.dataset?.rowCount == 50,
        L.text("default.measurement") != "default.measurement",
        document.windowControllers.first?.window?.contentViewController != nil,
        document.windowControllers.first?.window?.tabbingMode == .preferred,
        document.windowControllers.first?.window?.toolbar != nil
      else {
        throw NSError(domain: "OpenStatNativeSmoke", code: 3)
      }
      model.edit(row: 0, column: 1, text: "1.25")
      try await wait { !model.busy && model.value(row: 0, column: 1) == .number(1.25) }
      document.undoManager?.undo()
      try await wait { model.value(row: 0, column: 1) == .null }
      document.undoManager?.redo()
      try await wait { model.value(row: 0, column: 1) == .number(1.25) }
      model.appendCase()
      try await wait { !model.busy && model.dataset?.rowCount == 51 && model.pages[0] != nil }
      guard model.value(row: 50, column: 1) == .null else { throw ArrowPageError.invalid }
      document.undoManager?.undo()
      try await wait { model.dataset?.rowCount == 50 && model.pages[0] != nil }
      document.undoManager?.redo()
      try await wait { model.dataset?.rowCount == 51 && model.pages[0] != nil }
      model.appendVariable(name: "Original integer", storage: "int64")
      try await wait { !model.busy && model.dataset?.fields.count == 4 && model.pages[0] != nil }
      model.edit(row: 0, column: 3, text: "9223372036854775807")
      try await wait { !model.busy && model.value(row: 0, column: 3) == .integer(Int64.max) }
      model.edit(row: 50, column: 1, text: "0.0")
      try await wait { !model.busy && model.value(row: 50, column: 1) == .number(0.0) }
      model.edit(row: 50, column: 1, text: "-0.0")
      try await wait {
        if case .number(let value) = model.value(row: 50, column: 1) {
          return !model.busy && value.bitPattern == 0x8000_0000_0000_0000
        }
        return false
      }
      try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
      let project = directory.appendingPathComponent("Original-native.openstat")
      try await withCheckedThrowingContinuation {
        (continuation: CheckedContinuation<Void, Error>) in
        document.save(to: project, ofType: "org.openstat.project", for: .saveAsOperation) { error in
          if let error { continuation.resume(throwing: error) } else { continuation.resume() }
        }
      }
      let reopened =
        try controller.makeDocument(withContentsOf: project, ofType: "org.openstat.project")
        as! OpenStatDocument
      controller.addDocument(reopened)
      reopened.makeWindowControllers()
      try await wait {
        reopened.model.dataset != nil && reopened.model.pages[0] != nil && !reopened.model.busy
      }
      guard reopened.model.value(row: 0, column: 1) == .number(1.25),
        reopened.model.value(row: 0, column: 3) == .integer(Int64.max),
        reopened.model.dataset?.rowCount == 51, reopened.model.errorKey == nil
      else {
        throw NSError(domain: "OpenStatNativeSmoke", code: 4)
      }
      guard case .number(let savedZero) = reopened.model.value(row: 50, column: 1),
        savedZero.bitPattern == 0x8000_0000_0000_0000
      else { throw ArrowPageError.invalid }
      guard let measure = model.dataset?.fields[1].id else { throw ArrowPageError.invalid }
      model.transform(
        method: "columns.compute",
        parameters: [
          "name": .string("Original shifted"),
          "expression": .object([
            "op": .string("add"),
            "args": .array([
              .object(["field": .string(measure)]), .object(["constant": .number(2.0)]),
            ]),
          ]),
        ])
      try await wait { !model.busy && model.dataset?.fields.count == 5 && model.pages[0] != nil }
      guard model.value(row: 0, column: 4) == .number(3.25),
        model.value(row: 50, column: 4) == .number(2.0)
      else { throw ArrowPageError.invalid }
      document.undoManager?.undo()
      try await wait { model.dataset?.fields.count == 4 && model.pages[0] != nil }
      let classID = UUID().uuidString
      model.transform(
        method: "classification.intervals",
        parameters: [
          "source": .string(measure),
          "output": .object([
            "id": .string(classID), "name": .string("Original class"),
            "storage": .string("string"), "measurement": .string("ordinal"),
          ]),
          "classes": .array([
            .object([
              "label": .string("nonpositive"), "lower": .null, "upper": .number(0.0),
              "include_lower": .bool(false), "include_upper": .bool(true),
            ]),
            .object([
              "label": .string("positive"), "lower": .number(0.0), "upper": .null,
              "include_lower": .bool(false), "include_upper": .bool(false),
            ]),
          ]),
        ])
      try await wait { !model.busy && model.dataset?.fields.count == 5 && model.pages[0] != nil }
      guard model.value(row: 0, column: 4) == .string("positive"),
        model.value(row: 50, column: 4) == .string("nonpositive")
      else { throw ArrowPageError.invalid }
      document.undoManager?.undo()
      try await wait { model.dataset?.fields.count == 4 && model.pages[0] != nil }
      model.inspect(method: "dataset.missing_audit", parameters: [:])
      try await wait { !model.busy && model.summary != nil }
      guard model.summary?.object["total_cases"]?.int == 51,
        model.summary?.object["fields"]?.object[measure]?.object["valid"]?.int == 2
      else { throw ArrowPageError.invalid }
      let beforeSort = model.dataset?.revision
      model.transform(
        method: "dataset.sort",
        parameters: [
          "keys": .array([
            .object(["field": .string(measure), "ascending": .bool(false)])
          ])
        ])
      try await wait {
        !model.busy && model.dataset?.revision != beforeSort && model.pages[0] != nil
      }
      guard model.rowID(for: 1) == 50 else { throw ArrowPageError.invalid }
      document.undoManager?.undo()
      try await wait { model.dataset?.revision == beforeSort && model.pages[0] != nil }
      model.transform(
        method: "dataset.filter",
        parameters: [
          "condition": .object([
            "op": .string("not"),
            "args": .array([.object(["op": .string("is_missing"), "field": .string(measure)])]),
          ])
        ])
      try await wait { !model.busy && model.dataset?.rowCount == 2 && model.pages[0] != nil }
      guard model.rowID(for: 1) == 50 else { throw ArrowPageError.invalid }
      model.edit(row: 1, column: 1, text: "2.5")
      try await wait { !model.busy && model.value(row: 1, column: 1) == .number(2.5) }
      let filteredProject = directory.appendingPathComponent("Original-filtered.openstat")
      try await model.save(to: filteredProject)
      let filteredDocument =
        try controller.makeDocument(
          withContentsOf: filteredProject,
          ofType: "org.openstat.project") as! OpenStatDocument
      controller.addDocument(filteredDocument)
      filteredDocument.makeWindowControllers()
      try await wait { !filteredDocument.model.busy && filteredDocument.model.pages[0] != nil }
      guard filteredDocument.model.rowID(for: 1) == 50,
        filteredDocument.model.value(row: 1, column: 1) == .number(2.5)
      else { throw ArrowPageError.invalid }
      filteredDocument.close()
      document.undoManager?.undo()
      try await wait { model.value(row: 1, column: 1) == .number(-0.0) && model.pages[0] != nil }
      document.undoManager?.undo()
      try await wait { model.dataset?.rowCount == 51 && model.pages[0] != nil }
      let csv = directory.appendingPathComponent("Original-localized.csv")
      try "Identifier;Value\ncase-one;1,25\n".write(to: csv, atomically: true, encoding: .utf8)
      model.performImport(url: csv, delimiter: ";", decimalPoint: ",")
      try await wait { !model.busy && model.dataset?.rowCount == 1 && model.pages[0] != nil }
      guard model.value(row: 0, column: 1) == .number(1.25),
        model.dataset?.fields.contains(where: { $0.id == model.selectedField }) == true
      else { throw ArrowPageError.invalid }
      document.undoManager?.undo()
      try await wait { model.dataset?.rowCount == 51 && model.pages[0] != nil }
      guard model.dataset?.fields.contains(where: { $0.id == model.selectedField }) == true
      else { throw ArrowPageError.invalid }
      result = [
        "passed": true, "windows": controller.documents.count,
        "checks": [
          "native_window", "native_toolbar", "engine_start", "arrow_viewport", "typed_edit", "undo",
          "redo",
          "document_save",
          "document_reopen", "append_case", "append_variable", "int64_precision",
          "negative_zero_edit", "localized_csv_import", "undo_import", "managed_jobs",
          "safe_compute", "interval_classification", "missing_audit", "stable_sort",
          "stable_filter",
          "edit_filtered_case_id", "filtered_project_reopen",
        ],
        "localized_measurement": L.text("default.measurement"),
        "scope": "Native integration smoke only; full UI/accessibility tests are pending",
      ]
      if let view = document.windowControllers.first?.window?.contentView,
        let bitmap = view.bitmapImageRepForCachingDisplay(in: view.bounds)
      {
        view.cacheDisplay(in: view.bounds, to: bitmap)
        if let data = bitmap.representation(using: .png, properties: [:]) {
          try data.write(to: report.deletingPathExtension().appendingPathExtension("png"))
        }
      }
      reopened.close()
      document.close()
    } catch {
      result["error"] = String(describing: error)
    }
  }
}
