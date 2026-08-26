// BazSparkRevitBridge/ScreenCapture.cs
// T2 visual awareness: captures the Revit main window into a base64 PNG
// using Win32 PrintWindow (no focus stealing — safe while user works).
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

namespace BazSparkRevitBridge
{
    internal static class ScreenCapture
    {
        private const uint PW_CLIENTONLY = 0x1;
        private const uint PW_RENDERFULLCONTENT = 0x2;

        [StructLayout(LayoutKind.Sequential)]
        private struct RECT
        {
            public int Left, Top, Right, Bottom;
        }

        [DllImport("user32.dll")]
        private static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);

        [DllImport("user32.dll")]
        private static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);

        /// <summary>Returns a base64-encoded PNG snapshot of the given window.</summary>
        public static string CaptureBase64(IntPtr hwnd)
        {
            if (hwnd == IntPtr.Zero)
                throw new InvalidOperationException("Application window handle is unavailable.");

            if (!GetWindowRect(hwnd, out RECT rect))
                throw new InvalidOperationException("Failed to query application window rectangle.");

            int width = rect.Right - rect.Left;
            int height = rect.Bottom - rect.Top;
            if (width <= 0 || height <= 0)
                throw new InvalidOperationException("Application window has invalid size.");

            using (var bmp = new Bitmap(width, height, PixelFormat.Format32bppArgb))
            {
                using (var g = Graphics.FromImage(bmp))
                {
                    IntPtr hdc = g.GetHdc();
                    try
                    {
                        // PW_CLIENTONLY | PW_RENDERFULLCONTENT: client area with
                        // full content rendering (handles hardware-accelerated views).
                        PrintWindow(hwnd, hdc, PW_CLIENTONLY | PW_RENDERFULLCONTENT);
                    }
                    finally
                    {
                        g.ReleaseHdc(hdc);
                    }
                }

                using (var ms = new MemoryStream())
                {
                    bmp.Save(ms, ImageFormat.Png);
                    return Convert.ToBase64String(ms.ToArray());
                }
            }
        }
    }
}
