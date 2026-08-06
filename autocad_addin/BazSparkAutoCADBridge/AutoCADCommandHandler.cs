using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Colors;

namespace BazSparkAutoCADBridge
{
    /// <summary>
    /// Executes drawing and query operations using the AutoCAD .NET API on the active document.
    /// Runs thread-safely because the caller locks the document.
    /// </summary>
    public static class AutoCADCommandHandler
    {
        public static object DispatchCommand(Document doc, string action, JObject p)
        {
            return action switch
            {
                "get_info" => GetInfo(doc),
                "draw_line" => DrawLine(doc, p),
                "draw_polyline" => DrawPolyline(doc, p),
                "draw_circle" => DrawCircle(doc, p),
                "draw_text" => DrawText(doc, p),
                "insert_block" => InsertBlock(doc, p),
                "insert_block_instance" => InsertBlock(doc, p),
                "get_block_attributes" => GetBlockAttributes(doc, p),
                "query_elements" => QueryElements(doc, p),
                "get_entity_info" => GetEntityInfo(doc, p),
                "delete_entity" => DeleteEntity(doc, p),
                "modify_entity" => ModifyEntity(doc, p),
                "save" => SaveDocument(doc),
                "speckle_push" => SpecklePush(doc, p),
                _ => throw new NotSupportedException($"Unknown action: {action}")
            };
        }

        private static object GetInfo(Document doc)
        {
            return new
            {
                filename = doc.Name,
                database = doc.Database.Filename,
                measurement = doc.Database.Measurement == MeasurementValue.English ? "Imperial" : "Metric",
                insunits = doc.Database.Insunits.ToString()
            };
        }

        private static object DrawLine(Document doc, JObject p)
        {
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                Point3d start = GetPoint(p["start_point"] as JArray);
                Point3d end = GetPoint(p["end_point"] as JArray);

                using (Line line = new Line(start, end))
                {
                    line.SetDatabaseDefaults();
                    ApplyProperties(db, tr, line, p);

                    btr.AppendEntity(line);
                    tr.AddNewlyCreatedDBObject(line, true);
                    tr.Commit();

                    return new { handle = line.Handle.ToString(), success = true };
                }
            }
        }

        private static object DrawPolyline(Document doc, JObject p)
        {
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                using (Polyline pl = new Polyline())
                {
                    pl.SetDatabaseDefaults();

                    JArray? vertices = p["vertices"] as JArray;
                    if (vertices != null)
                    {
                        for (int i = 0; i < vertices.Count; i++)
                        {
                            JArray? vertex = vertices[i] as JArray;
                            if (vertex != null && vertex.Count >= 2)
                            {
                                double x = vertex[0].Value<double>();
                                double y = vertex[1].Value<double>();
                                pl.AddVertexAt(i, new Point2d(x, y), 0, 0, 0);
                            }
                        }
                    }

                    if (p["closed"]?.Value<bool>() == true)
                    {
                        pl.Closed = true;
                    }

                    ApplyProperties(db, tr, pl, p);

                    btr.AppendEntity(pl);
                    tr.AddNewlyCreatedDBObject(pl, true);
                    tr.Commit();

                    return new { handle = pl.Handle.ToString(), success = true };
                }
            }
        }

        private static object DrawCircle(Document doc, JObject p)
        {
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                Point3d center = GetPoint(p["center"] as JArray);
                double radius = p["radius"]?.Value<double>() ?? 1.0;

                using (Circle circle = new Circle(center, Vector3d.ZAxis, radius))
                {
                    circle.SetDatabaseDefaults();
                    ApplyProperties(db, tr, circle, p);

                    btr.AppendEntity(circle);
                    tr.AddNewlyCreatedDBObject(circle, true);
                    tr.Commit();

                    return new { handle = circle.Handle.ToString(), success = true };
                }
            }
        }

        private static object DrawText(Document doc, JObject p)
        {
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                string textStr = p["text"]?.ToString() ?? "";
                Point3d insertPoint = GetPoint(p["insertion_point"] as JArray);
                double height = p["height"]?.Value<double>() ?? 0.2;

                using (DBText text = new DBText())
                {
                    text.SetDatabaseDefaults();
                    text.TextString = textStr;
                    text.Position = insertPoint;
                    text.Height = height;
                    ApplyProperties(db, tr, text, p);

                    btr.AppendEntity(text);
                    tr.AddNewlyCreatedDBObject(text, true);
                    tr.Commit();

                    return new { handle = text.Handle.ToString(), success = true };
                }
            }
        }

        private static object DeleteEntity(Document doc, JObject p)
        {
            string handleStr = p["handle"]?.ToString() ?? throw new ArgumentException("Entity handle required.");
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                long ln = Convert.ToInt64(handleStr, 16);
                Handle h = new Handle(ln);
                ObjectId id = db.GetObjectId(false, h, 0);
                DBObject obj = tr.GetObject(id, OpenMode.ForWrite);
                
                obj.Erase();
                tr.Commit();

                return new { handle = handleStr, deleted = true };
            }
        }

        private static object ModifyEntity(Document doc, JObject p)
        {
            string handleStr = p["handle"]?.ToString() ?? throw new ArgumentException("Entity handle required.");
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                long ln = Convert.ToInt64(handleStr, 16);
                Handle h = new Handle(ln);
                ObjectId id = db.GetObjectId(false, h, 0);
                Entity ent = (Entity)tr.GetObject(id, OpenMode.ForWrite);

                var props = p["properties"] as JObject;
                if (props != null)
                {
                    ApplyProperties(db, tr, ent, props);

                    // Type specific geometry modifications
                    if (ent is Line line)
                    {
                        if (props["start_point"] != null) line.StartPoint = GetPoint(props["start_point"] as JArray);
                        if (props["end_point"] != null) line.EndPoint = GetPoint(props["end_point"] as JArray);
                    }
                    else if (ent is Circle circle)
                    {
                        if (props["center"] != null) circle.Center = GetPoint(props["center"] as JArray);
                        if (props["radius"] != null) circle.Radius = props["radius"].Value<double>();
                    }
                    else if (ent is DBText dbText)
                    {
                        if (props["text"] != null) dbText.TextString = props["text"].ToString();
                        if (props["insertion_point"] != null) dbText.Position = GetPoint(props["insertion_point"] as JArray);
                        if (props["height"] != null) dbText.Height = props["height"].Value<double>();
                    }
                }
                tr.Commit();

                return new { handle = handleStr, updated = true };
            }
        }

        private static object InsertBlock(Document doc, JObject p)
        {
            string blockName = p["block_name"]?.ToString()
                ?? p["name"]?.ToString()
                ?? throw new ArgumentException("Block name ('block_name' or 'name') is required.");

            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                if (!bt.Has(blockName))
                {
                    throw new InvalidOperationException($"Block definition '{blockName}' does not exist in document.");
                }

                BlockTableRecord modelSpace = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForWrite);
                ObjectId blockDefId = bt[blockName];

                Point3d insertPoint = GetPoint(p["insertion_point"] as JArray ?? p["position"] as JArray);

                double rotation = 0.0;
                if (p["rotation"] != null)
                {
                    rotation = p["rotation"].Value<double>();
                }
                else if (p["rotation_deg"] != null)
                {
                    rotation = p["rotation_deg"].Value<double>() * (Math.PI / 180.0);
                }

                double scaleX = p["scale_x"]?.Value<double>() ?? p["scale"]?.Value<double>() ?? 1.0;
                double scaleY = p["scale_y"]?.Value<double>() ?? p["scale"]?.Value<double>() ?? 1.0;
                double scaleZ = p["scale_z"]?.Value<double>() ?? p["scale"]?.Value<double>() ?? 1.0;

                using (BlockReference blockRef = new BlockReference(insertPoint, blockDefId))
                {
                    blockRef.SetDatabaseDefaults();
                    blockRef.ScaleFactors = new Scale3d(scaleX, scaleY, scaleZ);
                    blockRef.Rotation = rotation;

                    ApplyProperties(db, tr, blockRef, p);

                    modelSpace.AppendEntity(blockRef);
                    tr.AddNewlyCreatedDBObject(blockRef, true);

                    // Process block attribute definitions
                    BlockTableRecord blockDef = (BlockTableRecord)tr.GetObject(blockDefId, OpenMode.ForRead);
                    JObject? attributesObj = p["attributes"] as JObject ?? p["attribute_values"] as JObject;

                    if (blockDef.HasAttributeDefinitions)
                    {
                        foreach (ObjectId id in blockDef)
                        {
                            DBObject obj = tr.GetObject(id, OpenMode.ForRead);
                            if (obj is AttributeDefinition attDef && !attDef.Constant)
                            {
                                using (AttributeReference attRef = new AttributeReference())
                                {
                                    attRef.SetAttributeFromBlock(attDef, blockRef.BlockTransform);
                                    attRef.Position = attDef.Position.TransformBy(blockRef.BlockTransform);
                                    attRef.Rotation = attDef.Rotation + rotation;

                                    string tag = attDef.Tag;
                                    if (attributesObj != null)
                                    {
                                        string? customVal = null;
                                        foreach (var prop in attributesObj.Properties())
                                        {
                                            if (string.Equals(prop.Name, tag, StringComparison.OrdinalIgnoreCase))
                                            {
                                                customVal = prop.Value?.ToString();
                                                break;
                                            }
                                        }

                                        if (customVal != null)
                                        {
                                            attRef.TextString = customVal;
                                        }
                                        else
                                        {
                                            attRef.TextString = attDef.TextString;
                                        }
                                    }
                                    else
                                    {
                                        attRef.TextString = attDef.TextString;
                                    }

                                    blockRef.AttributeCollection.AppendAttribute(attRef);
                                    tr.AddNewlyCreatedDBObject(attRef, true);
                                }
                            }
                        }
                    }

                    tr.Commit();
                    return new { handle = blockRef.Handle.ToString(), name = blockName, success = true };
                }
            }
        }

        private static object GetBlockAttributes(Document doc, JObject p)
        {
            string handleStr = p["handle"]?.ToString() ?? throw new ArgumentException("Entity handle required.");
            Database db = doc.Database;
            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                long ln = Convert.ToInt64(handleStr, 16);
                Handle h = new Handle(ln);
                ObjectId id = db.GetObjectId(false, h, 0);
                DBObject obj = tr.GetObject(id, OpenMode.ForRead);

                if (!(obj is BlockReference blockRef))
                {
                    throw new InvalidOperationException($"Entity handle '{handleStr}' is not a BlockReference.");
                }

                var attributesDict = new Dictionary<string, string>();
                foreach (ObjectId attId in blockRef.AttributeCollection)
                {
                    DBObject attObj = tr.GetObject(attId, OpenMode.ForRead);
                    if (attObj is AttributeReference attRef)
                    {
                        attributesDict[attRef.Tag] = attRef.TextString;
                    }
                }

                var dynamicProps = new Dictionary<string, object>();
                if (blockRef.IsDynamicBlock)
                {
                    DynamicBlockReferencePropertyCollection props = blockRef.DynamicBlockReferencePropertyCollection;
                    foreach (DynamicBlockReferenceProperty prop in props)
                    {
                        if (prop.Value != null)
                        {
                            dynamicProps[prop.PropertyName] = prop.Value;
                        }
                    }
                }

                tr.Commit();
                return new
                {
                    handle = handleStr,
                    block_name = blockRef.Name,
                    attributes = attributesDict,
                    dynamic_properties = dynamicProps,
                    success = true
                };
            }
        }

        private static object QueryElements(Document doc, JObject p)
        {
            Database db = doc.Database;
            string? targetLayer = p["layer"]?.ToString();
            int maxLimit = p["limit"]?.Value<int>() ?? 500;

            var resultList = new List<object>();

            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                BlockTable bt = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                BlockTableRecord btr = (BlockTableRecord)tr.GetObject(bt[BlockTableRecord.ModelSpace], OpenMode.ForRead);

                foreach (ObjectId id in btr)
                {
                    if (resultList.Count >= maxLimit) break;
                    try
                    {
                        Entity ent = (Entity)tr.GetObject(id, OpenMode.ForRead);
                        if (targetLayer != null && !string.Equals(ent.Layer, targetLayer, StringComparison.OrdinalIgnoreCase))
                        {
                            continue;
                        }

                        resultList.Add(BuildEntitySummary(tr, ent));
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"[QueryElements] Error reading object {id}: {ex.Message}");
                    }
                }
                tr.Commit();
            }

            return new { count = resultList.Count, elements = resultList };
        }

        private static object GetEntityInfo(Document doc, JObject p)
        {
            string handleStr = p["handle"]?.ToString() ?? throw new ArgumentException("Entity handle required.");
            Database db = doc.Database;

            using (Transaction tr = db.TransactionManager.StartTransaction())
            {
                long ln = Convert.ToInt64(handleStr, 16);
                Handle h = new Handle(ln);
                ObjectId id = db.GetObjectId(false, h, 0);
                Entity ent = (Entity)tr.GetObject(id, OpenMode.ForRead);

                object summary = BuildEntitySummary(tr, ent);
                tr.Commit();
                return summary;
            }
        }

        private static object BuildEntitySummary(Transaction tr, Entity ent)
        {
            string typeName = ent.GetRXClass().Name;
            string handleStr = ent.Handle.ToString();
            string layerStr = ent.Layer;

            var attributesDict = new Dictionary<string, string>();
            var dynamicProps = new Dictionary<string, object>();
            string blockName = "";

            if (ent is BlockReference blockRef)
            {
                blockName = blockRef.Name;
                foreach (ObjectId attId in blockRef.AttributeCollection)
                {
                    DBObject attObj = tr.GetObject(attId, OpenMode.ForRead);
                    if (attObj is AttributeReference attRef)
                    {
                        attributesDict[attRef.Tag] = attRef.TextString;
                    }
                }

                if (blockRef.IsDynamicBlock)
                {
                    foreach (DynamicBlockReferenceProperty prop in blockRef.DynamicBlockReferencePropertyCollection)
                    {
                        if (prop.Value != null)
                        {
                            dynamicProps[prop.PropertyName] = prop.Value;
                        }
                    }
                }
            }

            double[]? boundsMin = null;
            double[]? boundsMax = null;
            try
            {
                if (ent.Bounds.HasValue)
                {
                    Point3d minP = ent.Bounds.Value.MinPoint;
                    Point3d maxP = ent.Bounds.Value.MaxPoint;
                    boundsMin = new double[] { minP.X, minP.Y, minP.Z };
                    boundsMax = new double[] { maxP.X, maxP.Y, maxP.Z };
                }
            }
            catch
            {
                // Ignore bounds calculation issues for custom proxy objects
            }

            return new
            {
                handle = handleStr,
                type = typeName,
                layer = layerStr,
                color = ent.ColorIndex,
                block_name = blockName,
                attributes = attributesDict,
                dynamic_properties = dynamicProps,
                bounds_min = boundsMin,
                bounds_max = boundsMax
            };
        }

        private static object SaveDocument(Document doc)
        {
            Database db = doc.Database;
            if (string.IsNullOrEmpty(doc.Name) || doc.Name.StartsWith("Drawing", StringComparison.OrdinalIgnoreCase))
            {
                return new { saved = false, reason = "Document has not been saved yet (default Drawing file)." };
            }
            db.SaveAs(doc.Name, DwgVersion.Current);
            return new { saved = true, path = doc.Name };
        }

        // ────────────────────────────────────────────────────────────────────────
        // Helpers
        // ────────────────────────────────────────────────────────────────────────

        private static Point3d GetPoint(JArray? arr)
        {
            if (arr != null && arr.Count >= 2)
            {
                double x = arr[0].Value<double>();
                double y = arr[1].Value<double>();
                double z = arr.Count >= 3 ? arr[2].Value<double>() : 0.0;
                return new Point3d(x, y, z);
            }
            return new Point3d(0, 0, 0);
        }

        private static void ApplyProperties(Database db, Transaction tr, Entity ent, JObject p)
        {
            if (p["layer"] != null)
            {
                string layerName = p["layer"].ToString();
                LayerTable lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
                if (lt.Has(layerName))
                {
                    ent.Layer = layerName;
                }
            }
            if (p["color"] != null)
            {
                int colorIndex = p["color"].Value<int>();
                if (colorIndex >= 0 && colorIndex <= 256)
                {
                    ent.ColorIndex = colorIndex;
                }
            }
        }

        private static object SpecklePush(Document doc, JObject p)
        {
            string streamId = p["stream_id"]?.ToString() ?? throw new ArgumentException("stream_id parameter is required.");
            string serverUrl = p["server_url"]?.ToString() ?? "https://speckle.xyz";
            string token = p["token"]?.ToString() ?? throw new ArgumentException("token parameter is required.");

            // Execute the async PushModel method synchronously inside AutoCAD lock context
            string commitId = System.Threading.Tasks.Task.Run(() => SpeckleConnector.PushModel(doc, streamId, serverUrl, token)).GetAwaiter().GetResult();
            return new { success = true, commit_id = commitId };
        }
    }
}
