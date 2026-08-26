// BazSparkRevitBridge/BazSparkExternalEventHandler.cs
// The core IExternalEventHandler that executes Revit API calls on the main thread.
// The Named Pipe server queues BazSparkCommand objects here;
// when Revit raises the ExternalEvent, this handler dequeues and executes them.

using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using Autodesk.Revit.DB.Architecture;
using Autodesk.Revit.UI;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace BazSparkRevitBridge
{
    /// <summary>
    /// Represents a command sent from the BAZspark Python Local Agent.
    /// </summary>
    public class BazSparkCommand
    {
        [JsonProperty("command_id")]  public string CommandId { get; set; } = Guid.NewGuid().ToString();
        [JsonProperty("action")]      public string Action    { get; set; } = "";
        [JsonProperty("params")]      public JObject Params   { get; set; } = new JObject();
        // The result will be written back here so the pipe server can respond
        public string? ResultJson { get; set; }
        public readonly System.Threading.ManualResetEventSlim Done = new(false);
    }

    /// <summary>
    /// Thread-safe queue + IExternalEventHandler.
    /// Commands are enqueued by the Named Pipe thread; Execute() runs on Revit's main thread.
    /// </summary>
    public class BazSparkExternalEventHandler : IExternalEventHandler
    {
        private readonly ConcurrentQueue<BazSparkCommand> _queue = new();

        /// <summary>Enqueue a command and raise the ExternalEvent.</summary>
        public void Enqueue(BazSparkCommand cmd)
        {
            _queue.Enqueue(cmd);
            Application.BazSparkEvent?.Raise();
        }

        public string GetName() => "BazSparkExternalEventHandler";

        /// <summary>
        /// Called by Revit on the main UI thread when the ExternalEvent is raised.
        /// Drains the queue and executes all pending commands.
        /// </summary>
        public void Execute(UIApplication uiApp)
        {
            while (_queue.TryDequeue(out var cmd))
            {
                try
                {
                    var result = DispatchCommand(uiApp, cmd);
                    cmd.ResultJson = JsonConvert.SerializeObject(
                        new { success = true, data = result });
                }
                catch (Exception ex)
                {
                    cmd.ResultJson = JsonConvert.SerializeObject(
                        new { success = false, error = ex.Message });
                }
                finally
                {
                    cmd.Done.Set(); // Signal the pipe server that we're done
                }
            }
        }

        // ────────────────────────────────────────────────────────────────────────
        // Command Dispatcher
        // ────────────────────────────────────────────────────────────────────────

        private object DispatchCommand(UIApplication uiApp, BazSparkCommand cmd)
        {
            return ExecuteCore(uiApp, cmd.Action, cmd.Params);
        }

        /// <summary>
        /// Executes one registered action. Also used recursively by undo_group
        /// to run composite command sequences inside a TransactionGroup.
        /// The action names here are mirrored in core/command_registry.json —
        /// tests/test_command_registry_contract.py fails the build on drift.
        /// </summary>
        private object ExecuteCore(UIApplication uiApp, string action, JObject p)
        {
            var doc  = uiApp.ActiveUIDocument?.Document
                       ?? throw new InvalidOperationException("No active Revit document.");
            var uidoc = uiApp.ActiveUIDocument;

            return action switch
            {
                // ── Document & Info ──────────────────────────────────────────
                "get_info" => new {
                    title = doc.Title,
                    path  = doc.PathName,
                    is_workshared = doc.IsWorkshared
                },

                "list_elements" => ListElements(doc, p),

                // ── Wall creation ────────────────────────────────────────────
                "create_wall" => CreateWall(doc, p),

                // ── Floor creation ───────────────────────────────────────────
                "create_floor" => CreateFloor(doc, p),

                // ── Door / Window insertion ──────────────────────────────────
                "place_family_instance" => PlaceFamilyInstance(doc, uiApp, p),

                // ── Hosted placement (doors/windows into a wall host) ────────
                "place_family_instance_hosted" => PlaceFamilyInstanceHosted(doc, p),

                // ── Structural column / beam ─────────────────────────────────
                "create_column" => CreateColumn(doc, p),
                "create_beam" => CreateBeam(doc, p),

                // ── Conduit run creation ──────────────────────────────────────
                "create_conduit_run" => CreateConduitRun(doc, p),

                // ── Fire devices placement ───────────────────────────────────
                "place_fire_devices" => PlaceFireDevices(doc, uiApp, p),

                // ── Element deletion ─────────────────────────────────────────
                "delete_element" => DeleteElement(doc, p),

                // ── Parameter read/write ─────────────────────────────────────
                "get_parameter" => GetParameter(doc, p),
                "set_parameter" => SetParameter(doc, p),

                // ── Views ────────────────────────────────────────────────────
                "list_views" => ListViews(doc),
                "list_levels" => ListLevels(doc),
                "list_grids" => ListGrids(doc),

                // ── Document lifecycle ───────────────────────────────────────
                "open_document" => OpenDocument(uiApp, p),
                "close_document" => CloseDocument(doc, p),

                // ── Sheets / datum ───────────────────────────────────────────
                "create_sheet" => CreateSheet(doc, p),
                "create_level" => CreateLevel(doc, p),
                "create_grid" => CreateGrid(doc, p),

                // ── Exports ──────────────────────────────────────────────────
                "export_dwg" => ExportDwg(doc, p),
                "export_pdf" => ExportPdf(doc, p),
                "export_ifc" => ExportIfc(doc, p),

                // ── Selection & viewport ─────────────────────────────────────
                "select_elements" => SelectElements(uidoc, p),
                "get_selection" => GetSelection(doc, uidoc),
                "zoom_to_fit" => ZoomToFit(uiApp),

                // ── Native Revit command passthrough ─────────────────────────
                "post_command" => PostCommand(uiApp, p),

                // ── Composite transactions ───────────────────────────────────
                "undo_group" => UndoGroup(uiApp, p),

                // ── T2 visual awareness ──────────────────────────────────────
                "capture_screen" => new {
                    image_base64 = ScreenCapture.CaptureBase64(uiApp.MainWindowHandle),
                    format = "png"
                },

                // ── Saving ───────────────────────────────────────────────────
                "save" => SaveDocument(doc),

                // ── Speckle Live Stream Integration ──────────────────────────
                "speckle_pull" => SpecklePull(doc, p),

                _ => throw new NotSupportedException($"Unknown action: {action}")
            };
        }

        // ────────────────────────────────────────────────────────────────────────
        // Helpers
        // ────────────────────────────────────────────────────────────────────────

        private static object ListElements(Document doc, JObject p)
        {
            var categoryName = p["category"]?.ToString() ?? "";
            var collector = new FilteredElementCollector(doc).WhereElementIsNotElementType();

            if (!string.IsNullOrEmpty(categoryName) &&
                Enum.TryParse<BuiltInCategory>(categoryName, out var builtIn))
                collector = collector.OfCategory(builtIn);

            var elements = new List<object>();
            foreach (var el in collector)
            {
                elements.Add(new {
                    id       = el.Id.IntegerValue,
                    name     = el.Name,
                    category = el.Category?.Name ?? ""
                });
                if (elements.Count >= 500) break; // Safety cap
            }
            return new { count = elements.Count, elements };
        }

        private static object CreateWall(Document doc, JObject p)
        {
            using var tx = new Transaction(doc, "BazSpark: Create Wall");
            tx.Start();

            var x1 = p["x1"]?.Value<double>() ?? 0;
            var y1 = p["y1"]?.Value<double>() ?? 0;
            var x2 = p["x2"]?.Value<double>() ?? 5000;
            var y2 = p["y2"]?.Value<double>() ?? 0;
            var height = p["height"]?.Value<double>() ?? 3000;

            // Convert mm → feet (Revit internal unit)
            double mmToFt = 1.0 / 304.8;
            var line = Line.CreateBound(
                new XYZ(x1 * mmToFt, y1 * mmToFt, 0),
                new XYZ(x2 * mmToFt, y2 * mmToFt, 0));

            var levelId = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .FirstElementId();

            var wall = Wall.Create(doc, line, levelId, false);
            if (wall is null) throw new InvalidOperationException("Wall creation failed.");

            tx.Commit();
            return new { id = wall.Id.IntegerValue, length_mm = line.Length * 304.8 };
        }

        private static object CreateFloor(Document doc, JObject p)
        {
            using var tx = new Transaction(doc, "BazSpark: Create Floor");
            tx.Start();

            var coords = p["points"]?.ToObject<List<List<double>>>()
                         ?? new List<List<double>> { new() { 0, 0 }, new() { 5000, 0 },
                                                      new() { 5000, 5000 }, new() { 0, 5000 } };
            double mmToFt = 1.0 / 304.8;
            var curveLoop = new CurveLoop();
            for (int i = 0; i < coords.Count; i++)
            {
                var a = coords[i];
                var b = coords[(i + 1) % coords.Count];
                curveLoop.Append(Line.CreateBound(
                    new XYZ(a[0] * mmToFt, a[1] * mmToFt, 0),
                    new XYZ(b[0] * mmToFt, b[1] * mmToFt, 0)));
            }

            var floorType = new FilteredElementCollector(doc)
                .OfClass(typeof(FloorType))
                .FirstElement() as FloorType;

            var levelId = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .FirstElementId();

            var floor = Floor.Create(doc, new List<CurveLoop> { curveLoop },
                floorType!.Id, levelId);
            tx.Commit();
            return new { id = floor.Id.IntegerValue };
        }

        private static bool LoadFamilySymbol(Document doc, string familyFilePath, string symbolName, out FamilySymbol? symbol)
        {
            symbol = null;
            if (string.IsNullOrEmpty(familyFilePath) || !System.IO.File.Exists(familyFilePath))
            {
                return false;
            }

            using var tx = new Transaction(doc, "BazSpark: Load Family Symbol");
            tx.Start();
            bool loaded = doc.LoadFamilySymbol(familyFilePath, symbolName, out symbol);
            if (!loaded)
            {
                if (doc.LoadFamily(familyFilePath, out Family family))
                {
                    foreach (ElementId symId in family.GetFamilySymbolIds())
                    {
                        var fs = doc.GetElement(symId) as FamilySymbol;
                        if (fs != null && (string.Equals(fs.Name, symbolName, StringComparison.OrdinalIgnoreCase) || string.IsNullOrEmpty(symbolName)))
                        {
                            symbol = fs;
                            break;
                        }
                    }
                }
            }
            tx.Commit();
            return symbol != null;
        }

        private static object PlaceFamilyInstance(Document doc, UIApplication uiApp, JObject p)
        {
            var familyName = p["family"]?.ToString() ?? p["family_name"]?.ToString() ?? "";
            var symbolName = p["symbol"]?.ToString() ?? p["symbol_name"]?.ToString() ?? familyName;
            var familyFilePath = p["family_file_path"]?.ToString() ?? p["family_path"]?.ToString() ?? "";

            var x = p["x"]?.Value<double>() ?? 0;
            var y = p["y"]?.Value<double>() ?? 0;
            var z = p["z"]?.Value<double>() ?? 0;
            double mmToFt = 1.0 / 304.8;

            var symbol = new FilteredElementCollector(doc)
                .OfClass(typeof(FamilySymbol))
                .OfType<FamilySymbol>()
                .FirstOrDefault(fs =>
                    (!string.IsNullOrEmpty(symbolName) && string.Equals(fs.Name, symbolName, StringComparison.OrdinalIgnoreCase)) ||
                    (!string.IsNullOrEmpty(familyName) && fs.FamilyName.IndexOf(familyName, StringComparison.OrdinalIgnoreCase) >= 0));

            if (symbol == null && !string.IsNullOrEmpty(familyFilePath))
            {
                LoadFamilySymbol(doc, familyFilePath, symbolName, out symbol);
            }

            if (symbol == null)
            {
                throw new InvalidOperationException($"Family Symbol '{symbolName}' (Family: '{familyName}') not found or loaded.");
            }

            using var tx = new Transaction(doc, "BazSpark: Place Family");
            tx.Start();
            if (!symbol.IsActive)
            {
                symbol.Activate();
                doc.Regenerate();
            }

            var inst = doc.Create.NewFamilyInstance(
                new XYZ(x * mmToFt, y * mmToFt, z * mmToFt),
                symbol,
                Autodesk.Revit.DB.Structure.StructuralType.NonStructural);

            var parameters = p["parameters"] as JObject;
            if (parameters != null && inst != null)
            {
                foreach (var prop in parameters.Properties())
                {
                    var param = inst.LookupParameter(prop.Name);
                    if (param != null && !param.IsReadOnly)
                    {
                        param.SetValueString(prop.Value?.ToString() ?? "");
                    }
                }
            }

            tx.Commit();
            return new { id = inst.Id.IntegerValue, family = symbol.FamilyName, symbol = symbol.Name, success = true };
        }

        private static object CreateConduitRun(Document doc, JObject p)
        {
            double x1 = p["x1"]?.Value<double>() ?? 0;
            double y1 = p["y1"]?.Value<double>() ?? 0;
            double z1 = p["z1"]?.Value<double>() ?? 0;

            double x2 = p["x2"]?.Value<double>() ?? 1000;
            double y2 = p["y2"]?.Value<double>() ?? 0;
            double z2 = p["z2"]?.Value<double>() ?? 0;

            if (p["start_point"] is JArray startArr && startArr.Count >= 2)
            {
                x1 = startArr[0].Value<double>();
                y1 = startArr[1].Value<double>();
                z1 = startArr.Count >= 3 ? startArr[2].Value<double>() : 0;
            }
            if (p["end_point"] is JArray endArr && endArr.Count >= 2)
            {
                x2 = endArr[0].Value<double>();
                y2 = endArr[1].Value<double>();
                z2 = endArr.Count >= 3 ? endArr[2].Value<double>() : 0;
            }

            double diameterMm = p["diameter"]?.Value<double>() ?? p["diameter_mm"]?.Value<double>() ?? 20.0;
            double mmToFt = 1.0 / 304.8;

            XYZ startPt = new XYZ(x1 * mmToFt, y1 * mmToFt, z1 * mmToFt);
            XYZ endPt = new XYZ(x2 * mmToFt, y2 * mmToFt, z2 * mmToFt);

            ElementId levelId = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .FirstElementId();

            if (p["level_id"] != null)
            {
                levelId = new ElementId(p["level_id"].Value<int>());
            }

            ElementId conduitTypeId = new FilteredElementCollector(doc)
                .OfClass(typeof(Autodesk.Revit.DB.Electrical.ConduitType))
                .FirstElementId();

            using var tx = new Transaction(doc, "BazSpark: Create Conduit Run");
            tx.Start();

            var conduit = Autodesk.Revit.DB.Electrical.Conduit.Create(doc, conduitTypeId, startPt, endPt, levelId);
            if (conduit == null)
            {
                throw new InvalidOperationException("Failed to create electrical conduit run.");
            }

            double diameterFt = diameterMm * mmToFt;
            Parameter diamParam = conduit.get_Parameter(BuiltInParameter.RBS_CONDUIT_DIAMETER_PARAM)
                                  ?? conduit.LookupParameter("Diameter")
                                  ?? conduit.LookupParameter("Nominal Diameter");
            if (diamParam != null && !diamParam.IsReadOnly)
            {
                diamParam.Set(diameterFt);
            }

            string systemType = p["system_type"]?.ToString() ?? "";
            if (!string.IsNullOrEmpty(systemType))
            {
                Parameter sysParam = conduit.LookupParameter("System Type")
                                     ?? conduit.LookupParameter("System Classification");
                if (sysParam != null && !sysParam.IsReadOnly)
                {
                    sysParam.SetValueString(systemType);
                }
            }

            tx.Commit();

            return new
            {
                id = conduit.Id.IntegerValue,
                length_mm = startPt.DistanceTo(endPt) * 304.8,
                diameter_mm = diameterMm,
                success = true
            };
        }

        private static object PlaceFireDevices(Document doc, UIApplication uiApp, JObject p)
        {
            var devicesArray = p["devices"] as JArray;
            var placedList = new List<object>();

            if (devicesArray != null)
            {
                foreach (JObject devObj in devicesArray)
                {
                    var res = PlaceFamilyInstance(doc, uiApp, devObj);
                    placedList.Add(res);
                }
            }
            else
            {
                var res = PlaceFamilyInstance(doc, uiApp, p);
                placedList.Add(res);
            }

            return new { count = placedList.Count, devices = placedList, success = true };
        }

        private static object DeleteElement(Document doc, JObject p)
        {
            // A1 FIX: backend sends "element_id"; legacy callers send "id".
            int? rawId = p["element_id"]?.Value<int>() ?? p["id"]?.Value<int>();
            if (rawId is null)
                throw new ArgumentException("element_id parameter is required.");
            var id = new ElementId(rawId.Value);
            using var tx = new Transaction(doc, "BazSpark: Delete");
            tx.Start();
            doc.Delete(id);
            tx.Commit();
            return new { deleted_id = id.IntegerValue, success = true };
        }

        private static object GetParameter(Document doc, JObject p)
        {
            int? rawId = p["element_id"]?.Value<int>() ?? p["id"]?.Value<int>();
            if (rawId is null)
                throw new ArgumentException("element_id parameter is required.");
            var id  = new ElementId(rawId.Value);
            var name = p["name"]?.ToString() ?? "";
            var el   = doc.GetElement(id) ?? throw new InvalidOperationException("Element not found.");
            var param = el.LookupParameter(name) ?? throw new InvalidOperationException($"Parameter '{name}' not found.");
            return new { name, value = param.AsValueString() };
        }

        private static object SetParameter(Document doc, JObject p)
        {
            int? rawId = p["element_id"]?.Value<int>() ?? p["id"]?.Value<int>();
            if (rawId is null)
                throw new ArgumentException("element_id parameter is required.");
            var id   = new ElementId(rawId.Value);
            var name  = p["name"]?.ToString() ?? "";
            var value = p["value"]?.ToString() ?? "";
            var el    = doc.GetElement(id) ?? throw new InvalidOperationException("Element not found.");
            var param = el.LookupParameter(name) ?? throw new InvalidOperationException($"Parameter '{name}' not found.");

            using var tx = new Transaction(doc, "BazSpark: Set Parameter");
            tx.Start();
            param.SetValueString(value);
            tx.Commit();
            return new { updated = true, success = true };
        }

        private static object ListViews(Document doc)
        {
            var views = new List<object>();
            foreach (View v in new FilteredElementCollector(doc).OfClass(typeof(View)))
            {
                if (!v.IsTemplate)
                    views.Add(new { id = v.Id.IntegerValue, name = v.Name, type = v.ViewType.ToString() });
            }
            return new { count = views.Count, views };
        }

        private static object ListLevels(Document doc)
        {
            var levels = new List<object>();
            foreach (Level lvl in new FilteredElementCollector(doc).OfClass(typeof(Level)))
            {
                levels.Add(new { id = lvl.Id.IntegerValue, name = lvl.Name, elevation_mm = lvl.Elevation * 304.8 });
            }
            return new { count = levels.Count, elements = levels };
        }

        private static object ListGrids(Document doc)
        {
            var grids = new List<object>();
            foreach (Grid grid in new FilteredElementCollector(doc).OfClass(typeof(Grid)))
            {
                grids.Add(new { id = grid.Id.IntegerValue, name = grid.Name });
            }
            return new { count = grids.Count, elements = grids };
        }

        // ────────────────────────────────────────────────────────────────────
        // B1: full-control command surface
        // ────────────────────────────────────────────────────────────────────

        private const double MmToFt = 1.0 / 304.8;

        private static object OpenDocument(UIApplication uiApp, JObject p)
        {
            string path = p["filepath"]?.ToString()
                ?? throw new ArgumentException("filepath parameter is required.");
            if (!System.IO.File.Exists(path))
                throw new System.IO.FileNotFoundException($"Document not found: {path}");

            uiApp.OpenAndActivateDocument(path, new OpenDocumentOptions(), false);
            return new { opened = true, path };
        }

        private static object CloseDocument(Document doc, JObject p)
        {
            bool saveChanges = p["save_changes"]?.Value<bool>() ?? true;
            string title = doc.Title;
            if (saveChanges && doc.IsModified && !string.IsNullOrEmpty(doc.PathName))
            {
                doc.Save();
            }
            doc.Close(false);
            return new { closed = true, title };
        }

        private static object CreateSheet(Document doc, JObject p)
        {
            string titleblockName = p["titleblock_name"]?.ToString() ?? "";

            FamilySymbol? tblock = null;
            foreach (FamilySymbol fs in new FilteredElementCollector(doc)
                         .OfCategory(BuiltInCategory.OST_TitleBlocks)
                         .OfClass(typeof(FamilySymbol)))
            {
                if (string.IsNullOrEmpty(titleblockName) ||
                    string.Equals(fs.Name, titleblockName, StringComparison.OrdinalIgnoreCase))
                {
                    tblock = fs;
                    break;
                }
            }
            if (tblock is null)
                throw new InvalidOperationException(
                    $"Title block '{titleblockName}' not found in the document.");

            View? viewToPlace = null;
            int? viewIdRaw = p["view_id"]?.Value<int>();
            if (viewIdRaw.HasValue)
                viewToPlace = doc.GetElement(new ElementId(viewIdRaw.Value)) as View;

            using var tx = new Transaction(doc, "BazSpark: Create Sheet");
            tx.Start();
            if (!tblock.IsActive)
            {
                tblock.Activate();
                doc.Regenerate();
            }

            ViewSheet sheet = ViewSheet.Create(doc, tblock.Id);

            string sheetNumber = p["sheet_number"]?.ToString() ?? "";
            string sheetName = p["sheet_name"]?.ToString() ?? "";
            if (!string.IsNullOrEmpty(sheetNumber))
                sheet.LookupParameter("Sheet Number")?.Set(sheetNumber);
            if (!string.IsNullOrEmpty(sheetName))
                sheet.LookupParameter("Sheet Name")?.Set(sheetName);

            if (viewToPlace != null && viewToPlace.CanBePlacedOnAViewSheet(sheet))
            {
                Viewport.Create(doc, sheet.Id, viewToPlace.Id, XYZ.Zero);
            }

            tx.Commit();
            return new { id = sheet.Id.IntegerValue, number = sheet.SheetNumber, success = true };
        }

        private static object CreateLevel(Document doc, JObject p)
        {
            string name = p["name"]?.ToString()
                ?? throw new ArgumentException("name parameter is required.");
            double elevationMm = p["elevation_mm"]?.Value<double>()
                ?? throw new ArgumentException("elevation_mm parameter is required.");

            using var tx = new Transaction(doc, "BazSpark: Create Level");
            tx.Start();
            Level level = Level.Create(doc, elevationMm * MmToFt);
            level.Name = name;
            tx.Commit();
            return new { id = level.Id.IntegerValue, name = level.Name, success = true };
        }

        private static object CreateGrid(Document doc, JObject p)
        {
            double x1 = p["x1"]?.Value<double>() ?? 0;
            double y1 = p["y1"]?.Value<double>() ?? 0;
            double x2 = p["x2"]?.Value<double>() ?? 0;
            double y2 = p["y2"]?.Value<double>() ?? 10000;

            if (p["start_point"] is JArray sArr && sArr.Count >= 2)
            {
                x1 = sArr[0].Value<double>(); y1 = sArr[1].Value<double>();
            }
            if (p["end_point"] is JArray eArr && eArr.Count >= 2)
            {
                x2 = eArr[0].Value<double>(); y2 = eArr[1].Value<double>();
            }

            using var tx = new Transaction(doc, "BazSpark: Create Grid");
            tx.Start();
            Grid grid = Grid.Create(doc, Line.CreateBound(
                new XYZ(x1 * MmToFt, y1 * MmToFt, 0),
                new XYZ(x2 * MmToFt, y2 * MmToFt, 0)));
            string? name = p["name"]?.ToString();
            if (!string.IsNullOrEmpty(name)) grid.Name = name;
            tx.Commit();
            return new { id = grid.Id.IntegerValue, name = grid.Name, success = true };
        }

        private static object CreateColumn(Document doc, JObject p)
        {
            double[] pt;
            if (p["location_point"] is JArray arr && arr.Count >= 2)
            {
                pt = new[] {
                    arr[0].Value<double>(), arr[1].Value<double>(),
                    arr.Count >= 3 ? arr[2].Value<double>() : 0d };
            }
            else
            {
                throw new ArgumentException("location_point parameter is required.");
            }
            double heightMm = p["height"]?.Value<double>() ?? 3000;
            string typeName = p["column_type"]?.ToString() ?? "";

            FamilySymbol? symbol = FindFirstFamilySymbol(doc, BuiltInCategory.OST_StructuralColumns, typeName);
            if (symbol is null)
                throw new InvalidOperationException("No structural column family type found in the document.");

            ElementId levelId = new FilteredElementCollector(doc)
                .OfClass(typeof(Level)).FirstElementId();

            using var tx = new Transaction(doc, "BazSpark: Create Column");
            tx.Start();
            if (!symbol.IsActive) { symbol.Activate(); doc.Regenerate(); }
            var level = doc.GetElement(levelId) as Level
                ?? throw new InvalidOperationException("No level found for column placement.");
            var inst = doc.Create.NewFamilyInstance(
                new XYZ(pt[0] * MmToFt, pt[1] * MmToFt, pt[2] * MmToFt),
                symbol, level,
                Autodesk.Revit.DB.Structure.StructuralType.Column);
            tx.Commit();
            return new { id = inst.Id.IntegerValue, success = true };
        }

        private static object CreateBeam(Document doc, JObject p)
        {
            double x1, y1, z1, x2, y2, z2;
            ReadStartEnd(p, out x1, out y1, out z1, out x2, out y2, out z2);
            string typeName = p["beam_type"]?.ToString() ?? "";

            FamilySymbol? symbol = FindFirstFamilySymbol(doc, BuiltInCategory.OST_StructuralFraming, typeName);
            if (symbol is null)
                throw new InvalidOperationException("No structural framing family type found in the document.");

            ElementId levelId = new FilteredElementCollector(doc)
                .OfClass(typeof(Level)).FirstElementId();

            using var tx = new Transaction(doc, "BazSpark: Create Beam");
            tx.Start();
            if (!symbol.IsActive) { symbol.Activate(); doc.Regenerate(); }
            var line = Line.CreateBound(
                new XYZ(x1 * MmToFt, y1 * MmToFt, z1 * MmToFt),
                new XYZ(x2 * MmToFt, y2 * MmToFt, z2 * MmToFt));
            var inst = doc.Create.NewFamilyInstance(
                line, symbol, levelId,
                Autodesk.Revit.DB.Structure.StructuralType.Beam);
            tx.Commit();
            return new { id = inst.Id.IntegerValue, length_mm = line.Length * 304.8, success = true };
        }

        private static void ReadStartEnd(JObject p,
            out double x1, out double y1, out double z1,
            out double x2, out double y2, out double z2)
        {
            x1 = y1 = z1 = 0; x2 = y2 = 0; z2 = 0;
            if (p["start_point"] is JArray sArr && sArr.Count >= 2)
            {
                x1 = sArr[0].Value<double>(); y1 = sArr[1].Value<double>();
                z1 = sArr.Count >= 3 ? sArr[2].Value<double>() : 0;
            }
            if (p["end_point"] is JArray eArr && eArr.Count >= 2)
            {
                x2 = eArr[0].Value<double>(); y2 = eArr[1].Value<double>();
                z2 = eArr.Count >= 3 ? eArr[2].Value<double>() : 0;
            }
        }

        private static FamilySymbol? FindFirstFamilySymbol(
            Document doc, BuiltInCategory category, string nameContains)
        {
            foreach (FamilySymbol fs in new FilteredElementCollector(doc)
                         .OfCategory(category)
                         .OfClass(typeof(FamilySymbol))
                         .Cast<FamilySymbol>())
            {
                if (string.IsNullOrEmpty(nameContains) ||
                    fs.Name.IndexOf(nameContains, StringComparison.OrdinalIgnoreCase) >= 0 ||
                    fs.FamilyName.IndexOf(nameContains, StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return fs;
                }
            }
            return null;
        }

        private static object PlaceFamilyInstanceHosted(Document doc, JObject p)
        {
            int? hostIdRaw = p["host_id"]?.Value<int>();
            double x = p["x"]?.Value<double>() ?? 0;
            double y = p["y"]?.Value<double>() ?? 0;
            double z = p["z"]?.Value<double>() ?? 0;
            string familyName = p["family"]?.ToString() ?? p["family_name"]?.ToString() ?? "";

            var symbol = new FilteredElementCollector(doc)
                .OfClass(typeof(FamilySymbol))
                .OfType<FamilySymbol>()
                .FirstOrDefault(fs =>
                    (!string.IsNullOrEmpty(familyName) &&
                     (string.Equals(fs.Name, familyName, StringComparison.OrdinalIgnoreCase) ||
                      fs.FamilyName.IndexOf(familyName, StringComparison.OrdinalIgnoreCase) >= 0)));
            if (symbol is null)
                throw new InvalidOperationException($"Family '{familyName}' not found in the document.");

            HostObject? host = null;
            if (hostIdRaw.HasValue)
                host = doc.GetElement(new ElementId(hostIdRaw.Value)) as HostObject;

            using var tx = new Transaction(doc, "BazSpark: Place Hosted Instance");
            tx.Start();
            if (!symbol.IsActive) { symbol.Activate(); doc.Regenerate(); }

            var xyz = new XYZ(x * MmToFt, y * MmToFt, z * MmToFt);
            FamilyInstance inst;
            if (host != null)
            {
                inst = doc.Create.NewFamilyInstance(
                    xyz, symbol, host,
                    doc.GetElement(host.LevelId) as Level,
                    Autodesk.Revit.DB.Structure.StructuralType.NonStructural);
            }
            else
            {
                inst = doc.Create.NewFamilyInstance(
                    xyz, symbol,
                    Autodesk.Revit.DB.Structure.StructuralType.NonStructural);
            }

            ApplyNamedParameters(inst, p["parameters"] as JObject);
            tx.Commit();
            return new { id = inst.Id.IntegerValue, hosted = host != null, success = true };
        }

        private static void ApplyNamedParameters(Element element, JObject? parameters)
        {
            if (parameters is null || element is null) return;
            foreach (var prop in parameters.Properties())
            {
                var param = element.LookupParameter(prop.Name);
                if (param != null && !param.IsReadOnly)
                {
                    param.SetValueString(prop.Value?.ToString() ?? "");
                }
            }
        }

        private static object ExportDwg(Document doc, JObject p)
        {
            string filepath = p["filepath"]?.ToString()
                ?? throw new ArgumentException("filepath parameter is required.");
            string folder = System.IO.Path.GetDirectoryName(filepath) ?? ".";
            string name = System.IO.Path.GetFileNameWithoutExtension(filepath);

            var viewIds = ResolveExportViews(doc, p);
            var options = new DWGExportOptions();

            using var tx = new Transaction(doc, "BazSpark: Export DWG");
            tx.Start();
            bool ok = doc.Export(folder, name, viewIds, options);
            tx.Commit();
            return new { exported = ok, path = filepath, format = "dwg", success = ok };
        }

        private static object ExportPdf(Document doc, JObject p)
        {
            string filepath = p["filepath"]?.ToString()
                ?? throw new ArgumentException("filepath parameter is required.");
            string folder = System.IO.Path.GetDirectoryName(filepath) ?? ".";
            string name = System.IO.Path.GetFileNameWithoutExtension(filepath);

            var viewIds = ResolveExportViews(doc, p);
            var options = new PDFExportOptions();

            // PDF export writes <name>.pdf into folder; no transaction required.
            bool ok = doc.Export(folder, name, viewIds, options);
            return new { exported = ok, path = filepath, format = "pdf", success = ok };
        }

        private static object ExportIfc(Document doc, JObject p)
        {
            string filepath = p["filepath"]?.ToString()
                ?? throw new ArgumentException("filepath parameter is required.");
            string folder = System.IO.Path.GetDirectoryName(filepath) ?? ".";
            string name = System.IO.Path.GetFileNameWithoutExtension(filepath);

            var options = new IFCExportOptions();

            using var tx = new Transaction(doc, "BazSpark: Export IFC");
            tx.Start();
            doc.Export(folder, name, options);
            tx.Commit();
            return new { exported = true, path = filepath, format = "ifc", success = true };
        }

        private static ICollection<ElementId> ResolveExportViews(Document doc, JObject p)
        {
            int? viewId = p["view_id"]?.Value<int>();
            if (viewId.HasValue)
                return new List<ElementId> { new ElementId(viewId.Value) };

            var ids = new List<ElementId>();
            foreach (ElementId id in new FilteredElementCollector(doc)
                         .OfClass(typeof(View))
                         .Cast<View>()
                         .Where(v => !v.IsTemplate && v.ViewType == ViewType.FloorPlan)
                         .Select(v => v.Id))
            {
                ids.Add(id);
            }
            return ids.Count > 0 ? ids : new List<ElementId> { doc.ActiveView.Id };
        }

        private static object SelectElements(Autodesk.Revit.UI.UIDocument uidoc, JObject p)
        {
            var rawIds = p["element_ids"] as JArray
                ?? throw new ArgumentException("element_ids parameter is required.");
            var ids = new List<ElementId>();
            foreach (var token in rawIds)
                ids.Add(new ElementId(token.Value<int>()));

            uidoc.Selection.SetElementIds(ids);
            return new { selected = ids.Count, success = true };
        }

        private static object GetSelection(Document doc, Autodesk.Revit.UI.UIDocument uidoc)
        {
            var items = new List<object>();
            foreach (ElementId id in uidoc.Selection.GetElementIds())
            {
                var el = doc.GetElement(id);
                items.Add(new { id = id.IntegerValue, name = el?.Name ?? "" });
            }
            return new { count = items.Count, elements = items };
        }

        private static object ZoomToFit(UIApplication uiApp)
        {
            var uidoc = uiApp.ActiveUIDocument
                ?? throw new InvalidOperationException("No active Revit document.");
            View activeView = uidoc.ActiveView;
            foreach (UIView uiv in uiApp.GetOpenUIViews())
            {
                if (uiv.ViewId == activeView.Id)
                {
                    uiv.ZoomToFit();
                    uidoc.RefreshActiveView();
                    return new { zoomed = true, success = true };
                }
            }
            throw new InvalidOperationException("Active view has no open UIView.");
        }

        private static object PostCommand(UIApplication uiApp, JObject p)
        {
            string commandName = p["postable_command"]?.ToString()
                ?? throw new ArgumentException("postable_command parameter is required.");

            if (!Enum.TryParse<PostableCommand>(commandName, ignoreCase: true, out var pc))
                throw new ArgumentException($"Unknown PostableCommand: {commandName}");

            uiApp.PostCommand(pc);
            // PostCommand queues the command — it runs after this handler returns.
            return new { queued = true, command = commandName, success = true };
        }

        private static object UndoGroup(UIApplication uiApp, JObject p)
        {
            string name = p["name"]?.ToString() ?? "BazSpark Composite";
            var actions = p["actions"] as JArray
                ?? throw new ArgumentException("actions parameter is required (array of {action, params}).");

            var doc = uiApp.ActiveUIDocument?.Document
                ?? throw new InvalidOperationException("No active Revit document.");

            using (var tg = new TransactionGroup(doc, name))
            {
                tg.Start();
                try
                {
                    int executed = 0;
                    var results = new List<object>();
                    foreach (JObject sub in actions.OfType<JObject>())
                    {
                        string subAction = sub["action"]?.ToString()
                            ?? throw new ArgumentException("Each action entry needs 'action'.");
                        var subParams = sub["params"] as JObject ?? new JObject();
                        object result = ExecuteCore(uiApp, subAction, subParams);
                        results.Add(result);
                        executed++;
                    }
                    tg.Assimilate();
                    return new { executed, results, success = true };
                }
                catch
                {
                    // Dispose without Assimilate rolls back every sub-transaction.
                    throw;
                }
            }
        }

        private static object SaveDocument(Document doc)
        {
            if (string.IsNullOrEmpty(doc.PathName))
                return new { saved = false, reason = "Document has no path (unsaved new file)" };
            doc.Save();
            return new { saved = true, path = doc.PathName };
        }

        private static object SpecklePull(Document doc, JObject p)
        {
            string streamId = p["stream_id"]?.ToString() ?? throw new ArgumentException("stream_id parameter is required.");
            string serverUrl = p["server_url"]?.ToString() ?? "https://speckle.xyz";
            string token = p["token"]?.ToString() ?? throw new ArgumentException("token parameter is required.");

            // Pull elements from Speckle stream asynchronously
            var elements = System.Threading.Tasks.Task.Run(() => SpeckleConnector.ReceiveModel(streamId, serverUrl, token)).GetAwaiter().GetResult();
            
            // Build in Revit on Revit main thread
            int created = SpeckleConnector.BuildElementsInRevit(doc, elements);
            return new { success = true, pulled_count = elements.Count, created_count = created };
        }
    }
}
