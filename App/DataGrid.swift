import AppKit
import SwiftUI

struct DataGrid: NSViewRepresentable {
  @ObservedObject var model: DocumentModel
  func makeCoordinator() -> Coordinator { Coordinator(model) }
  func makeNSView(context: Context) -> NSScrollView {
    let table = NSTableView()
    table.delegate = context.coordinator
    table.dataSource = context.coordinator
    table.rowHeight = 28
    table.usesAlternatingRowBackgroundColors = true
    table.columnAutoresizingStyle = .noColumnAutoresizing
    table.allowsMultipleSelection = true
    table.setAccessibilityLabel(L.text("grid.label"))
    let scroll = NSScrollView()
    scroll.documentView = table
    scroll.hasVerticalScroller = true
    scroll.hasHorizontalScroller = true
    context.coordinator.table = table
    return scroll
  }
  func updateNSView(_ view: NSScrollView, context: Context) {
    guard let table = context.coordinator.table else { return }
    context.coordinator.model = model
    if context.coordinator.revision != model.dataset?.revision {
      context.coordinator.revision = model.dataset?.revision
      table.deselectAll(nil)
    }
    let signature = model.dataset?.fields.map { "\($0.id):\($0.name)" }.joined(separator: "|") ?? ""
    if signature != context.coordinator.signature {
      context.coordinator.signature = signature
      for column in table.tableColumns { table.removeTableColumn(column) }
      let number = NSTableColumn(identifier: NSUserInterfaceItemIdentifier("row"))
      number.title = L.text("grid.case")
      number.width = 65
      table.addTableColumn(number)
      for field in model.dataset?.fields ?? [] {
        let column = NSTableColumn(identifier: NSUserInterfaceItemIdentifier(field.id))
        column.title = field.name
        column.width = 180
        table.addTableColumn(column)
      }
    }
    if table.currentEditor() == nil { table.reloadData() }
  }
  @MainActor
  final class Coordinator: NSObject, NSTableViewDataSource, NSTableViewDelegate, NSTextFieldDelegate
  {
    var model: DocumentModel
    weak var table: NSTableView?
    var signature = ""
    var revision: String?
    init(_ model: DocumentModel) { self.model = model }
    func numberOfRows(in tableView: NSTableView) -> Int { model.dataset?.rowCount ?? 0 }
    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int)
      -> NSView?
    {
      guard let tableColumn else { return nil }
      let index = tableView.tableColumns.firstIndex(of: tableColumn) ?? 0
      let identifier = NSUserInterfaceItemIdentifier("cell-\(index)")
      let cell =
        (tableView.makeView(withIdentifier: identifier, owner: self) as? NSTableCellView)
        ?? NSTableCellView()
      cell.identifier = identifier
      if cell.textField == nil {
        let text = NSTextField()
        text.isBordered = false
        text.drawsBackground = false
        text.translatesAutoresizingMaskIntoConstraints = false
        text.delegate = self
        cell.addSubview(text)
        cell.textField = text
        NSLayoutConstraint.activate([
          text.leadingAnchor.constraint(equalTo: cell.leadingAnchor, constant: 8),
          text.trailingAnchor.constraint(equalTo: cell.trailingAnchor, constant: -8),
          text.centerYAnchor.constraint(equalTo: cell.centerYAnchor),
        ])
      }
      let text = cell.textField!
      text.isEditable = index > 0 && !model.busy
      text.isSelectable = index > 0
      if index == 0 {
        text.stringValue =
          model.rowID(for: row).map { String(UInt64($0) + 1) } ?? L.text("grid.loading")
        text.textColor = .secondaryLabelColor
      } else if let value = model.value(row: row, column: index - 1) {
        text.stringValue = value.display()
        text.textColor = .labelColor
      } else {
        text.stringValue = L.text("grid.loading")
        text.textColor = .tertiaryLabelColor
        text.isEditable = false
        Task { await model.loadPage(row) }
      }
      text.setAccessibilityLabel(L.format("grid.cell", tableColumn.title, row + 1))
      return cell
    }
    func tableViewSelectionDidChange(_ notification: Notification) {
      guard let table else { return }
      model.selectedRowIDs = Set(table.selectedRowIndexes.compactMap { model.rowID(for: $0) })
    }
    func controlTextDidEndEditing(_ notification: Notification) {
      guard let text = notification.object as? NSTextField, let table else { return }
      let row = table.row(for: text)
      let column = table.column(for: text) - 1
      guard row >= 0, column >= 0 else { return }
      model.edit(row: row, column: column, text: text.stringValue)
    }
  }
}
