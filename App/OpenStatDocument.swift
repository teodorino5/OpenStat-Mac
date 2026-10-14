import AppKit
import SwiftUI

@MainActor
final class OpenStatDocument: NSDocument {
  let model = DocumentModel()
  private let opening = OpeningLocation()
  private var toolbarOwner: NativeToolbar?
  override init() {
    super.init()
    model.document = self
    hasUndoManager = true
    undoManager?.groupsByEvent = false
  }
  override class var autosavesInPlace: Bool { true }
  override func read(from url: URL, ofType typeName: String) throws {
    guard FileManager.default.fileExists(atPath: url.appendingPathComponent("manifest.json").path)
    else { throw CocoaError(.fileReadCorruptFile) }
    opening.set(url)
  }
  override func makeWindowControllers() {
    let view = MainView(model: model)
    let window = NSWindow(contentViewController: NSHostingController(rootView: view))
    window.setContentSize(NSSize(width: 1180, height: 740))
    window.minSize = NSSize(width: 850, height: 540)
    window.tabbingMode = .preferred
    window.title = L.text("app.name")
    toolbarOwner = NativeToolbar(document: self)
    window.toolbar = toolbarOwner?.makeToolbar()
    addWindowController(NSWindowController(window: window))
    Task { await model.bootstrap(opening: opening.get()) }
  }
  override func save(
    to url: URL, ofType typeName: String, for saveOperation: NSDocument.SaveOperationType,
    completionHandler: @escaping (Error?) -> Void
  ) {
    let token = changeCountToken(for: saveOperation)
    Task {
      do {
        try await model.save(to: url)
        if saveOperation == .saveOperation || saveOperation == .saveAsOperation {
          fileURL = url
          fileType = typeName
        }
        updateChangeCount(withToken: token, for: saveOperation)
        completionHandler(nil)
      } catch {
        let key = (error as? LocalizedError)?.errorDescription ?? "error.file_io"
        completionHandler(
          NSError(
            domain: "org.openstat.document", code: 1,
            userInfo: [NSLocalizedDescriptionKey: L.text(key)]))
      }
    }
  }
  override func close() {
    model.close()
    super.close()
  }
}

@MainActor
final class OpenStatDocumentController: NSDocumentController {
  override var defaultType: String? { "org.openstat.project" }
  override func documentClass(forType typeName: String) -> AnyClass? { OpenStatDocument.self }
}

private final class OpeningLocation: @unchecked Sendable {
  private let lock = NSLock()
  private var value: URL?
  func set(_ url: URL) {
    lock.lock()
    defer { lock.unlock() }
    value = url
  }
  func get() -> URL? {
    lock.lock()
    defer { lock.unlock() }
    return value
  }
}
