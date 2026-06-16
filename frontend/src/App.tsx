import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Toaster } from 'sonner';
import { DashboardPage } from './pages/DashboardPage';
import { ProjectsPage } from './pages/ProjectsPage';
import { EngineeringPage } from './pages/EngineeringPage';
import { ReportsPage } from './pages/ReportsPage';
import { SettingsPage } from './pages/SettingsPage';
import { FireAlarmPage } from './pages/FireAlarmPage';
import { FireAlarmDesigner } from './components/mockups/engineering/FireAlarmDesigner';
import { DigitalTwinPage } from './pages/DigitalTwinPage';
import { CADSettingsPage } from './pages/CADSettingsPage';
import './i18n';
import './styles/globals.css';
import './styles/typography.css';

function App() {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    // Set document direction based on language for RTL support
    if (i18n.language === 'ar') {
      document.documentElement.dir = 'rtl';
      document.documentElement.lang = 'ar';
    } else {
      document.documentElement.dir = 'ltr';
      document.documentElement.lang = 'en';
    }
  }, [i18n.language]);

  // Define routes
  const routes = [
    { path: '/', element: <Navigate to="/dashboard" /> },
    { path: '/dashboard', element: <DashboardPage /> },
    { path: '/projects', element: <ProjectsPage /> },
    { path: '/engineering', element: <EngineeringPage /> },
    { path: '/reports', element: <ReportsPage /> },
    { path: '/settings', element: <SettingsPage /> },
    { path: '/settings/cad', element: <CADSettingsPage /> },
    { path: '/digital-twin', element: <DigitalTwinPage /> },
    // Fire Alarm Specific Routes
    { path: '/fire-alarm', element: <FireAlarmPage /> },
    { path: '/fire-alarm/designer', element: <FireAlarmDesigner /> },
  ];

  return (
    <Router>
      <div className="flex h-screen bg-slate-900 text-slate-100">
        <div className="flex-1 flex flex-col overflow-hidden">
          <header className="h-14 flex items-center px-4 border-b border-slate-700 bg-slate-800">
            <h1 className="text-lg font-semibold text-slate-100">FireAI Revit</h1>
            <div className="ml-auto flex gap-2">
              <select
                value={i18n.language}
                onChange={(e) => i18n.changeLanguage(e.target.value)}
                className="bg-slate-900 border border-slate-600 rounded px-2 py-1 text-sm text-slate-100"
              >
                <option value="en">English</option>
                <option value="ar">العربية</option>
              </select>
            </div>
          </header>
          <main className="flex-1 overflow-auto bg-slate-900">
            <Routes>
              {routes.map((route) => (
                <Route key={route.path} path={route.path} element={route.element} />
              ))}
            </Routes>
          </main>
        </div>
      </div>
      <Toaster position="bottom-right" />
    </Router>
  );
}

export default App;
