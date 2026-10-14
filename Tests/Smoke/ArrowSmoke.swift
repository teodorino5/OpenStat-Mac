import Foundation
import OpenStatCore

/// Original literal expectations: no expected value is computed by the Swift reader.
enum ArrowSmoke {
  static func run(root: URL) throws {
    let definitions: [[String: Any]] = zip(
      ["i", "f", "s", "b", "m"],
      ["int64", "float64", "string", "bool", "multiple_response"]
    ).map { id, storage in
      [
        "id": id, "name": id, "storage": storage, "measurement": "nominal",
        "role": "characteristic", "levels": [], "missing_codes": [], "value_labels": [:],
      ]
    }
    let fields = try JSONDecoder().decode(
      [Variable].self,
      from: JSONSerialization.data(withJSONObject: definitions))
    let folder = root.appendingPathComponent("build/arrow-fixtures")
    let input = try Data(contentsOf: folder.appendingPathComponent("typed.arrow"))
    let page = try ArrowPageReader.decode(
      input, revision: "literal", offset: 42, count: 3, fields: fields)
    try Smoke.expect(page.rowIDs == [42, 43, 44], "Arrow stable IDs changed")
    try Smoke.expect(
      page.rows[0][0] == .integer(Int64.min) && page.rows[1][0] == .integer(Int64.max),
      "Arrow int64 bounds changed")
    guard case .number(let zero) = page.rows[0][1], case .number(let tiny) = page.rows[1][1],
      case .number(let precise) = page.rows[2][1]
    else { throw ArrowPageError.invalid }
    try Smoke.expect(zero.bitPattern == 0x8000_0000_0000_0000, "Arrow negative zero lost")
    try Smoke.expect(
      tiny.bitPattern == 1 && precise.bitPattern == 0x3ff3_c0ca_428c_59fb,
      "Arrow float64 precision lost")
    try Smoke.expect(
      page.rows[0][2] == .string("česky 🧪") && page.rows[1][2] == .string(""), "Arrow UTF-8 changed"
    )
    try Smoke.expect(
      page.rows[0][3] == .bool(true) && page.rows[1][3] == .bool(false), "Arrow bits changed")
    try Smoke.expect(
      page.rows[0][4] == .array([.string("česky"), .string("blue")])
        && page.rows[1][4] == .array([]), "Arrow response set changed")
    try Smoke.expect(
      page.rows[2].enumerated().allSatisfy { $0.offset == 1 || $0.element == .null },
      "Arrow nulls changed")
    let empty = try Data(contentsOf: folder.appendingPathComponent("empty.arrow"))
    try Smoke.expect(
      try ArrowPageReader.decode(empty, revision: "empty", offset: 0, count: 0, fields: fields).rows
        .isEmpty, "Empty Arrow page failed")
    for name in ["compressed", "nonfinite", "duplicate-response", "null-response"] {
      let invalid = try Data(contentsOf: folder.appendingPathComponent("\(name).arrow"))
      try rejected {
        _ = try ArrowPageReader.decode(invalid, revision: "x", offset: 42, count: 3, fields: fields)
      }
    }
    // Every truncation boundary must fail without a memory trap.
    for size in 0..<input.count {
      try rejected {
        _ = try ArrowPageReader.decode(
          Data(input.prefix(size)), revision: "x", offset: 42, count: 3, fields: fields)
      }
    }
    try rejected {
      _ = try ArrowPageReader.decode(input, revision: "x", offset: 41, count: 3, fields: fields)
    }
    try rejected {
      _ = try ArrowPageReader.decode(input, revision: "x", offset: 42, count: 2, fields: fields)
    }
    try rejected {
      _ = try ArrowPageReader.decode(input, revision: "x", offset: 42, count: 513, fields: fields)
    }
    try rejected {
      _ = try ArrowPageReader.decode(input, revision: "x", offset: 42, count: 3, fields: [])
    }
    // Deterministic corruption exercises table pointers, lengths and body offsets.
    // Some flips produce different valid data; the requirement here is no crash.
    for index in input.indices {
      var changed = input
      changed[index] ^= 0xff
      _ = try? ArrowPageReader.decode(changed, revision: "x", offset: 42, count: 3, fields: fields)
    }
    print(
      "PASS: Arrow literal data, 6 inputs, \(input.count) truncations and \(input.count) byte mutations."
    )
  }
  static func rejected(_ operation: () throws -> Void) throws {
    do { try operation() } catch is ArrowPageError { return }
    throw ArrowPageError.invalid
  }
}
