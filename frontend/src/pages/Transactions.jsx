import { useCallback, useEffect, useState, useRef } from 'react';
import { fetchTransactions, deleteTransaction, importTransactionsCsv } from '../api';
import TransactionModal from '../components/TransactionModal';
import {
  PageHeader,
  Button,
  LoadingState,
  ErrorState,
  EmptyState,
  WarningBanner,
  CurrencyValue,
} from '../components/ui';
import { Plus, Edit2, Trash2 } from 'lucide-react';
import './Transactions.css';
import { usePortfolio } from '../portfolioContext';

function importBannerSeverity(status) {
  if (status.startsWith('Imported')) return 'success';
  if (status.includes('failed') || status.includes('Please choose')) return 'warning';
  return 'info';
}

function displayLineTotal(txn) {
  if (txn.type === 'STOCK_SPLIT') return null;
  return Number(txn.quantity) * Number(txn.price_per_share) + Number(txn.fees || 0);
}

export default function Transactions() {
  const { apiQuery, selectedPortfolioName, selectedPortfolioMode } = usePortfolio();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTransaction, setEditingTransaction] = useState(null);
  const [importStatus, setImportStatus] = useState('');
  const [importErrors, setImportErrors] = useState([]);
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef(null);

  const loadData = useCallback(() => {
    setLoading(true);
    setError('');
    fetchTransactions(1, 50, apiQuery)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiQuery]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAdd = () => {
    setEditingTransaction(null);
    setIsModalOpen(true);
  };

  const handleEdit = (txn) => {
    setEditingTransaction(txn);
    setIsModalOpen(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this transaction?')) return;
    try {
      await deleteTransaction(id);
      loadData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleModalSuccess = () => {
    loadData();
  };

  const handleImportClick = () => {
    setImportStatus('');
    setImportErrors([]);
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setImportStatus('Please choose a .csv file');
      return;
    }
    setImporting(true);
    setImportStatus('');
    setImportErrors([]);
    try {
      const portfolioId = apiQuery?.portfolio_id ?? null;
      const result = await importTransactionsCsv(file, portfolioId);
      if (result.success) {
        setImportStatus(`Imported ${result.imported_count} transactions`);
        loadData();
      } else {
        setImportErrors(result.errors || []);
        setImportStatus('Import failed — fix errors and try again');
      }
    } catch (err) {
      setImportStatus(err.message || 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  if (loading && !data) return <LoadingState message="Loading transactions…" />;
  if (error && !data) {
    return (
      <ErrorState
        title="Unable to load transactions"
        message={error}
        onRetry={loadData}
      />
    );
  }

  const items = data?.items ?? [];
  const importTarget =
    selectedPortfolioMode === 'portfolio' ? selectedPortfolioName : 'Default Portfolio';

  return (
    <div className="transactions-page">
      <PageHeader
        title="Transactions"
        subtitle={`${data?.total ?? 0} records · Source-of-truth activity ledger`}
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="transactions-page__file-input"
              onChange={handleFileChange}
            />
            <Button variant="secondary" onClick={handleImportClick} disabled={importing}>
              {importing ? 'Importing…' : 'Import from CSV'}
            </Button>
            <Button variant="primary" onClick={handleAdd} className="transactions-page__add-btn">
              <Plus size={16} aria-hidden="true" />
              Add Transaction
            </Button>
          </>
        }
      />

      <WarningBanner
        severity="info"
        message={
          <>
            Imported transactions will be added to: <strong>{importTarget}</strong>. CSV:
            Action=STOCK_SPLIT uses Qty=split_from and Price/Share=split_to; SWAP rows import as
            splits.
          </>
        }
        className="transactions-page__banner"
      />

      {importStatus && importErrors.length === 0 ? (
        <WarningBanner
          severity={importBannerSeverity(importStatus)}
          message={importStatus}
          className="transactions-page__banner"
        />
      ) : null}

      {importErrors.length > 0 ? (
        <div className="transactions-import-block transactions-page__banner">
          <WarningBanner
            severity="error"
            title={importStatus || 'Import failed — fix errors and try again'}
          />
          <ul className="transactions-import-errors">
            {importErrors.map((er, i) => (
              <li key={i}>
                Row {er.row}
                {er.field ? ` — ${er.field}` : ''}: {er.message}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {items.length === 0 ? (
        <EmptyState
          title="No transactions found."
          description="Add a transaction manually or import from CSV."
        />
      ) : (
        <div className="transactions-table-wrapper">
          <table className="transactions-table">
            <thead>
              <tr>
                <th>Portfolio</th>
                <th>Symbol</th>
                <th>Date</th>
                <th>Type</th>
                <th className="num-col">Quantity</th>
                <th className="num-col">Price / Share</th>
                <th className="num-col">Fees</th>
                <th className="num-col">Total</th>
                <th className="actions-col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((txn) => {
                const isSplit = txn.type === 'STOCK_SPLIT';
                const total = displayLineTotal(txn);
                const currency = txn.currency || 'EUR';

                return (
                  <tr key={txn.id} className="transactions-table__row">
                    <td>{txn.portfolio_name || (txn.portfolio_id != null ? `#${txn.portfolio_id}` : '')}</td>
                    <td className="transactions-table__symbol">{txn.asset_symbol}</td>
                    <td>{txn.date}</td>
                    <td>
                      <span
                        className={`ui-txn-type ui-txn-type--${String(txn.type || '').toLowerCase().replace(/_/g, '-')}`}
                      >
                        {txn.type}
                      </span>
                    </td>
                    <td className="num-col">
                      {isSplit ? `${txn.split_from}:${txn.split_to}` : txn.quantity}
                    </td>
                    <td className="num-col">
                      {isSplit ? (
                        '—'
                      ) : (
                        <CurrencyValue value={txn.price_per_share} currency={currency} />
                      )}
                    </td>
                    <td className="num-col">
                      {isSplit ? (
                        '—'
                      ) : (
                        <CurrencyValue value={txn.fees} currency={currency} />
                      )}
                    </td>
                    <td className="num-col">
                      {isSplit || total == null ? (
                        '—'
                      ) : (
                        <CurrencyValue value={total} currency={currency} />
                      )}
                    </td>
                    <td className="actions-col">
                      <div className="transactions-table__actions">
                        <Button
                          variant="ghost"
                          onClick={() => handleEdit(txn)}
                          title="Edit"
                          className="transactions-table__icon-btn"
                        >
                          <Edit2 size={16} aria-hidden="true" />
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={() => handleDelete(txn.id)}
                          title="Delete"
                          className="transactions-table__icon-btn transactions-table__icon-btn--danger"
                        >
                          <Trash2 size={16} aria-hidden="true" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <TransactionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleModalSuccess}
        initialData={editingTransaction}
      />
    </div>
  );
}
