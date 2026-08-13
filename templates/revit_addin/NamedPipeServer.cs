using System;
using System.IO.Pipes;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Concurrent;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Autodesk.Revit.UI;

namespace FireAI.RevitAddin
{
    /// <summary>
    /// NamedPipeServer.cs — Named pipe listener for Python MCP server commands.
    ///
    /// V214: This class implements the C# side of the Python↔C# named pipe bridge.
    /// The Python MCP server (fireai/mcp_server/revit_mcp_server.py) sends JSON
    /// commands over the named pipe "\\.\pipe\FireAIRevitPipe". This class
    /// listens for commands, deserializes them, and enqueues them in the
    /// ThreadSafeQueueHandler for execution on the Revit UI thread.
    ///
    /// PROTOCOL:
    ///   Each message is a JSON object terminated by a newline (\n):
    ///     {"action": "set_parameter", "element_id": "12345",
    ///      "parameter_name": "Diameter", "value": 25.0,
    ///      "nfpa_reference": "NFPA 72 §17.7.3.2.3"}
    ///
    ///   Response is a JSON object terminated by a newline:
    ///     {"status": "queued", "pending_count": 3}
    ///     OR
    ///     {"status": "error", "message": "Invalid action type"}
    ///
    /// THREAD SAFETY:
    ///   - The pipe server runs on a background thread (not the Revit UI thread)
    ///   - Commands are enqueued in ThreadSafeQueueHandler (thread-safe)
    ///   - Revit's ExternalEvent system raises the handler on the UI thread
    /// </summary>
    public class NamedPipeServer : IDisposable
    {
        private const string PipeName = "FireAIRevitPipe";
        private readonly ThreadSafeQueueHandler _handler;
        private readonly ExternalEvent _externalEvent;
        private CancellationTokenSource _cts;
        private Task _serverTask;
        private bool _disposed = false;

        // Statistics
        private int _totalReceived = 0;
        private int _totalQueued = 0;
        private int _totalErrors = 0;

        public NamedPipeServer(ThreadSafeQueueHandler handler, ExternalEvent externalEvent)
        {
            _handler = handler ?? throw new ArgumentNullException(nameof(handler));
            _externalEvent = externalEvent ?? throw new ArgumentNullException(nameof(externalEvent));
        }

        /// <summary>
        /// Start listening for commands on a background thread.
        /// </summary>
        public void Start()
        {
            if (_serverTask != null && !_serverTask.IsCompleted)
                return; // Already running

            _cts = new CancellationTokenSource();
            _serverTask = Task.Run(() => ListenLoop(_cts.Token), _cts.Token);
        }

        /// <summary>
        /// Stop listening and clean up.
        /// </summary>
        public void Stop()
        {
            _cts?.Cancel();
            // Wait for the server task to finish (with timeout)
            try
            {
                _serverTask?.Wait(TimeSpan.FromSeconds(5));
            }
            catch (AggregateException)
            {
                // Task cancelled — expected
            }
        }

        private void ListenLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                NamedPipeServerStream pipeServer = null;
                try
                {
                    pipeServer = new NamedPipeServerStream(
                        PipeName,
                        PipeDirection.InOut,
                        NamedPipeServerStream.MaxAllowedServerInstances,
                        PipeTransmissionMode.Byte,
                        PipeOptions.None
                    );

                    // Wait for a client to connect (blocks until connected or cancelled)
                    pipeServer.WaitForConnectionAsync(ct).GetAwaiter().GetResult();

                    if (ct.IsCancellationRequested)
                        break;

                    // Read the command (newline-delimited JSON)
                    var sb = new StringBuilder();
                    byte[] buffer = new byte[4096];
                    int bytesRead;

                    while ((bytesRead = pipeServer.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        string chunk = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                        sb.Append(chunk);
                        if (chunk.Contains('\n'))
                            break;
                    }

                    string rawMessage = sb.ToString().Trim();
                    if (string.IsNullOrEmpty(rawMessage))
                    {
                        SendResponse(pipeServer, new { status = "error", message = "Empty message" });
                        continue;
                    }

                    _totalReceived++;

                    // Parse and enqueue the command
                    string responseJson;
                    try
                    {
                        var command = JObject.Parse(rawMessage);
                        string action = command["action"]?.ToString() ?? "";

                        var actionDelegate = BuildAction(action, command);
                        if (actionDelegate == null)
                        {
                            _totalErrors++;
                            responseJson = JsonConvert.SerializeObject(new
                            {
                                status = "error",
                                message = $"Unknown action: '{action}'"
                            });
                        }
                        else
                        {
                            _handler.EnqueueAction(actionDelegate);
                            _totalQueued++;

                            // Signal Revit to process the queue
                            _externalEvent.Raise();

                            responseJson = JsonConvert.SerializeObject(new
                            {
                                status = "queued",
                                pending_count = _handler.PendingCount,
                                total_received = _totalReceived,
                                total_queued = _totalQueued
                            });
                        }
                    }
                    catch (JsonException jex)
                    {
                        _totalErrors++;
                        responseJson = JsonConvert.SerializeObject(new
                        {
                            status = "error",
                            message = $"JSON parse error: {jex.Message}"
                        });
                    }

                    SendResponse(pipeServer, responseJson);
                }
                catch (OperationCanceledException)
                {
                    break; // Shutdown requested
                }
                catch (Exception ex)
                {
                    _totalErrors++;
                    System.Diagnostics.Debug.WriteLine(
                        $"[FireAI NamedPipeServer] Error: {ex.Message}");
                }
                finally
                {
                    pipeServer?.Dispose();
                }
            }
        }

        private void SendResponse(NamedPipeServerStream pipe, string json)
        {
            try
            {
                byte[] responseBytes = Encoding.UTF8.GetBytes(json + "\n");
                pipe.Write(responseBytes, 0, responseBytes.Length);
                pipe.Flush();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[FireAI NamedPipeServer] Failed to send response: {ex.Message}");
            }
        }

        /// <summary>
        /// Build an Action&lt;UIApplication&gt; from a parsed JSON command.
        /// Supported actions:
        ///   - set_parameter: Set a numeric parameter on an element
        ///   - set_string_parameter: Set a string parameter on an element
        ///   - create_wall: Create a wall (delegates to Revit API Wall.Create)
        /// </summary>
        private Action<UIApplication> BuildAction(string actionType, JObject command)
        {
            switch (actionType.ToLowerInvariant())
            {
                case "set_parameter":
                    return ModelUpdateActions.SetParameter(
                        command["element_id"]?.ToString() ?? "",
                        command["parameter_name"]?.ToString() ?? "",
                        command["value"]?.Value<double>() ?? 0.0,
                        command["nfpa_reference"]?.ToString() ?? ""
                    );

                case "set_string_parameter":
                    return ModelUpdateActions.SetStringParameter(
                        command["element_id"]?.ToString() ?? "",
                        command["parameter_name"]?.ToString() ?? "",
                        command["value"]?.ToString() ?? "",
                        command["nfpa_reference"]?.ToString() ?? ""
                    );

                case "create_wall":
                    return (app) =>
                    {
                        var doc = app.ActiveUIDocument.Document;
                        var startArr = command["start_point"] as JArray;
                        var endArr = command["end_point"] as JArray;
                        if (startArr == null || endArr == null)
                            throw new ArgumentException("create_wall requires start_point and end_point arrays");

                        double sx = startArr[0].Value<double>();
                        double sy = startArr[1].Value<double>();
                        double sz = startArr.Count > 2 ? startArr[2].Value<double>() : 0;
                        double ex = endArr[0].Value<double>();
                        double ey = endArr[1].Value<double>();
                        double ez = endArr.Count > 2 ? endArr[2].Value<double>() : 0;

                        // Convert mm to feet (Revit internal units)
                        const double MM_TO_FEET = 1.0 / 304.8;
                        var start = new Autodesk.Revit.DB.XYZ(sx * MM_TO_FEET, sy * MM_TO_FEET, sz * MM_TO_FEET);
                        var end = new Autodesk.Revit.DB.XYZ(ex * MM_TO_FEET, ey * MM_TO_FEET, ez * MM_TO_FEET);
                        var line = Autodesk.Revit.DB.Line.CreateBound(start, end);

                        // Find level by name
                        string levelName = command["level"]?.ToString() ?? "Level 1";
                        var levelCollector = new Autodesk.Revit.DB.FilteredElementCollector(doc)
                            .OfClass(typeof(Autodesk.Revit.DB.Level));
                        var targetLevel = levelCollector.FirstOrDefault<Autodesk.Revit.DB.Level>(
                            l => l.Name == levelName);

                        if (targetLevel == null)
                            throw new InvalidOperationException($"Level '{levelName}' not found");

                        Autodesk.Revit.DB.Wall.Create(doc, line, targetLevel.Id, false);
                    };

                default:
                    return null;
            }
        }

        /// <summary>
        /// Get processing statistics.
        /// </summary>
        public (int Received, int Queued, int Errors) GetStats()
            => (_totalReceived, _totalQueued, _totalErrors);

        public void Dispose()
        {
            if (!_disposed)
            {
                Stop();
                _cts?.Dispose();
                _disposed = true;
            }
        }
    }
}
