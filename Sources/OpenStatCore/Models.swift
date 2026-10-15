import Foundation

public enum JSONValue: Codable, Equatable, Sendable {
  case null
  case bool(Bool)
  case integer(Int64)
  case number(Double)
  case string(String)
  case array([JSONValue])
  case object([String: JSONValue])

  public init(from decoder: Decoder) throws {
    let container = try decoder.singleValueContainer()
    if container.decodeNil() {
      self = .null
    } else if let value = try? container.decode(Bool.self) {
      self = .bool(value)
    } else if let value = try? container.decode(Int64.self) {
      self = .integer(value)
    } else if let value = try? container.decode(Double.self) {
      self = .number(value)
    } else if let value = try? container.decode(String.self) {
      self = .string(value)
    } else if let value = try? container.decode([JSONValue].self) {
      self = .array(value)
    } else {
      self = .object(try container.decode([String: JSONValue].self))
    }
  }

  public func encode(to encoder: Encoder) throws {
    var container = encoder.singleValueContainer()
    switch self {
    case .null: try container.encodeNil()
    case .bool(let value): try container.encode(value)
    case .integer(let value): try container.encode(value)
    case .number(let value): try container.encode(value)
    case .string(let value): try container.encode(value)
    case .array(let value): try container.encode(value)
    case .object(let value): try container.encode(value)
    }
  }

  public var object: [String: JSONValue] {
    if case .object(let value) = self { return value }
    return [:]
  }
  public var array: [JSONValue] {
    if case .array(let value) = self { return value }
    return []
  }
  public var string: String {
    if case .string(let value) = self { return value }
    return ""
  }
  public var int: Int {
    if case .integer(let value) = self { return Int(value) }
    return 0
  }

  public func display(locale: Locale = .current) -> String {
    switch self {
    case .null: return ""
    case .string(let value): return value
    case .bool(let value): return value ? "true" : "false"
    case .integer(let value): return String(value)
    case .number(let value):
      // Editable cells use a shortest-round-trip representation, never rounded display values.
      return String(value).replacingOccurrences(of: ".", with: locale.decimalSeparator ?? ".")
    case .array, .object:
      guard let data = try? JSONEncoder().encode(self) else { return "" }
      return String(decoding: data, as: UTF8.self)
    }
  }
}

public struct Variable: Identifiable, Codable, Equatable, Sendable {
  public var id, name, storage, measurement, role: String
  public var levels, missingCodes: [String]
  public var valueLabels: [String: String]
  enum CodingKeys: String, CodingKey {
    case id, name, storage, measurement, role, levels
    case missingCodes = "missing_codes"
    case valueLabels = "value_labels"
  }
}

public struct Dataset: Codable, Equatable, Sendable {
  public let id, revision, name: String
  public let rowCount: Int
  public var fields: [Variable]
  public var context, observationUnit: String
  enum CodingKeys: String, CodingKey {
    case id, revision, name, fields, context
    case rowCount = "row_count"
    case observationUnit = "observation_unit"
  }
}

public struct DataPage: Codable, Sendable {
  public let revision: String
  public let offset, count: Int
  public let rowIDs: [Int]
  public let fields: [String]
  public let rows: [[JSONValue]]
  enum CodingKeys: String, CodingKey {
    case revision, offset, count, fields, rows
    case rowIDs = "row_ids"
  }
}

public enum CellParser {
  public static func parse(_ text: String, storage: String, locale: Locale) throws -> JSONValue {
    if text.isEmpty { return .null }
    switch storage {
    case "string": return .string(text)
    case "int64":
      guard let value = Int64(text) else { throw ParseError.invalid }
      return .integer(value)
    case "float64":
      let decimal = locale.decimalSeparator ?? "."
      let normalized = text.replacingOccurrences(of: decimal, with: ".")
      guard let value = Double(normalized), value.isFinite else { throw ParseError.invalid }
      return .number(value)
    case "bool":
      guard text == "true" || text == "false" else { throw ParseError.invalid }
      return .bool(text == "true")
    case "multiple_response":
      guard let value = try? JSONDecoder().decode([String].self, from: Data(text.utf8)),
        Set(value).count == value.count
      else { throw ParseError.invalid }
      return .array(value.map(JSONValue.string))
    default: throw ParseError.invalid
    }
  }
  public enum ParseError: Error { case invalid }
}

public struct WorkbookBlock: Identifiable, Codable, Equatable, Sendable {
  public var id: String
  public var type: String
  public var title: String
  public var collapsed: Bool
  public var annotation: String?
  public var sourceAnalysis: String?
  public var content: [String: JSONValue]

  enum CodingKeys: String, CodingKey {
    case id, type, title, collapsed, annotation, content
    case sourceAnalysis = "source_analysis"
  }

  public init(
    id: String,
    type: String,
    title: String,
    collapsed: Bool = false,
    annotation: String? = nil,
    sourceAnalysis: String? = nil,
    content: [String: JSONValue] = [:]
  ) {
    self.id = id
    self.type = type
    self.title = title
    self.collapsed = collapsed
    self.annotation = annotation
    self.sourceAnalysis = sourceAnalysis
    self.content = content
  }
}

public struct ResultsWorkbook: Identifiable, Codable, Equatable, Sendable {
  public var id: String
  public var title: String
  public var revision: Int
  public var blocks: [WorkbookBlock]

  public init(
    id: String,
    title: String,
    revision: Int = 1,
    blocks: [WorkbookBlock] = []
  ) {
    self.id = id
    self.title = title
    self.revision = revision
    self.blocks = blocks
  }
}
