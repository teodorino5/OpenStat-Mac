import XCTest

@testable import OpenStatCore

final class ModelsTests: XCTestCase {
  func testJSONPreservesIntegerPrecisionAndMissingValues() throws {
    let value = JSONValue.object([
      "integer": .integer(9_007_199_254_740_993),
      "missing": .null, "value": .number(1.25),
      "text": .string("česky"), "flag": .bool(false),
    ])
    XCTAssertEqual(
      try JSONDecoder().decode(JSONValue.self, from: JSONEncoder().encode(value)), value)
  }
  func testLocaleDecimalParsingAndInvalidValues() throws {
    XCTAssertEqual(
      try CellParser.parse("1,25", storage: "float64", locale: Locale(identifier: "cs_CZ")),
      .number(1.25))
    XCTAssertEqual(
      try CellParser.parse("1.25", storage: "float64", locale: Locale(identifier: "en_US")),
      .number(1.25))
    XCTAssertEqual(try CellParser.parse("", storage: "int64", locale: .current), .null)
    XCTAssertEqual(
      try CellParser.parse("blue", storage: "string", locale: .current), .string("blue"))
    XCTAssertEqual(try CellParser.parse("false", storage: "bool", locale: .current), .bool(false))
    for text in ["nan", "inf", "1,2.3", "text"] {
      XCTAssertThrowsError(
        try CellParser.parse(text, storage: "float64", locale: Locale(identifier: "cs_CZ")))
    }
    XCTAssertThrowsError(try CellParser.parse("1.2", storage: "int64", locale: .current))
    XCTAssertThrowsError(try CellParser.parse("yes", storage: "bool", locale: .current))
  }
  func testEditableDisplayDoesNotRoundStoredValues() throws {
    let value = JSONValue.number(1.2345678901234567)
    for language in ["cs_CZ", "en_US"] {
      let locale = Locale(identifier: language)
      XCTAssertEqual(
        try CellParser.parse(value.display(locale: locale), storage: "float64", locale: locale),
        value)
    }
  }
  func testResponseSets() throws {
    XCTAssertEqual(
      try CellParser.parse("[\"blue\",\"red\"]", storage: "multiple_response", locale: .current),
      .array([.string("blue"), .string("red")]))
    XCTAssertThrowsError(
      try CellParser.parse("[\"red\",\"red\"]", storage: "multiple_response", locale: .current))
    XCTAssertThrowsError(
      try CellParser.parse("[2]", storage: "multiple_response", locale: .current))
  }
}
