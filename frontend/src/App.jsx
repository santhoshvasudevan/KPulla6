import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { AuthProvider } from './authContext';
import { ThemeProvider } from './themeContext';
import { setUnauthorizedHandler } from './api';
import Layout from './components/Layout';
import { ProtectedRoute, PublicOnlyRoute } from './components/auth/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Cash from './pages/Cash';
import Assets from './pages/Assets';
import Settings from './pages/Settings';
import AssetDetail from './pages/AssetDetail';
import Compare from './pages/Compare';
import Login from './pages/auth/Login';
import Register from './pages/auth/Register';
import ForgotPassword from './pages/auth/ForgotPassword';
import { PortfolioProvider } from './portfolioContext';

function UnauthorizedRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    setUnauthorizedHandler(() => navigate('/login', { replace: true }));
    return () => setUnauthorizedHandler(null);
  }, [navigate]);
  return null;
}

function AppRoutes() {
  return (
    <>
      <UnauthorizedRedirect />
      <Routes>
        <Route element={<PublicOnlyRoute />}>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
        </Route>

        <Route
          element={
            <PortfolioProvider>
              <ProtectedRoute />
            </PortfolioProvider>
          }
        >
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="dashboard" element={<Navigate to="/" replace />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="cash" element={<Cash />} />
            <Route path="assets" element={<Assets />} />
            <Route path="assets/:assetSymbol" element={<AssetDetail />} />
            <Route path="compare" element={<Compare />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
