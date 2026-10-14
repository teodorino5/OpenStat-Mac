import Foundation

public enum ArrowPageError: Error, LocalizedError {
  case invalid, unsupported, limit, checksum, artifact
  public var errorDescription: String? {
    switch self {
    case .invalid: return "error.arrow_invalid"
    case .unsupported: return "error.arrow_unsupported"
    case .limit: return "error.arrow_limit"
    case .checksum: return "error.checksum"
    case .artifact: return "error.artifact_handle"
    }
  }
}

/// Original bounded reader for the engine's uncompressed Arrow IPC file subset.
/// Layout references: Apache Arrow format/File.fbs, Message.fbs and Schema.fbs.
/// No external parser or generated library code is embedded.
public enum ArrowPageReader {
  public static let maximumBytes = 32 * 1024 * 1024

  public static func decode(
    _ data: Data, revision: String, offset: Int, count: Int,
    fields: [Variable], expectedRowIDs: [Int]? = nil
  ) throws -> DataPage {
    guard data.count <= maximumBytes, count >= 0, count <= 512, offset >= 0,
      fields.count <= 1024
    else { throw ArrowPageError.limit }
    let bytes = Bytes(data: data)
    guard data.count >= 18, try bytes.string(0, 6) == "ARROW1",
      try bytes.string(data.count - 6, 6) == "ARROW1"
    else { throw ArrowPageError.invalid }
    let footerSize = Int(try bytes.u32(data.count - 10))
    guard footerSize > 0, footerSize <= data.count - 18 else { throw ArrowPageError.invalid }
    let footerStart = data.count - 10 - footerSize
    let footer = try Table(bytes: bytes.slice(footerStart, footerSize))
    guard try footer.short(0) == 4 else { throw ArrowPageError.unsupported }
    guard let schema = try footer.table(1), try schema.short(0) == 0,
      try footer.vector(2, stride: 24).count == 0,
      try schema.vector(3, stride: 8).count == 0
    else { throw ArrowPageError.unsupported }
    let definitions = try schema.vector(1, stride: 4)
    let expected = [("_openstat_row_id", "int64")] + fields.map { ($0.id, $0.storage) }
    guard definitions.count == expected.count else { throw ArrowPageError.invalid }
    for index in 0..<definitions.count {
      let field = try definitions.table(index)
      guard try field.text(0) == expected[index].0,
        try storage(field) == expected[index].1
      else { throw ArrowPageError.invalid }
    }
    let blocks = try footer.vector(3, stride: 24)
    guard blocks.count <= 512 else { throw ArrowPageError.limit }
    var rows: [[JSONValue]] = []
    var rowIDs: [Int] = []
    for block in 0..<blocks.count {
      let entry = blocks.start + block * 24
      let position = try footer.bytes.size64(entry)
      let metadataSize = Int(try footer.bytes.i32(entry + 8))
      let bodySize = try footer.bytes.size64(entry + 16)
      guard metadataSize >= 8, position >= 8, position <= footerStart,
        metadataSize <= footerStart - position,
        bodySize <= footerStart - position - metadataSize,
        try bytes.u32(position) == UInt32.max
      else { throw ArrowPageError.invalid }
      let messageSize = Int(try bytes.u32(position + 4))
      guard messageSize > 0, messageSize <= metadataSize - 8 else { throw ArrowPageError.invalid }
      let message = try Table(bytes: bytes.slice(position + 8, messageSize))
      guard try message.short(0) == 4, try message.byte(1) == 3,
        try message.long(3) == Int64(bodySize), let batch = try message.table(2)
      else { throw ArrowPageError.invalid }
      guard try batch.field(3) == nil, try batch.vector(4, stride: 8).count == 0
      else { throw ArrowPageError.unsupported }
      let batchCount = try batch.size(0)
      guard batchCount <= count - rows.count else { throw ArrowPageError.invalid }
      var cursor = Cursor(
        body: try bytes.slice(position + metadataSize, bodySize),
        nodes: try batch.vector(1, stride: 16), buffers: try batch.vector(2, stride: 16))
      var columns: [[JSONValue]] = []
      for (_, type) in expected {
        columns.append(try cursor.column(type, expectedCount: batchCount))
      }
      guard cursor.nodeIndex == cursor.nodes.count, cursor.bufferIndex == cursor.buffers.count
      else { throw ArrowPageError.invalid }
      for row in 0..<batchCount {
        guard case .integer(let identifier) = columns[0][row], let rowID = Int(exactly: identifier),
          rowID >= 0
        else { throw ArrowPageError.invalid }
        rowIDs.append(rowID)
        rows.append(columns.dropFirst().map { $0[row] })
      }
    }
    guard rows.count == count else { throw ArrowPageError.invalid }
    if let expectedRowIDs {
      guard expectedRowIDs.count == count, rowIDs == expectedRowIDs,
        Set(rowIDs).count == rowIDs.count
      else { throw ArrowPageError.invalid }
    } else {
      for (index, identifier) in rowIDs.enumerated() {
        let (expectedID, overflow) = offset.addingReportingOverflow(index)
        guard !overflow, identifier == expectedID else { throw ArrowPageError.invalid }
      }
    }
    return DataPage(
      revision: revision, offset: offset, count: count, rowIDs: rowIDs,
      fields: fields.map(\.id), rows: rows)
  }

  private static func storage(_ field: Table, depth: Int = 0) throws -> String {
    guard depth <= 1 else { throw ArrowPageError.unsupported }
    guard try field.field(4) == nil else { throw ArrowPageError.unsupported }
    let children = try field.vector(5, stride: 4)
    let type = try field.byte(2)
    if type == 12 {
      guard children.count == 1, try storage(children.table(0), depth: depth + 1) == "string"
      else { throw ArrowPageError.unsupported }
      return "multiple_response"
    }
    guard children.count == 0 else { throw ArrowPageError.unsupported }
    switch type {
    case 2:
      guard let integer = try field.table(3), try integer.int(0) == 64,
        try integer.byte(1) == 1
      else { throw ArrowPageError.unsupported }
      return "int64"
    case 3:
      guard let floating = try field.table(3), try floating.short(0) == 2
      else { throw ArrowPageError.unsupported }
      return "float64"
    case 5: return "string"
    case 6: return "bool"
    default: throw ArrowPageError.unsupported
    }
  }

  private struct Bytes {
    let data: Data
    func range(_ start: Int, _ length: Int) throws -> Range<Int> {
      guard start >= 0, length >= 0, start <= data.count, length <= data.count - start
      else { throw ArrowPageError.invalid }
      return start..<(start + length)
    }
    func slice(_ start: Int, _ length: Int) throws -> Bytes {
      Bytes(data: Data(data[try range(start, length)]))
    }
    func u8(_ position: Int) throws -> UInt8 {
      _ = try range(position, 1)
      return data[position]
    }
    func u16(_ position: Int) throws -> UInt16 {
      try scalar(position, UInt16.self)
    }
    func u32(_ position: Int) throws -> UInt32 {
      try scalar(position, UInt32.self)
    }
    func i32(_ position: Int) throws -> Int32 { Int32(bitPattern: try u32(position)) }
    func i64(_ position: Int) throws -> Int64 {
      Int64(bitPattern: try scalar(position, UInt64.self))
    }
    func size64(_ position: Int) throws -> Int {
      let value = try i64(position)
      guard value >= 0, let size = Int(exactly: value) else { throw ArrowPageError.invalid }
      return size
    }
    func scalar<T: FixedWidthInteger>(_ position: Int, _ type: T.Type) throws -> T {
      _ = try range(position, MemoryLayout<T>.size)
      return data.withUnsafeBytes {
        T(littleEndian: $0.loadUnaligned(fromByteOffset: position, as: T.self))
      }
    }
    func string(_ start: Int, _ length: Int) throws -> String {
      guard let value = String(data: Data(data[try range(start, length)]), encoding: .utf8)
      else { throw ArrowPageError.invalid }
      return value
    }
  }

  private struct Vector {
    let bytes: Bytes, start: Int, count: Int
    func table(_ index: Int) throws -> Table {
      guard index >= 0, index < count else { throw ArrowPageError.invalid }
      let position = start + index * 4
      return try Table(bytes: bytes, position: position + Int(bytes.u32(position)))
    }
  }

  private struct Table {
    let bytes: Bytes, position: Int, vtable: Int, vtableLength: Int, objectLength: Int
    init(bytes: Bytes, position: Int? = nil) throws {
      self.bytes = bytes
      self.position = try position ?? Int(bytes.u32(0))
      let distance = Int(try bytes.i32(self.position))
      let (vtable, overflow) = self.position.subtractingReportingOverflow(distance)
      guard !overflow else { throw ArrowPageError.invalid }
      self.vtable = vtable
      vtableLength = Int(try bytes.u16(vtable))
      objectLength = Int(try bytes.u16(vtable + 2))
      guard vtableLength >= 4, vtableLength % 2 == 0, objectLength >= 4
      else { throw ArrowPageError.invalid }
      _ = try bytes.range(vtable, vtableLength)
      _ = try bytes.range(self.position, objectLength)
    }
    func field(_ slot: Int) throws -> Int? {
      guard slot * 2 + 4 < vtableLength else { return nil }
      let relative = Int(try bytes.u16(vtable + 4 + slot * 2))
      if relative == 0 { return nil }
      guard relative >= 4, relative < objectLength else { throw ArrowPageError.invalid }
      return position + relative
    }
    func byte(_ slot: Int) throws -> UInt8 { try field(slot).map { try bytes.u8($0) } ?? 0 }
    func short(_ slot: Int) throws -> UInt16 { try field(slot).map { try bytes.u16($0) } ?? 0 }
    func int(_ slot: Int) throws -> Int32 { try field(slot).map { try bytes.i32($0) } ?? 0 }
    func long(_ slot: Int) throws -> Int64 { try field(slot).map { try bytes.i64($0) } ?? 0 }
    func size(_ slot: Int) throws -> Int {
      let value = try long(slot)
      guard value >= 0, let size = Int(exactly: value) else { throw ArrowPageError.invalid }
      return size
    }
    func table(_ slot: Int) throws -> Table? {
      guard let pointer = try field(slot) else { return nil }
      return try Table(bytes: bytes, position: pointer + Int(bytes.u32(pointer)))
    }
    func vector(_ slot: Int, stride: Int) throws -> Vector {
      guard let pointer = try field(slot) else { return Vector(bytes: bytes, start: 0, count: 0) }
      let start = pointer + Int(try bytes.u32(pointer))
      let count = Int(try bytes.u32(start))
      guard count <= bytes.data.count / stride else { throw ArrowPageError.invalid }
      _ = try bytes.range(start + 4, count * stride)
      return Vector(bytes: bytes, start: start + 4, count: count)
    }
    func text(_ slot: Int) throws -> String {
      guard let pointer = try field(slot) else { throw ArrowPageError.invalid }
      let start = pointer + Int(try bytes.u32(pointer))
      let count = Int(try bytes.u32(start))
      guard count <= 16384 else { throw ArrowPageError.limit }
      return try bytes.string(start + 4, count)
    }
  }

  private struct Cursor {
    let body: Bytes, nodes: Vector, buffers: Vector
    var nodeIndex = 0, bufferIndex = 0
    mutating func buffer() throws -> Bytes {
      guard bufferIndex < buffers.count else { throw ArrowPageError.invalid }
      let position = buffers.start + bufferIndex * 16
      bufferIndex += 1
      return try body.slice(buffers.bytes.size64(position), buffers.bytes.size64(position + 8))
    }
    mutating func column(_ type: String, expectedCount: Int?) throws -> [JSONValue] {
      guard nodeIndex < nodes.count else { throw ArrowPageError.invalid }
      let position = nodes.start + nodeIndex * 16
      nodeIndex += 1
      let length = try nodes.bytes.size64(position)
      let nullCount = try nodes.bytes.size64(position + 8)
      guard length <= 1_000_000, nullCount <= length,
        expectedCount == nil || expectedCount == length
      else { throw ArrowPageError.invalid }
      let validity = try buffer()
      guard nullCount == 0 || validity.data.count >= (length + 7) / 8
      else { throw ArrowPageError.invalid }
      func valid(_ index: Int) throws -> Bool {
        if validity.data.isEmpty { return true }
        return try validity.u8(index / 8) & (1 << (index % 8)) != 0
      }
      let values = try buffer()
      var result: [JSONValue] = []
      if type == "string" || type == "multiple_response" {
        _ = try values.range(0, (length + 1) * 4)
        var offsets: [Int] = []
        for index in 0...length {
          let value = Int(try values.i32(index * 4))
          guard value >= 0, value >= (offsets.last ?? 0) else { throw ArrowPageError.invalid }
          offsets.append(value)
        }
        let strings = type == "string" ? try buffer() : nil
        let children = type == "multiple_response" ? try column("string", expectedCount: nil) : nil
        let capacity = strings?.data.count ?? children!.count
        guard offsets.last! <= capacity else { throw ArrowPageError.invalid }
        for index in 0..<length {
          if try !valid(index) {
            result.append(.null)
            continue
          }
          let start = offsets[index]
          let end = offsets[index + 1]
          if let strings {
            result.append(.string(try strings.string(start, end - start)))
          } else {
            let elements = Array(children![start..<end])
            let labels = elements.compactMap { value -> String? in
              if case .string(let text) = value { return text }
              return nil
            }
            guard labels.count == elements.count, Set(labels).count == labels.count
            else { throw ArrowPageError.invalid }
            result.append(.array(elements))
          }
        }
      } else {
        let bytesNeeded = type == "bool" ? (length + 7) / 8 : length * 8
        _ = try values.range(0, bytesNeeded)
        for index in 0..<length {
          if try !valid(index) {
            result.append(.null)
            continue
          }
          switch type {
          case "int64": result.append(.integer(try values.i64(index * 8)))
          case "float64":
            let value = Double(bitPattern: UInt64(bitPattern: try values.i64(index * 8)))
            guard value.isFinite else { throw ArrowPageError.invalid }
            result.append(.number(value))
          case "bool": result.append(.bool(try values.u8(index / 8) & (1 << (index % 8)) != 0))
          default: throw ArrowPageError.unsupported
          }
        }
      }
      guard result.filter({ $0 == .null }).count == nullCount else { throw ArrowPageError.invalid }
      return result
    }
  }
}
