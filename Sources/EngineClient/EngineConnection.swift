import Foundation
import OpenStatCore

/// Serial protocol state lives on a queue; blocking process I/O never runs on the main actor.
public final class EngineConnection: @unchecked Sendable {
  private let queue = DispatchQueue(label: "org.openstat.engine.connection")
  private let process = Process()
  private let input = Pipe(), output = Pipe(), diagnostics = Pipe()
  private var decoder = FrameDecoder()
  private var pending: [String: CheckedContinuation<JSONValue, Error>] = [:]
  private var stopped = false

  public init(python: URL, engineSource: URL) throws {
    process.executableURL = python
    process.arguments = [
      "-I", "-c",
      "import sys; sys.path.insert(0, sys.argv.pop(1)); from openstat_engine.cli import main; raise SystemExit(main())",
      engineSource.path, "serve",
    ]
    process.environment = [
      "HOME": NSHomeDirectory(), "PATH": "/usr/bin:/bin", "LC_ALL": "en_US.UTF-8",
      "TMPDIR": FileManager.default.temporaryDirectory.path,
    ]
    process.standardInput = input
    process.standardOutput = output
    process.standardError = diagnostics
    output.fileHandleForReading.readabilityHandler = { [weak self] handle in
      let data = handle.availableData
      self?.queue.async { [weak self] in self?.receive(data) }
    }
    // Drain diagnostics so a verbose native dependency cannot deadlock the child.
    diagnostics.fileHandleForReading.readabilityHandler = { handle in _ = handle.availableData }
    process.terminationHandler = { [weak self] _ in
      self?.queue.async { [weak self] in self?.fail(RPCError.unavailable) }
    }
    do { try process.run() } catch {
      close()
      throw RPCError.unavailable
    }
  }

  public func call(_ method: String, _ parameters: [String: JSONValue] = [:]) async throws
    -> JSONValue
  {
    try await withCheckedThrowingContinuation { continuation in
      queue.async {
        guard !self.stopped else {
          continuation.resume(throwing: RPCError.unavailable)
          return
        }
        let id = UUID().uuidString
        self.pending[id] = continuation
        do {
          let data = try RPCFrame.encode(
            .object([
              "jsonrpc": .string("2.0"), "id": .string(id), "method": .string(method),
              "params": .object(parameters),
            ]))
          try self.input.fileHandleForWriting.write(contentsOf: data)
        } catch { self.fail(error) }
        self.queue.asyncAfter(deadline: .now() + 30) {
          // Termination prevents later queued requests from waiting behind a hung operation.
          if self.pending[id] != nil {
            self.fail(RPCError.timeout)
            self.process.terminate()
          }
        }
      }
    }
  }

  private func receive(_ data: Data) {
    if data.isEmpty {
      fail(RPCError.unavailable)
      return
    }
    do {
      for payload in try decoder.append(data) {
        let response = try JSONDecoder().decode(JSONValue.self, from: payload).object
        guard response["jsonrpc"]?.string == "2.0", let id = response["id"]?.string,
          let continuation = pending.removeValue(forKey: id)
        else { throw RPCError.protocolFailure }
        if let error = response["error"] {
          continuation.resume(
            throwing: RPCError.engine(error.object["message"]?.string ?? "error.engine_internal"))
        } else if let result = response["result"] {
          continuation.resume(returning: result)
        } else {
          continuation.resume(throwing: RPCError.protocolFailure)
        }
      }
    } catch { fail(error) }
  }

  private func fail(_ error: Error) {
    stopped = true
    let waiting = Array(pending.values)
    pending.removeAll()
    for continuation in waiting { continuation.resume(throwing: error) }
  }

  public func close() {
    output.fileHandleForReading.readabilityHandler = nil
    diagnostics.fileHandleForReading.readabilityHandler = nil
    process.terminationHandler = nil
    if process.isRunning { process.terminate() }
    queue.async { self.fail(RPCError.unavailable) }
  }
  deinit { if process.isRunning { process.terminate() } }
}
