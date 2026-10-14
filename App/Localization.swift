import Foundation

enum L {
  static func text(_ key: String) -> String {
    let language = Locale.preferredLanguages.first?.hasPrefix("cs") == true ? "cs" : "en"
    #if SWIFT_PACKAGE
      let packaged = Bundle.main.url(
        forResource: "OpenStatMac_OpenStatApp", withExtension: "bundle")
      let resources = packaged.flatMap { Bundle(url: $0) } ?? Bundle.module
      let root = resources.resourceURL!
    #else
      let root = Bundle.main.resourceURL!
    #endif
    guard let bundle = Bundle(url: root.appendingPathComponent("\(language).lproj")) else {
      return key
    }
    return bundle.localizedString(forKey: key, value: key, table: "Localizable")
  }
  static func format(_ key: String, _ arguments: CVarArg...) -> String {
    String(format: text(key), locale: Locale.current, arguments: arguments)
  }
}
