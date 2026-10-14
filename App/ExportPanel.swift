import OpenStatCore
import SwiftUI

/// Selects a typed export format and explains known format losses before saving.
struct ExportPanel: View {
  @ObservedObject var model: DocumentModel
  @State private var format = "csv"
  @State private var delimiter = ","
  @State private var decimalPoint = "."
  @State private var didRequestExport = false

  private let formats = ["csv", "tsv", "parquet", "json", "sqlite", "xlsx", "sav", "dta"]
  private let flatTextLosses = [
    "codebook", "field_ids", "context", "null_empty_string_distinction", "multiple_response_type",
  ]

  private var knownLosses: [String] {
    flatTextLosses + ["row_ids", "observation_unit", "codebook_missing_codes"]
  }

  var body: some View {
    VStack(alignment: .leading, spacing: 16) {
      Text(L.text("export.title")).font(.title2)
      Picker(L.text("export.format"), selection: $format) {
        ForEach(formats, id: \.self) { Text(L.text("export.format.\($0)")).tag($0) }
      }

      if format == "csv" || format == "tsv" {
        csvOptions
      }

      lossNotes
      if let result = exportResult {
        Divider()
        resultView(result)
      }

      HStack {
        Button(L.text("action.cancel")) { model.showingExport = false }
          .keyboardShortcut(.cancelAction)
        Spacer()
        Button(L.text("export.save")) {
          didRequestExport = true
          model.summary = nil
          model.exportData(format: format, delimiter: delimiter, decimalPoint: decimalPoint)
        }
        .keyboardShortcut(.defaultAction)
        .disabled(model.busy || invalidCSVOptions)
      }
    }
    .padding(24)
    .frame(width: 540)
    .onChange(of: format) { oldFormat, newFormat in
      didRequestExport = false
      if newFormat == "tsv" {
        delimiter = "\t"
      } else if newFormat == "csv" || oldFormat == "tsv" {
        delimiter = ","
      }
    }
    .onChange(of: delimiter) { _, _ in didRequestExport = false }
    .onChange(of: decimalPoint) { _, _ in didRequestExport = false }
  }

  private var csvOptions: some View {
    VStack(alignment: .leading, spacing: 10) {
      if format == "csv" {
        Picker(L.text("export.delimiter"), selection: $delimiter) {
          Text(L.text("export.delimiter.comma")).tag(",")
          Text(L.text("export.delimiter.semicolon")).tag(";")
          Text(L.text("export.delimiter.tab")).tag("\t")
        }
      } else {
        Text(L.text("export.tsv_delimiter")).font(.caption).foregroundStyle(.secondary)
      }
      Picker(L.text("export.decimal_point"), selection: $decimalPoint) {
        Text(L.text("export.decimal.dot")).tag(".")
        Text(L.text("export.decimal.comma")).tag(",")
      }
      if delimiter == decimalPoint {
        Text(L.text("export.invalid_csv_options"))
          .font(.caption).foregroundStyle(.red)
      }
    }
  }

  private var invalidCSVOptions: Bool {
    (format == "csv" || format == "tsv") && delimiter == decimalPoint
  }

  @ViewBuilder private var lossNotes: some View {
    VStack(alignment: .leading, spacing: 8) {
      Text(L.text("export.before_saving")).font(.headline)
      if format == "csv" || format == "tsv" {
        Text(L.text("export.flat_text_note")).font(.caption).foregroundStyle(.secondary)
        ForEach(flatTextLosses, id: \.self) { loss in
          Label(L.text("export.loss.\(loss)"), systemImage: "exclamationmark.triangle")
            .font(.caption).foregroundStyle(.secondary)
        }
      } else {
        Text(L.text("export.format_note.\(format)"))
          .font(.caption).foregroundStyle(.secondary)
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
    .padding(12)
    .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
  }

  @ViewBuilder private func resultView(_ result: JSONValue) -> some View {
    let value = result.object
    VStack(alignment: .leading, spacing: 8) {
      Text(L.text("export.complete")).font(.headline)
      if let rows = value["rows"]?.int {
        Text(L.format("export.rows", rows))
      }
      if let path = value["path"]?.string {
        Text(path).font(.caption.monospaced()).textSelection(.enabled)
      }
      let reported = value["losses"]?.array.compactMap(\.string) ?? []
      if !reported.isEmpty {
        Text(L.text("export.reported_losses")).font(.subheadline.bold())
        ForEach(reported, id: \.self) { loss in
          Label(
            L.text("export.loss.\(knownLosses.contains(loss) ? loss : "unknown")"),
            systemImage: "exclamationmark.triangle"
          )
          .font(.caption).foregroundStyle(.secondary)
        }
      } else {
        Text(L.text("export.no_reported_losses")).font(.caption).foregroundStyle(.secondary)
      }
      if format == "xlsx" {
        Text(L.text("export.xlsx_roundtrip_note"))
          .font(.caption).foregroundStyle(.secondary)
      }
    }
    .frame(maxWidth: .infinity, alignment: .leading)
  }

  private var exportResult: JSONValue? {
    guard didRequestExport, let summary = model.summary,
      summary.object["path"]?.string != nil,
      summary.object["rows"]?.int != nil
    else { return nil }
    return summary
  }
}
