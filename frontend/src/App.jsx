import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import Assets from './pages/Assets';
import Settings from './pages/Settings';
import AssetDetail from './pages/AssetDetail';
import { PortfolioProvider } from './portfolioContext';

function App() {
  return (
    <PortfolioProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="assets" element={<Assets />} />
            <Route path="assets/:assetSymbol" element={<AssetDetail />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PortfolioProvider>
  );
}

export default App;
