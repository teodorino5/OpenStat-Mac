import AppKit

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
  var controller: OpenStatDocumentController?
  func applicationDidFinishLaunching(_ notification: Notification) {
    controller = OpenStatDocumentController()
    installMenus()
    NSApp.setActivationPolicy(.regular)
    controller?.newDocument(nil)
    NSApp.activate(ignoringOtherApps: true)
    if let flag = CommandLine.arguments.firstIndex(of: "--self-check"),
      CommandLine.arguments.count > flag + 1, let controller
    {
      let report = URL(fileURLWithPath: CommandLine.arguments[flag + 1])
      Task { await NativeSmoke.run(controller: controller, report: report) }
    }
  }
  func applicationShouldOpenUntitledFile(_ sender: NSApplication) -> Bool { false }
  private func installMenus() {
    let bar = NSMenu()
    func menu(_ title: String, items: [(String, Selector?, String)]) {
      let parent = NSMenuItem()
      parent.title = title
      let child = NSMenu(title: title)
      for (name, action, key) in items {
        child.addItem(NSMenuItem(title: name, action: action, keyEquivalent: key))
      }
      parent.submenu = child
      bar.addItem(parent)
    }
    menu(
      L.text("app.name"),
      items: [(L.text("action.quit"), #selector(NSApplication.terminate(_:)), "q")])
    menu(
      L.text("menu.file"),
      items: [
        (L.text("action.new"), #selector(NSDocumentController.newDocument(_:)), "n"),
        (L.text("action.open"), #selector(NSDocumentController.openDocument(_:)), "o"),
        (L.text("action.save"), #selector(NSDocument.save(_:)), "s"),
        (L.text("action.save_as"), #selector(NSDocument.saveAs(_:)), "S"),
        (L.text("action.close"), #selector(NSWindow.performClose(_:)), "w"),
      ])
    menu(
      L.text("menu.edit"),
      items: [
        (L.text("action.undo"), Selector(("undo:")), "z"),
        (L.text("action.redo"), Selector(("redo:")), "Z"),
        (L.text("action.cut"), #selector(NSText.cut(_:)), "x"),
        (L.text("action.copy"), #selector(NSText.copy(_:)), "c"),
        (L.text("action.paste"), #selector(NSText.paste(_:)), "v"),
        (L.text("action.select_all"), #selector(NSText.selectAll(_:)), "a"),
      ])
    menu(L.text("menu.statistics"), items: [(L.text("phase.order"), nil, "")])
    menu(
      L.text("menu.window"),
      items: [
        (L.text("action.minimize"), #selector(NSWindow.performMiniaturize(_:)), "m"),
        (L.text("action.next_tab"), #selector(NSWindow.selectNextTab(_:)), ""),
        (L.text("action.previous_tab"), #selector(NSWindow.selectPreviousTab(_:)), ""),
      ])
    NSApp.windowsMenu = bar.items.last?.submenu
    NSApp.mainMenu = bar
  }
}

@main
struct OpenStatMain {
  @MainActor
  static func main() {
    let application = NSApplication.shared
    let delegate = AppDelegate()
    application.delegate = delegate
    application.run()
    withExtendedLifetime(delegate) {}
  }
}
