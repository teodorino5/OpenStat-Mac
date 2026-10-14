import AppKit

@MainActor
final class NativeToolbar: NSObject, NSToolbarDelegate, NSToolbarItemValidation {
  private weak var document: OpenStatDocument?
  private let importID = NSToolbarItem.Identifier("openstat.import")
  private let caseID = NSToolbarItem.Identifier("openstat.addCase")
  private let variableID = NSToolbarItem.Identifier("openstat.addVariable")
  private let saveID = NSToolbarItem.Identifier("openstat.save")
  init(document: OpenStatDocument) { self.document = document }
  func makeToolbar() -> NSToolbar {
    let toolbar = NSToolbar(identifier: "openstat.document")
    toolbar.delegate = self
    toolbar.displayMode = .iconAndLabel
    return toolbar
  }
  func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
    [importID, caseID, variableID, .flexibleSpace, saveID]
  }
  func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] {
    [importID, caseID, variableID, .flexibleSpace, saveID]
  }
  func toolbar(
    _ toolbar: NSToolbar, itemForItemIdentifier identifier: NSToolbarItem.Identifier,
    willBeInsertedIntoToolbar flag: Bool
  ) -> NSToolbarItem? {
    let item = NSToolbarItem(itemIdentifier: identifier)
    item.target = self
    if identifier == importID {
      item.label = L.text("action.import")
      item.image = NSImage(
        systemSymbolName: "square.and.arrow.down", accessibilityDescription: item.label)
      item.action = #selector(importData(_:))
    } else if identifier == caseID {
      item.label = L.text("action.add_case")
      item.image = NSImage(systemSymbolName: "plus", accessibilityDescription: item.label)
      item.action = #selector(addCase(_:))
    } else if identifier == variableID {
      item.label = L.text("action.add_variable")
      item.image = NSImage(
        systemSymbolName: "tablecells.badge.ellipsis", accessibilityDescription: item.label)
      item.action = #selector(addVariable(_:))
    } else if identifier == saveID {
      item.label = L.text("action.save")
      item.image = NSImage(
        systemSymbolName: "square.and.arrow.up", accessibilityDescription: item.label)
      item.action = #selector(saveData(_:))
    } else {
      return nil
    }
    return item
  }
  func validateToolbarItem(_ item: NSToolbarItem) -> Bool {
    document?.model.dataset != nil && document?.model.busy == false
  }
  @objc private func importData(_ sender: Any?) { document?.model.importCSV() }
  @objc private func addCase(_ sender: Any?) { document?.model.appendCase() }
  @objc private func addVariable(_ sender: Any?) { document?.model.showingNewVariable = true }
  @objc private func saveData(_ sender: Any?) { document?.save(sender) }
}
