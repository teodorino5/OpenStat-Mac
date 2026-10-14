import Foundation
import OpenStatCore

public enum RPCError: Error, LocalizedError {
  case protocolFailure
  case engine(String)
  case unavailable, timeout
  public var errorDescription: String? {
    switch self {
    case .engine(let key): return key
    case .protocolFailure: return "error.rpc_request"
    case .unavailable: return "error.runtime_missing"
    case .timeout: return "error.rpc_timeout"
    }
  }
}

public struct FrameDecoder {
  private var buffer = Data()
  public init() {}

  public mutating func append(_ data: Data) throws -> [Data] {
    buffer.append(data)
    var result: [Data] = []
    let separator = Data("\r\n\r\n".utf8)
    while let boundary = buffer.range(of: separator) {
      guard boundary.lowerBound <= 4096,
        let header = String(data: buffer[..<boundary.lowerBound], encoding: .ascii)
      else { throw RPCError.protocolFailure }
      let lines = header.components(separatedBy: "\r\n")
      var length: Int?
      for line in lines {
        let pieces = line.split(separator: ":", maxSplits: 1)
        guard pieces.count == 2 else { throw RPCError.protocolFailure }
        if pieces[0].lowercased() == "content-length" {
          guard length == nil else { throw RPCError.protocolFailure }
          length = Int(pieces[1].trimmingCharacters(in: .whitespaces))
        }
      }
      guard let length, length > 0, length <= 8 * 1024 * 1024
      else { throw RPCError.protocolFailure }
      let end = boundary.upperBound + length
      guard buffer.count >= end else { break }
      result.append(Data(buffer[boundary.upperBound..<end]))
      buffer.removeSubrange(..<end)
    }
    if buffer.count > 8 * 1024 * 1024 + 4096 { throw RPCError.protocolFailure }
    if buffer.range(of: separator) == nil && buffer.count > 4096 { throw RPCError.protocolFailure }
    return result
  }
}

public enum RPCFrame {
  public static func encode(_ value: JSONValue) throws -> Data {
    let body = try JSONEncoder().encode(value)
    return Data("Content-Length: \(body.count)\r\n\r\n".utf8) + body
  }
}
