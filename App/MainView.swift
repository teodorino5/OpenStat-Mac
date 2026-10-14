import SwiftUI

struct MainView: View {
  @ObservedObject var model: DocumentModel
  @State private var section = "datasets"
  @State private var nameDraft = ""
  @State private var unitDraft = ""
  var body: some View {
    NavigationSplitView {
      List(selection: $section) {
        Section(L.text("sidebar.project")) {
          Label(L.text("sidebar.datasets"), systemImage: "tablecells").tag("datasets")
          Label(L.text("sidebar.analyses"), systemImage: "function").tag("analyses")
          Label(L.text("sidebar.results"), systemImage: "doc.richtext").tag("results")
          Label(L.text("sidebar.workflows"), systemImage: "point.3.connected.trianglepath.dotted")
            .tag("workflows")
        }
        Section(L.text("sidebar.datasets")) {
          if let dataset = model.dataset {
            Label(dataset.name, systemImage: "square.grid.3x3").tag("datasets")
          }
        }
      }
      .navigationSplitViewColumnWidth(min: 180, ideal: 210)
      .safeAreaInset(edge: .bottom) {
        Text(L.text("phase.foundation")).font(.caption).foregroundStyle(.secondary).padding()
      }
    } detail: {
      if section == "datasets" {
        VStack(spacing: 0) {
          HStack {
            Image(systemName: "tablecells").foregroundStyle(.tint)
            Text(model.dataset?.name ?? L.text("dataset.untitled")).font(.headline)
            Spacer()
            if model.busy {
              if let progress = model.jobProgress {
                ProgressView(value: progress).frame(width: 100).accessibilityLabel(
                  L.text("job.stage"))
              } else {
                ProgressView().controlSize(.small)
              }
              Button(L.text("action.cancel")) { model.cancelOperation() }
            }
            if let dataset = model.dataset {
              Text(L.format("dataset.dimensions", dataset.rowCount, dataset.fields.count))
                .font(.caption).foregroundStyle(.secondary)
            }
          }.padding(14)
          Divider()
          HStack(spacing: 0) {
            DataGrid(model: model)
            Divider()
            inspector.frame(width: 280)
          }
          Divider()
          HStack {
            Text(L.text("status.data_only"))
            Spacer()
            if let context = model.dataset?.context { Text(L.text("context.\(context)")) }
          }.font(.caption).foregroundStyle(.secondary).padding(10)
        }
      } else {
        ContentUnavailableView(
          L.text("phase.coming"), systemImage: "function",
          description: Text(L.text("phase.order")))
      }
    }
    .sheet(
      isPresented: Binding(
        get: { model.importSource != nil },
        set: {
          if !$0 { model.importSource = nil }
        })
    ) {
      if let source = model.importSource { CSVImportOptions(model: model, source: source) }
    }
    .sheet(isPresented: $model.showingNewVariable) { NewVariableForm(model: model) }
    .sheet(isPresented: $model.showingClassification) {
      ClassificationPanel(model: model).frame(width: 680, height: 690)
    }
    .sheet(isPresented: $model.showingColumns) {
      ColumnOperationsPanel(model: model).frame(width: 600, height: 690)
    }
    .sheet(isPresented: $model.showingCases) {
      CaseOperationsPanel(model: model).frame(width: 640, height: 690)
    }
    .sheet(isPresented: $model.showingCodebook) {
      CodebookPanel(model: model).frame(width: 600, height: 690)
    }
    .sheet(isPresented: $model.showingExport) {
      ExportPanel(model: model).frame(width: 600, height: 600)
    }
    .sheet(isPresented: $model.showingOutliers) {
      OutlierPanel(model: model).frame(width: 600, height: 600)
    }
    .alert(
      L.text("error.title"),
      isPresented: Binding(
        get: { model.errorKey != nil }, set: { if !$0 { model.errorKey = nil } }
      )
    ) {
      Button(L.text("action.ok")) { model.errorKey = nil }
    } message: {
      Text(L.text(model.errorKey ?? "error.engine_internal"))
    }
  }

  private var inspector: some View {
    ScrollView {
      VStack(alignment: .leading, spacing: 18) {
        Text(L.text("inspector.title")).font(.headline)
        Button(L.text("action.classification")) { model.showingClassification = true }
        Button(L.text("action.columns")) { model.showingColumns = true }
        Button(L.text("action.cases")) { model.showingCases = true }
        Button(L.text("action.export")) { model.showingExport = true }
        Button(L.text("action.outliers")) { model.showingOutliers = true }
        Button(L.text("action.codebook")) { model.showingCodebook = true }
        Button(L.text("action.delete_cases")) { model.deleteSelectedCases() }
          .disabled(model.selectedRowIDs.isEmpty)
        Button(L.text("action.drop_variable")) { model.dropSelectedVariable() }
          .disabled((model.dataset?.fields.count ?? 0) <= 1)
        if let dataset = model.dataset {
          Picker(L.text("inspector.variable"), selection: $model.selectedField) {
            ForEach(dataset.fields) { Text($0.name).tag($0.id) }
          }
          if let index = dataset.fields.firstIndex(where: { $0.id == model.selectedField }) {
            let field = dataset.fields[index]
            TextField(L.text("inspector.name"), text: $nameDraft)
              .onSubmit { model.updateField(index, key: "name", value: nameDraft) }
            Picker(
              L.text("inspector.role"),
              selection: Binding(
                get: { field.role }, set: { model.updateField(index, key: "role", value: $0) }
              )
            ) {
              ForEach(["identifier", "characteristic"], id: \.self) {
                Text(L.text("role.\($0)")).tag($0)
              }
            }
            Text(L.text("inspector.measurement")).font(.caption).foregroundStyle(.secondary)
            Picker(
              L.text("inspector.measurement"),
              selection: Binding(
                get: { field.measurement },
                set: { model.updateField(index, key: "measurement", value: $0) }
              )
            ) {
              ForEach(
                ["continuous", "discrete", "ordinal", "binary", "nominal", "multiple_response"],
                id: \.self
              ) {
                Text(L.text("measurement.\($0)")).tag($0)
              }
            }.labelsHidden().frame(maxWidth: .infinity, alignment: .leading)
            Text(L.format("inspector.storage", field.storage)).font(.caption).foregroundStyle(
              .secondary)
          }
          Divider()
          Text(L.text("inspector.scope")).font(.headline)
          Picker(
            L.text("inspector.context"),
            selection: Binding(
              get: { dataset.context }, set: { model.updateContext($0) }
            )
          ) {
            ForEach(["unspecified", "sample", "population"], id: \.self) {
              Text(L.text("context.\($0)")).tag($0)
            }
          }
          TextField(L.text("inspector.unit"), text: $unitDraft)
            .onSubmit { model.updateUnit(unitDraft) }
          Text(L.text("inspector.scope_note")).font(.caption).foregroundStyle(.secondary)
        }
      }.padding(18).disabled(model.busy)
    }.background(.regularMaterial)
      .onChange(of: model.dataset) { _, dataset in
        nameDraft = dataset?.fields.first(where: { $0.id == model.selectedField })?.name ?? ""
        unitDraft = dataset?.observationUnit ?? ""
      }
      .onChange(of: model.selectedField) { _, field in
        nameDraft = model.dataset?.fields.first(where: { $0.id == field })?.name ?? ""
      }
  }
}

private struct CSVImportOptions: View {
  @ObservedObject var model: DocumentModel
  let source: URL
  @State private var delimiter: String
  @State private var decimalPoint = "."
  init(model: DocumentModel, source: URL) {
    self.model = model
    self.source = source
    _delimiter = State(initialValue: source.pathExtension.lowercased() == "tsv" ? "\t" : ",")
  }
  var body: some View {
    VStack(alignment: .leading, spacing: 16) {
      Text(L.text("import.title")).font(.headline)
      Text(source.lastPathComponent).lineLimit(1)
      Picker(L.text("import.delimiter"), selection: $delimiter) {
        Text(L.text("import.comma")).tag(",")
        Text(L.text("import.semicolon")).tag(";")
        Text(L.text("import.tab")).tag("\t")
        Text(L.text("import.pipe")).tag("|")
      }
      Picker(L.text("import.decimal"), selection: $decimalPoint) {
        Text(L.text("import.dot")).tag(".")
        Text(L.text("import.comma")).tag(",")
      }
      Text(L.text("import.note")).font(.caption).foregroundStyle(.secondary)
      if delimiter == decimalPoint {
        Text(L.text("error.csv_options")).font(.caption).foregroundStyle(.red)
      }
      HStack {
        Spacer()
        Button(L.text("action.cancel")) { model.importSource = nil }.keyboardShortcut(.cancelAction)
        Button(L.text("action.import")) {
          model.performImport(url: source, delimiter: delimiter, decimalPoint: decimalPoint)
        }.keyboardShortcut(.defaultAction).disabled(delimiter == decimalPoint || model.busy)
      }
    }.padding(24).frame(width: 420)
  }
}

private struct NewVariableForm: View {
  @ObservedObject var model: DocumentModel
  @State private var name = ""
  @State private var storage = "float64"
  var body: some View {
    VStack(alignment: .leading, spacing: 16) {
      Text(L.text("action.add_variable")).font(.headline)
      TextField(L.text("inspector.name"), text: $name)
      Picker(L.text("variable.storage"), selection: $storage) {
        ForEach(["float64", "int64", "string", "bool", "multiple_response"], id: \.self) {
          Text(L.text("storage.\($0)")).tag($0)
        }
      }
      Text(L.text("variable.note")).font(.caption).foregroundStyle(.secondary)
      HStack {
        Spacer()
        Button(L.text("action.cancel")) { model.showingNewVariable = false }.keyboardShortcut(
          .cancelAction)
        Button(L.text("action.add_variable")) { model.appendVariable(name: name, storage: storage) }
          .keyboardShortcut(.defaultAction)
          .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.busy)
      }
    }.padding(24).frame(width: 420)
  }
}
