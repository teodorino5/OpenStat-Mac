import CryptoKit
import Foundation
import OpenStatCore

extension EngineConnection {
  /// Decode bounded files off the UI actor and release the handle on success or failure.
  public func page(dataset: Dataset, offset: Int, limit: Int) async throws -> DataPage {
    guard offset >= 0, limit > 0, limit <= 512, dataset.rowCount >= 0 else {
      throw ArrowPageError.limit
    }
    let hello = try await call("engine.hello")
    guard hello.object["ui_transport"]?.string == "arrow_ipc_file",
      let directory = hello.object["artifact_directory"]?.string
    else { throw RPCError.protocolFailure }
    let result = try await call(
      "dataset.page",
      [
        "revision": .string(dataset.revision), "offset": .integer(Int64(offset)),
        "limit": .integer(Int64(limit)), "format": .string("arrow"),
      ])
    let artifact = result.object["artifact"]?.object ?? [:]
    guard let handle = artifact["handle"]?.string,
      UUID(uuidString: handle)?.uuidString.lowercased() == handle
    else { throw ArrowPageError.artifact }
    do {
      guard result.object["revision"]?.string == dataset.revision,
        result.object["offset"]?.int == offset, result.object["format"]?.string == "arrow",
        let count = result.object["count"]?.int,
        count == min(limit, max(0, dataset.rowCount - offset)),
        result.object["fields"]?.array == dataset.fields.map({ .string($0.id) }),
        let path = artifact["path"]?.string, let checksum = artifact["sha256"]?.string,
        let size = artifact["bytes"]?.int, size > 0, size <= ArrowPageReader.maximumBytes
      else { throw ArrowPageError.invalid }
      let rowIDs = try (result.object["row_ids"]?.array ?? []).map { value -> Int in
        guard case .integer(let identifier) = value, let row = Int(exactly: identifier), row >= 0
        else { throw ArrowPageError.invalid }
        return row
      }
      guard rowIDs.count == count, Set(rowIDs).count == count else { throw ArrowPageError.invalid }
      let page = try await Task.detached {
        let folder = URL(fileURLWithPath: directory).resolvingSymlinksInPath().standardizedFileURL
        let temporary = FileManager.default.temporaryDirectory.resolvingSymlinksInPath()
          .standardizedFileURL
        let file = URL(fileURLWithPath: path).standardizedFileURL
        guard folder.deletingLastPathComponent() == temporary,
          folder.lastPathComponent.hasPrefix("openstat-"),
          file.lastPathComponent == "\(handle).arrow",
          file.deletingLastPathComponent().resolvingSymlinksInPath().standardizedFileURL == folder,
          try file.resourceValues(forKeys: [.isSymbolicLinkKey, .isRegularFileKey]).isSymbolicLink
            != true,
          try file.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true
        else { throw ArrowPageError.artifact }
        let reader = try FileHandle(forReadingFrom: file)
        defer { try? reader.close() }
        let data = try reader.read(upToCount: ArrowPageReader.maximumBytes + 1) ?? Data()
        guard data.count == size else { throw ArrowPageError.limit }
        let actual = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        guard actual == checksum else { throw ArrowPageError.checksum }
        return try ArrowPageReader.decode(
          data, revision: dataset.revision, offset: offset,
          count: count, fields: dataset.fields, expectedRowIDs: rowIDs)
      }.value
      _ = try await call("artifact.release", ["handle": .string(handle)])
      return page
    } catch {
      _ = try? await call("artifact.release", ["handle": .string(handle)])
      throw error
    }
  }
}
