import OpenStatCore
import XCTest

@testable import EngineClient

final class FramingTests: XCTestCase {
  func testByteByByteUnicodeAndMultipleFrames() throws {
    let first = JSONValue.object(["text": .string("česky")])
    let second = JSONValue.object(["result": .null])
    let data = try RPCFrame.encode(first) + RPCFrame.encode(second)
    var decoder = FrameDecoder()
    var messages: [Data] = []
    for byte in data { messages += try decoder.append(Data([byte])) }
    XCTAssertEqual(messages.count, 2)
    XCTAssertEqual(try JSONDecoder().decode(JSONValue.self, from: messages[0]), first)
    XCTAssertEqual(try JSONDecoder().decode(JSONValue.self, from: messages[1]), second)
  }
  func testFrameLimitsAndInvalidHeaders() {
    for text in [
      "Content-Length: -1\r\n\r\n", "Content-Length: 99999999\r\n\r\n",
      "Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}", "BadHeader\r\n\r\n{}",
    ] {
      var decoder = FrameDecoder()
      XCTAssertThrowsError(try decoder.append(Data(text.utf8)))
    }
  }
}
