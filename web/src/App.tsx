import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AppLayout from './layout/AppLayout';

const queryClient = new QueryClient();

import Overview from './pages/Overview';
import HbtVisualizer from './pages/HbtVisualizer';
import Alerts from './pages/Alerts';
import Logs from './pages/Logs';
import Incidents from './pages/Incidents';
import Settings from './pages/Settings';

const baseName = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={baseName}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Overview />} />
            <Route path="hbt" element={<HbtVisualizer />} />
            <Route path="logs" element={<Logs />} />
            <Route path="alerts" element={<Alerts />} />
            <Route path="incidents" element={<Incidents />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
