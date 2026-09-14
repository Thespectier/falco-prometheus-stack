import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AppLayout from './layout/AppLayout';

import Overview from './pages/Overview';
import HbtVisualizer from './pages/HbtVisualizer';
import Alerts from './pages/Alerts';
import Logs from './pages/Logs';
import Incidents from './pages/Incidents';
import Settings from './pages/Settings';

const queryClient = new QueryClient();

/**
 * 页面路由表。
 *
 * `path` 与侧栏导航项（`layout/AppLayout.tsx` 的 NAV_ITEMS）必须一一对应；
 * 空字符串表示 AppLayout 下的默认页。改这里要同步改导航，否则点进去会落到兜底路由。
 */
const PAGES = [
  { path: '', element: <Overview /> },
  { path: 'hbt', element: <HbtVisualizer /> },
  { path: 'logs', element: <Logs /> },
  { path: 'alerts', element: <Alerts /> },
  { path: 'incidents', element: <Incidents /> },
  { path: 'settings', element: <Settings /> },
];

const baseName = (import.meta.env.BASE_URL || '/').replace(/\/$/, '');

const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={baseName}>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            {PAGES.map((page) => (
              <Route key={page.path} path={page.path} element={page.element} />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
