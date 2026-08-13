using System;
using Autodesk.Revit.UI;

namespace FireAI.RevitAddin
{
    /// <summary>
    /// FireAIApplication.cs — Revit IExternalApplication entry point.
    ///
    /// V214: This class is loaded by Revit when the add-in starts.
    /// It creates the ThreadSafeQueueHandler + ExternalEvent + NamedPipeServer
    /// and keeps them alive for the duration of the Revit session.
    ///
    /// Registration: The FireAIRevitAddin.addin file tells Revit to load
    /// this class on startup. The .csproj build target copies the .dll
    /// and .addin file to %APPDATA%\Autodesk\Revit\Addins\2024\.
    /// </summary>
    public class FireAIApplication : IExternalApplication
    {
        private ThreadSafeQueueHandler _queueHandler;
        private ExternalEvent _externalEvent;
        private NamedPipeServer _pipeServer;

        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                // Create the thread-safe queue handler
                _queueHandler = new ThreadSafeQueueHandler();

                // Create the ExternalEvent that signals Revit to process the queue
                _externalEvent = ExternalEvent.Create(_queueHandler);

                // Start the named pipe server (listens for Python MCP commands)
                _pipeServer = new NamedPipeServer(_queueHandler, _externalEvent);
                _pipeServer.Start();

                // Add a ribbon panel with a status button
                var panel = application.CreateRibbonPanel("FireAI");
                var statusButton = panel.AddItem(new PushButtonData(
                    "FireAIStatus",
                    "FireAI Status",
                    typeof(FireAIApplication).Assembly.Location,
                    "FireAI.RevitAddin.FireAIStatusCommand"
                )) as PushButton;
                if (statusButton != null)
                {
                    statusButton.ToolTip = "Show FireAI add-in connection status";
                    statusButton.LargeImage = null; // TODO: Add icon
                }

                System.Diagnostics.Debug.WriteLine(
                    "[FireAI] Add-in started successfully. Named pipe: \\\\.\\pipe\\FireAIRevitPipe");

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[FireAI] FATAL: Add-in startup failed: {ex.Message}");
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            try
            {
                _pipeServer?.Stop();
                _pipeServer?.Dispose();
                _externalEvent?.Dispose();

                System.Diagnostics.Debug.WriteLine("[FireAI] Add-in shutdown complete.");
                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(
                    $"[FireAI] Shutdown error: {ex.Message}");
                return Result.Failed;
            }
        }
    }
}
