import { Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import {
  createFixedDeposit,
  createFixedDepositInterestPayment,
  deleteFixedDeposit,
  fetchBankAccounts,
  fetchFixedDepositInterestPayments,
  fetchFixedDeposits,
  fetchPortfolios,
  markFixedDepositMatured,
  renewFixedDeposit,
  settleFixedDeposit,
  updateFixedDeposit,
} from '../api';
import { usePortfolio } from '../portfolioContext';
import {
  PageHeader,
  DataTableShell,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
  KpiCard,
  Button,
  LoadingState,
  ErrorState,
  WarningBanner,
  CurrencyValue,
  StatusBadge,
} from '../components/ui';
import { fdPayoutLabel, fdStatusBadgeProps, fdStatusCounts } from '../utils/fdDisplay';
import './FixedDeposits.css';

const FD_SECTION_NAV = [
  { href: '#fd-overview', label: 'Overview' },
  { href: '#fd-deposits', label: 'Deposits' },
];

const PAYOUT_FREQUENCIES = [
  { value: 'MONTHLY', label: 'Monthly' },
  { value: 'QUARTERLY', label: 'Quarterly' },
  { value: 'HALF_YEARLY', label: 'Half yearly' },
  { value: 'ANNUALLY', label: 'Annually' },
  { value: 'COMPOUNDED', label: 'Compounded' },
];

const STATUSES = [
  { value: 'ACTIVE', label: 'Active' },
  { value: 'MATURED', label: 'Matured' },
  { value: 'CLOSED', label: 'Closed' },
];

function emptyForm() {
  return {
    portfolio_id: '',
    bank_account_id: '',
    institution_name: '',
    deposit_account_number: '',
    principal_amount: '',
    currency: 'INR',
    interest_rate_percent: '',
    interest_payout_frequency: 'QUARTERLY',
    investment_date: '',
    maturity_date: '',
    nominee_name: '',
    comment: '',
    status: 'ACTIVE',
  };
}

function bankHasLedger(bank) {
  return Boolean(bank?.has_ledger_entries || bank?.balance_source === 'ledger');
}

function ledgerBalanceForFd(bank) {
  if (!bank) return 0;
  return bankHasLedger(bank) ? Number(bank.current_balance) : 0;
}

function needsOpeningBalanceSeed(bank) {
  return (
    bank &&
    Number(bank.opening_balance) > 0 &&
    !bank.opening_balance_seeded &&
    !bankHasLedger(bank)
  );
}

function hasMisleadingManualBalance(bank) {
  return bank && !bankHasLedger(bank) && Number(bank.current_balance) > 0;
}

const FD_BALANCE_AS_OF_NOTE =
  'Available bank balance is checked as of the FD investment date.';

const FD_BACKDATED_LEDGER_NOTE =
  'If this FD is backdated, make sure the opening balance or cash deposit is recorded on or before the FD investment date.';

const FD_BACKDATED_HINT =
  'For backdated FDs, record or seed bank cash on or before the investment date.';

function formatFdInsufficientError(message) {
  if (!message || !/insufficient/i.test(message)) return message;
  let formatted = message.replace(/\bavailable:/i, 'Available as of investment date:');
  if (!/backdated fd/i.test(formatted)) {
    formatted = `${formatted} ${FD_BACKDATED_HINT}`;
  }
  return formatted;
}

function emptyInterestForm() {
  return {
    payment_date: new Date().toISOString().slice(0, 10),
    gross_interest: '',
    tax_withheld: '0',
    comment: '',
  };
}

function computeDisplayNetInterest(gross, tax) {
  const grossNum = parseFloat(gross);
  const taxNum = parseFloat(tax);
  if (!Number.isFinite(grossNum) || !Number.isFinite(taxNum)) return null;
  return grossNum - taxNum;
}

function isSettledFd(fd) {
  return fd?.status === 'CLOSED' || fd?.status === 'MATURED_SETTLED';
}

function canMarkMatured(fd) {
  return fd?.status === 'ACTIVE';
}

function canSettle(fd) {
  return fd?.status === 'ACTIVE' || fd?.status === 'MATURED';
}

function canRenew(fd) {
  return (
    (fd?.status === 'ACTIVE' || fd?.status === 'MATURED') &&
    !fd?.has_renewal
  );
}

function emptyRenewalForm(fd) {
  const today = new Date().toISOString().slice(0, 10);
  return {
    renewal_date: today,
    new_deposit_account_number: '',
    new_principal_amount: fd ? String(fd.principal_amount ?? '') : '',
    new_interest_rate_percent: fd ? String(fd.interest_rate_percent ?? '') : '',
    new_interest_payout_frequency: fd?.interest_payout_frequency || 'QUARTERLY',
    new_investment_date: today,
    new_maturity_date: '',
    gross_interest: '0',
    tax_withheld: '0',
    cash_payout_amount: '0',
    nominee_name: fd?.nominee_name || '',
    comment: '',
  };
}

function emptySettlementForm(fd) {
  return {
    settlement_type: fd?.status === 'MATURED' ? 'MATURITY' : 'MATURITY',
    settlement_date: new Date().toISOString().slice(0, 10),
    principal_returned: fd ? String(fd.principal_amount ?? '') : '',
    gross_interest: '0',
    tax_withheld: '0',
    comment: '',
  };
}

export default function FixedDeposits() {
  const { apiQuery, settingsLoaded } = usePortfolio();
  const [items, setItems] = useState([]);
  const [portfolios, setPortfolios] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [interestFd, setInterestFd] = useState(null);
  const [interestForm, setInterestForm] = useState(emptyInterestForm);
  const [interestModalOpen, setInterestModalOpen] = useState(false);
  const [interestSubmitting, setInterestSubmitting] = useState(false);
  const [interestFormError, setInterestFormError] = useState('');
  const [expandedFdId, setExpandedFdId] = useState(null);
  const [interestPaymentsByFd, setInterestPaymentsByFd] = useState({});
  const [interestLoadingFdId, setInterestLoadingFdId] = useState(null);
  const [settlementFd, setSettlementFd] = useState(null);
  const [settlementForm, setSettlementForm] = useState(emptySettlementForm());
  const [settlementModalOpen, setSettlementModalOpen] = useState(false);
  const [settlementSubmitting, setSettlementSubmitting] = useState(false);
  const [settlementFormError, setSettlementFormError] = useState('');
  const [renewalFd, setRenewalFd] = useState(null);
  const [renewalForm, setRenewalForm] = useState(emptyRenewalForm());
  const [renewalModalOpen, setRenewalModalOpen] = useState(false);
  const [renewalSubmitting, setRenewalSubmitting] = useState(false);
  const [renewalFormError, setRenewalFormError] = useState('');
  const [markingMaturedId, setMarkingMaturedId] = useState(null);

  const statusCounts = useMemo(() => fdStatusCounts(items), [items]);

  const loadData = useCallback(async () => {
    if (!settingsLoaded || !apiQuery) return;
    setLoading(true);
    setError('');
    try {
      const [fdData, portfolioData, bankData] = await Promise.all([
        fetchFixedDeposits(apiQuery),
        fetchPortfolios(),
        fetchBankAccounts(),
      ]);
      setItems(Array.isArray(fdData) ? fdData : []);
      setPortfolios((portfolioData || []).filter((p) => p.is_active));
      setBankAccounts(Array.isArray(bankData) ? bankData : []);
    } catch (err) {
      setError(err.message || 'Failed to load fixed deposits.');
    } finally {
      setLoading(false);
    }
  }, [apiQuery, settingsLoaded]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openCreate = () => {
    setEditing(null);
    const defaultPortfolio = portfolios[0];
    const defaultBank = bankAccounts[0];
    setForm({
      ...emptyForm(),
      portfolio_id: defaultPortfolio ? String(defaultPortfolio.id) : '',
      bank_account_id: defaultBank ? String(defaultBank.id) : '',
      currency: defaultBank?.currency || 'INR',
    });
    setFormError('');
    setModalOpen(true);
  };

  const openEdit = (fd) => {
    setEditing(fd);
    setForm({
      portfolio_id: String(fd.portfolio_id),
      bank_account_id: String(fd.bank_account_id),
      institution_name: fd.institution_name || '',
      deposit_account_number: fd.deposit_account_number || '',
      principal_amount: String(fd.principal_amount ?? ''),
      currency: fd.currency || 'INR',
      interest_rate_percent: String(fd.interest_rate_percent ?? ''),
      interest_payout_frequency: fd.interest_payout_frequency || 'QUARTERLY',
      investment_date: fd.investment_date || '',
      maturity_date: fd.maturity_date || '',
      nominee_name: fd.nominee_name || '',
      comment: fd.comment || '',
      status: fd.status || 'ACTIVE',
    });
    setFormError('');
    setModalOpen(true);
  };

  const onBankChange = (bankId) => {
    const bank = bankAccounts.find((b) => String(b.id) === String(bankId));
    setForm((prev) => ({
      ...prev,
      bank_account_id: bankId,
      currency: bank?.currency || prev.currency,
    }));
  };

  const selectedBank = bankAccounts.find(
    (b) => String(b.id) === String(form.bank_account_id)
  );

  const openingFieldsLocked = Boolean(editing?.has_opening_cash_movement);
  const ledgerBalance = ledgerBalanceForFd(selectedBank);
  const principalAmount = parseFloat(form.principal_amount);
  const createBlockedByLedger =
    !editing &&
    selectedBank &&
    Number.isFinite(principalAmount) &&
    principalAmount > 0 &&
    ledgerBalance < principalAmount;
  const createBlockMessage = createBlockedByLedger
    ? needsOpeningBalanceSeed(selectedBank)
      ? 'Opening balance is not yet seeded into the cash ledger. Seed opening balance in Settings → Bank Accounts before creating a fixed deposit.'
      : `Insufficient ledger balance. Available (current ledger total): ${ledgerBalance} ${selectedBank.currency}; required: ${form.principal_amount} ${selectedBank.currency}. ${FD_BALANCE_AS_OF_NOTE} ${FD_BACKDATED_HINT}`
    : '';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    if (createBlockedByLedger) {
      setFormError(createBlockMessage);
      return;
    }
    setSubmitting(true);
    const payload = {
      portfolio_id: Number(form.portfolio_id),
      bank_account_id: Number(form.bank_account_id),
      institution_name: form.institution_name.trim(),
      deposit_account_number: form.deposit_account_number.trim(),
      principal_amount: form.principal_amount,
      currency: form.currency,
      interest_rate_percent: form.interest_rate_percent,
      interest_payout_frequency: form.interest_payout_frequency,
      investment_date: form.investment_date,
      maturity_date: form.maturity_date,
      nominee_name: form.nominee_name.trim(),
      comment: form.comment.trim(),
      status: form.status,
    };
    try {
      if (editing) {
        await updateFixedDeposit(editing.id, payload);
        setStatus('Fixed deposit updated.');
      } else {
        await createFixedDeposit(payload);
        setStatus('Fixed deposit created.');
      }
      setModalOpen(false);
      await loadData();
    } catch (err) {
      setFormError(formatFdInsufficientError(err.message || 'Save failed.'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeactivate = async (fd) => {
    if (!window.confirm(`Deactivate fixed deposit ${fd.deposit_account_number}?`)) return;
    try {
      await deleteFixedDeposit(fd.id);
      setStatus('Fixed deposit deactivated.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to deactivate fixed deposit.');
    }
  };

  const openInterestModal = (fd) => {
    setInterestFd(fd);
    setInterestForm(emptyInterestForm());
    setInterestFormError('');
    setInterestModalOpen(true);
  };

  const closeInterestModal = () => {
    setInterestModalOpen(false);
    setInterestFd(null);
    setInterestFormError('');
  };

  const loadInterestPayments = async (fdId) => {
    setInterestLoadingFdId(fdId);
    try {
      const data = await fetchFixedDepositInterestPayments(fdId);
      setInterestPaymentsByFd((prev) => ({
        ...prev,
        [fdId]: Array.isArray(data) ? data : [],
      }));
    } catch (err) {
      setError(err.message || 'Failed to load interest payments.');
    } finally {
      setInterestLoadingFdId(null);
    }
  };

  const toggleInterestPayments = async (fd) => {
    if (expandedFdId === fd.id) {
      setExpandedFdId(null);
      return;
    }
    setExpandedFdId(fd.id);
    if (!interestPaymentsByFd[fd.id]) {
      await loadInterestPayments(fd.id);
    }
  };

  const handleInterestSubmit = async (e) => {
    e.preventDefault();
    setInterestFormError('');

    const gross = parseFloat(interestForm.gross_interest);
    const tax = parseFloat(interestForm.tax_withheld || '0');
    if (!Number.isFinite(gross) || gross <= 0) {
      setInterestFormError('Gross interest must be greater than zero.');
      return;
    }
    if (!Number.isFinite(tax) || tax < 0) {
      setInterestFormError('Tax withheld must be zero or positive.');
      return;
    }
    if (tax > gross) {
      setInterestFormError('Tax withheld cannot exceed gross interest.');
      return;
    }
    if (!interestForm.payment_date) {
      setInterestFormError('Payment date is required.');
      return;
    }

    const payload = {
      payment_date: interestForm.payment_date,
      gross_interest: interestForm.gross_interest,
      tax_withheld: interestForm.tax_withheld || '0',
    };
    if (interestForm.comment.trim()) {
      payload.comment = interestForm.comment.trim();
    }

    setInterestSubmitting(true);
    try {
      const result = await createFixedDepositInterestPayment(interestFd.id, payload);
      closeInterestModal();
      setStatus(
        result.warning
          ? `Interest payment recorded. ${result.warning}`
          : 'Interest payment recorded.'
      );
      if (expandedFdId === interestFd.id) {
        await loadInterestPayments(interestFd.id);
      } else {
        setInterestPaymentsByFd((prev) => {
          const next = { ...prev };
          delete next[interestFd.id];
          return next;
        });
      }
      await loadData();
    } catch (err) {
      setInterestFormError(err.message || 'Failed to record interest payment.');
    } finally {
      setInterestSubmitting(false);
    }
  };

  const displayNetInterest = computeDisplayNetInterest(
    interestForm.gross_interest,
    interestForm.tax_withheld
  );

  const openSettlementModal = (fd) => {
    setSettlementFd(fd);
    setSettlementForm(emptySettlementForm(fd));
    setSettlementFormError('');
    setSettlementModalOpen(true);
  };

  const closeSettlementModal = () => {
    setSettlementModalOpen(false);
    setSettlementFd(null);
    setSettlementFormError('');
  };

  const handleMarkMatured = async (fd) => {
    setMarkingMaturedId(fd.id);
    setError('');
    try {
      await markFixedDepositMatured(fd.id);
      setStatus('Fixed deposit marked as matured.');
      await loadData();
    } catch (err) {
      setError(err.message || 'Failed to mark fixed deposit as matured.');
    } finally {
      setMarkingMaturedId(null);
    }
  };

  const handleSettlementSubmit = async (e) => {
    e.preventDefault();
    setSettlementFormError('');

    const principal = parseFloat(settlementForm.principal_returned);
    const gross = parseFloat(settlementForm.gross_interest || '0');
    const tax = parseFloat(settlementForm.tax_withheld || '0');
    if (!Number.isFinite(principal) || principal < 0) {
      setSettlementFormError('Principal returned must be zero or positive.');
      return;
    }
    if (!Number.isFinite(gross) || gross < 0) {
      setSettlementFormError('Gross final interest must be zero or positive.');
      return;
    }
    if (!Number.isFinite(tax) || tax < 0) {
      setSettlementFormError('Tax withheld must be zero or positive.');
      return;
    }
    if (tax > gross) {
      setSettlementFormError('Tax withheld cannot exceed gross final interest.');
      return;
    }
    const net = gross - tax;
    if (principal + net <= 0) {
      setSettlementFormError(
        'At least one of principal returned or net interest must be greater than zero.'
      );
      return;
    }
    if (!settlementForm.settlement_date) {
      setSettlementFormError('Settlement date is required.');
      return;
    }

    const payload = {
      settlement_type: settlementForm.settlement_type,
      settlement_date: settlementForm.settlement_date,
      principal_returned: settlementForm.principal_returned,
      gross_interest: settlementForm.gross_interest || '0',
      tax_withheld: settlementForm.tax_withheld || '0',
    };
    if (settlementForm.comment.trim()) {
      payload.comment = settlementForm.comment.trim();
    }

    setSettlementSubmitting(true);
    try {
      const result = await settleFixedDeposit(settlementFd.id, payload);
      closeSettlementModal();
      setStatus(
        `Settlement recorded. FD status is now ${result.fixed_deposit_status}. Portfolio value drops by principal; proceeds are in bank cash only.`
      );
      await loadData();
    } catch (err) {
      setSettlementFormError(err.message || 'Failed to record settlement.');
    } finally {
      setSettlementSubmitting(false);
    }
  };

  const displaySettlementNet = computeDisplayNetInterest(
    settlementForm.gross_interest,
    settlementForm.tax_withheld
  );
  const displayTotalProceeds =
    displaySettlementNet == null
      ? null
      : (parseFloat(settlementForm.principal_returned || '0') || 0) + displaySettlementNet;

  const openRenewalModal = (fd) => {
    setRenewalFd(fd);
    setRenewalForm(emptyRenewalForm(fd));
    setRenewalFormError('');
    setRenewalModalOpen(true);
  };

  const closeRenewalModal = () => {
    setRenewalModalOpen(false);
    setRenewalFd(null);
    setRenewalFormError('');
  };

  const handleRenewalSubmit = async (e) => {
    e.preventDefault();
    setRenewalFormError('');

    const principal = parseFloat(renewalForm.new_principal_amount);
    const rate = parseFloat(renewalForm.new_interest_rate_percent);
    const gross = parseFloat(renewalForm.gross_interest || '0');
    const tax = parseFloat(renewalForm.tax_withheld || '0');
    const payout = parseFloat(renewalForm.cash_payout_amount || '0');

    if (!renewalForm.new_deposit_account_number.trim()) {
      setRenewalFormError('New deposit account number is required.');
      return;
    }
    if (!Number.isFinite(principal) || principal <= 0) {
      setRenewalFormError('New principal amount must be greater than zero.');
      return;
    }
    if (!Number.isFinite(rate) || rate < 0) {
      setRenewalFormError('New interest rate must be zero or positive.');
      return;
    }
    if (!Number.isFinite(gross) || gross < 0) {
      setRenewalFormError('Gross interest must be zero or positive.');
      return;
    }
    if (!Number.isFinite(tax) || tax < 0) {
      setRenewalFormError('Tax withheld must be zero or positive.');
      return;
    }
    if (tax > gross) {
      setRenewalFormError('Tax withheld cannot exceed gross interest.');
      return;
    }
    if (!Number.isFinite(payout) || payout < 0) {
      setRenewalFormError('Cash payout amount must be zero or positive.');
      return;
    }
    if (!renewalForm.renewal_date) {
      setRenewalFormError('Renewal date is required.');
      return;
    }
    if (!renewalForm.new_maturity_date) {
      setRenewalFormError('New maturity date is required.');
      return;
    }
    const investmentDate = renewalForm.new_investment_date || renewalForm.renewal_date;
    if (renewalForm.new_maturity_date <= investmentDate) {
      setRenewalFormError('New maturity date must be after new investment date.');
      return;
    }

    const payload = {
      renewal_date: renewalForm.renewal_date,
      new_deposit_account_number: renewalForm.new_deposit_account_number.trim(),
      new_principal_amount: renewalForm.new_principal_amount,
      new_interest_rate_percent: renewalForm.new_interest_rate_percent,
      new_interest_payout_frequency: renewalForm.new_interest_payout_frequency,
      new_investment_date: investmentDate,
      new_maturity_date: renewalForm.new_maturity_date,
      gross_interest: renewalForm.gross_interest || '0',
      tax_withheld: renewalForm.tax_withheld || '0',
      cash_payout_amount: renewalForm.cash_payout_amount || '0',
    };
    if (renewalForm.nominee_name.trim()) {
      payload.nominee_name = renewalForm.nominee_name.trim();
    }
    if (renewalForm.comment.trim()) {
      payload.comment = renewalForm.comment.trim();
    }

    setRenewalSubmitting(true);
    try {
      const result = await renewFixedDeposit(renewalFd.id, payload);
      closeRenewalModal();
      setStatus(
        `Renewal recorded. Old FD is ${result.old_fixed_deposit.status}; new FD is ${result.new_fixed_deposit.status}. Renewed principal replaces the old FD in Debt allocation.`
      );
      await loadData();
    } catch (err) {
      setRenewalFormError(err.message || 'Failed to record renewal.');
    } finally {
      setRenewalSubmitting(false);
    }
  };

  const displayRenewalNet = computeDisplayNetInterest(
    renewalForm.gross_interest,
    renewalForm.tax_withheld
  );

  if (!settingsLoaded || loading) {
    return <LoadingState message="Loading fixed deposits…" />;
  }
  if (error && items.length === 0 && !status) {
    return <ErrorState title="Error loading fixed deposits" message={error} />;
  }

  return (
    <div className="fixed-deposits-page">
      <PageHeader
        title="Fixed Deposits"
        subtitle="Debt investments — principal-only portfolio value until settlement; proceeds credit bank cash only."
        actions={
          <Button variant="primary" onClick={openCreate} disabled={bankAccounts.length === 0}>
            Add fixed deposit
          </Button>
        }
      />

      {bankAccounts.length === 0 ? (
        <WarningBanner
          severity="warning"
          message="Add at least one active bank account in Settings before creating a fixed deposit."
        />
      ) : null}

      {status ? <WarningBanner severity="success" message={status} className="fd-banner" /> : null}
      {error ? <WarningBanner severity="error" message={error} className="fd-banner" /> : null}

      <div className="fixed-deposits-page__overview" id="fd-overview" aria-label="Fixed deposit overview">
        <KpiCard
          label="Total deposits"
          value={String(statusCounts.total)}
          helperText="In current portfolio view"
          size="compact"
        />
        <KpiCard
          label="Active"
          value={String(statusCounts.active)}
          helperText="Principal still in debt allocation"
          size="compact"
          variant="gain"
        />
        <KpiCard
          label="Matured"
          value={String(statusCounts.matured)}
          helperText="Awaiting settlement or renewal"
          size="compact"
          variant="warning"
        />
        <KpiCard
          label="Settled / closed"
          value={String(statusCounts.settled)}
          helperText="Lifecycle complete"
          size="compact"
        />
      </div>

      <nav className="fd-section-nav" aria-label="Fixed deposits section navigation">
        {FD_SECTION_NAV.map((item) => (
          <a key={item.href} className="fd-section-nav__link" href={item.href}>
            {item.label}
          </a>
        ))}
      </nav>

      <div id="fd-deposits" className="fixed-deposits-page__deposits">
      <DataTableShell
        className="fixed-deposits-page__table"
        title="Fixed deposit holdings"
        subtitle="Lifecycle actions and interest history per deposit"
        dense
        empty={items.length === 0}
        emptyTitle="No active fixed deposits"
        emptyDescription="No active fixed deposits for the current portfolio view."
      >
        {items.length > 0 ? (
          <AppTable compact className="fd-table">
            <thead>
              <tr>
                <AppTableHeaderCell>Portfolio</AppTableHeaderCell>
                <AppTableHeaderCell>Institution</AppTableHeaderCell>
                <AppTableHeaderCell>Deposit account</AppTableHeaderCell>
                <AppTableHeaderCell>Bank account</AppTableHeaderCell>
                <AppTableHeaderCell numeric>Principal</AppTableHeaderCell>
                <AppTableHeaderCell>Currency</AppTableHeaderCell>
                <AppTableHeaderCell numeric>Rate %</AppTableHeaderCell>
                <AppTableHeaderCell>Payout</AppTableHeaderCell>
                <AppTableHeaderCell>Investment</AppTableHeaderCell>
                <AppTableHeaderCell>Maturity</AppTableHeaderCell>
                <AppTableHeaderCell>Nominee</AppTableHeaderCell>
                <AppTableHeaderCell>Status</AppTableHeaderCell>
                <AppTableHeaderCell className="fd-table__actions-col">Actions</AppTableHeaderCell>
              </tr>
            </thead>
            <tbody>
              {items.map((fd) => {
                const badge = fdStatusBadgeProps(fd.status);
                return (
                  <Fragment key={fd.id}>
                    <tr>
                      <AppTableCell>{fd.portfolio_name}</AppTableCell>
                      <AppTableCell>{fd.institution_name}</AppTableCell>
                      <AppTableCell className="fd-table__account">{fd.deposit_account_number}</AppTableCell>
                      <AppTableCell>{fd.bank_account_name}</AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue value={fd.principal_amount} currency={fd.currency} />
                      </AppTableCell>
                      <AppTableCell>{fd.currency}</AppTableCell>
                      <AppTableCell numeric>{fd.interest_rate_percent}</AppTableCell>
                      <AppTableCell>{fdPayoutLabel(fd.interest_payout_frequency)}</AppTableCell>
                      <AppTableCell>{fd.investment_date}</AppTableCell>
                      <AppTableCell className="fd-table__maturity">{fd.maturity_date}</AppTableCell>
                      <AppTableCell>{fd.nominee_name || '—'}</AppTableCell>
                      <AppTableCell>
                        <StatusBadge status={badge.status} label={badge.label} />
                      </AppTableCell>
                      <AppTableCell className="fd-table__actions-col">
                        <div className="fd-table__actions">
                          {!isSettledFd(fd) ? (
                            <Button
                              variant="secondary"
                              type="button"
                              onClick={() => openInterestModal(fd)}
                            >
                              Record interest
                            </Button>
                          ) : null}
                          {canMarkMatured(fd) ? (
                            <Button
                              variant="secondary"
                              type="button"
                              onClick={() => handleMarkMatured(fd)}
                              disabled={markingMaturedId === fd.id}
                            >
                              {markingMaturedId === fd.id ? 'Marking…' : 'Mark matured'}
                            </Button>
                          ) : null}
                          {canSettle(fd) ? (
                            <Button
                              variant="secondary"
                              type="button"
                              onClick={() => openSettlementModal(fd)}
                            >
                              {fd.status === 'MATURED' ? 'Settle' : 'Settle / Close'}
                            </Button>
                          ) : null}
                          {canRenew(fd) ? (
                            <Button
                              variant="secondary"
                              type="button"
                              onClick={() => openRenewalModal(fd)}
                            >
                              Renew
                            </Button>
                          ) : null}
                          <Button variant="secondary" type="button" onClick={() => openEdit(fd)}>
                            Edit
                          </Button>
                          <Button variant="secondary" type="button" onClick={() => handleDeactivate(fd)}>
                            Deactivate
                          </Button>
                          <Button
                            variant="secondary"
                            type="button"
                            onClick={() => toggleInterestPayments(fd)}
                          >
                            {expandedFdId === fd.id ? 'Hide payments' : 'Interest payments'}
                          </Button>
                        </div>
                      </AppTableCell>
                    </tr>
                    {expandedFdId === fd.id ? (
                      <tr key={`${fd.id}-payments`} className="fd-interest-payments-row">
                        <td colSpan={13}>
                          {interestLoadingFdId === fd.id ? (
                            <p className="settings-hint">Loading interest payments…</p>
                          ) : (interestPaymentsByFd[fd.id] || []).length === 0 ? (
                            <p className="settings-hint">No interest payments recorded yet.</p>
                          ) : (
                            <AppTable compact className="fd-interest-table">
                              <thead>
                                <tr>
                                  <AppTableHeaderCell>Date</AppTableHeaderCell>
                                  <AppTableHeaderCell numeric>Gross</AppTableHeaderCell>
                                  <AppTableHeaderCell numeric>Tax</AppTableHeaderCell>
                                  <AppTableHeaderCell numeric>Net</AppTableHeaderCell>
                                  <AppTableHeaderCell>Comment</AppTableHeaderCell>
                                </tr>
                              </thead>
                              <tbody>
                                {(interestPaymentsByFd[fd.id] || []).map((p) => (
                                  <tr key={p.id}>
                                    <AppTableCell>{p.payment_date}</AppTableCell>
                                    <AppTableCell numeric>
                                      <CurrencyValue value={p.gross_interest} currency={p.currency} />
                                    </AppTableCell>
                                    <AppTableCell numeric>
                                      <CurrencyValue value={p.tax_withheld} currency={p.currency} />
                                    </AppTableCell>
                                    <AppTableCell numeric>
                                      <CurrencyValue value={p.net_interest} currency={p.currency} />
                                    </AppTableCell>
                                    <AppTableCell>{p.comment || '—'}</AppTableCell>
                                  </tr>
                                ))}
                              </tbody>
                            </AppTable>
                          )}
                          <p className="settings-hint">
                            Interest credits bank cash only; FD portfolio value remains principal-only.
                          </p>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </AppTable>
        ) : null}
      </DataTableShell>
      </div>

      {modalOpen ? (
        <div className="fd-modal-backdrop" role="presentation" onClick={() => setModalOpen(false)}>
          <div
            className="fd-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fd-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="fd-modal-title">{editing ? 'Edit fixed deposit' : 'Add fixed deposit'}</h2>
            {!editing ? (
              <p className="settings-hint fd-form__note">
                Creating a fixed deposit will debit the principal from the linked bank account.
              </p>
            ) : null}
            {formError ? <WarningBanner severity="error" message={formError} /> : null}
            {!editing && createBlockedByLedger ? (
              <WarningBanner severity="warning" message={createBlockMessage} />
            ) : null}
            <form onSubmit={handleSubmit} className="fd-form">
              <div className="form-group">
                <label htmlFor="fd-portfolio">Portfolio</label>
                <select
                  id="fd-portfolio"
                  value={form.portfolio_id}
                  onChange={(e) => setForm((p) => ({ ...p, portfolio_id: e.target.value }))}
                  required
                  disabled={openingFieldsLocked}
                >
                  <option value="">Select portfolio</option>
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="fd-bank">Bank account</label>
                <select
                  id="fd-bank"
                  value={form.bank_account_id}
                  onChange={(e) => onBankChange(e.target.value)}
                  required
                  disabled={openingFieldsLocked}
                >
                  <option value="">Select bank account</option>
                  {bankAccounts.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.institution_name})
                    </option>
                  ))}
                </select>
                {selectedBank ? (
                  <>
                    <p className="settings-hint">
                      Ledger balance (current total from API): {ledgerBalance}{' '}
                      {selectedBank.currency}
                    </p>
                    <p className="settings-hint">{FD_BALANCE_AS_OF_NOTE}</p>
                    {!editing && form.investment_date && bankHasLedger(selectedBank) ? (
                      <p className="settings-hint">{FD_BACKDATED_LEDGER_NOTE}</p>
                    ) : null}
                    {hasMisleadingManualBalance(selectedBank) ? (
                      <p className="settings-hint">
                        Reference balance ({selectedBank.current_balance}{' '}
                        {selectedBank.currency}) is not in the cash ledger yet.
                      </p>
                    ) : null}
                    {needsOpeningBalanceSeed(selectedBank) ? (
                      <WarningBanner
                        severity="warning"
                        message="Opening balance is not yet seeded into the cash ledger. Seed opening balance in Settings → Bank Accounts before opening a fixed deposit."
                      />
                    ) : null}
                  </>
                ) : null}
              </div>
              <div className="form-group">
                <label htmlFor="fd-institution">Institution</label>
                <input
                  id="fd-institution"
                  value={form.institution_name}
                  onChange={(e) => setForm((p) => ({ ...p, institution_name: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-deposit-acct">Deposit account number</label>
                <input
                  id="fd-deposit-acct"
                  value={form.deposit_account_number}
                  onChange={(e) => setForm((p) => ({ ...p, deposit_account_number: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-principal">Principal amount</label>
                <input
                  id="fd-principal"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={form.principal_amount}
                  onChange={(e) => setForm((p) => ({ ...p, principal_amount: e.target.value }))}
                  required
                  disabled={openingFieldsLocked}
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-currency">Currency</label>
                <input id="fd-currency" value={form.currency} readOnly disabled={openingFieldsLocked} />
              </div>
              <div className="form-group">
                <label htmlFor="fd-rate">Interest rate (%)</label>
                <input
                  id="fd-rate"
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.interest_rate_percent}
                  onChange={(e) => setForm((p) => ({ ...p, interest_rate_percent: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-payout">Payout frequency</label>
                <select
                  id="fd-payout"
                  value={form.interest_payout_frequency}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, interest_payout_frequency: e.target.value }))
                  }
                >
                  {PAYOUT_FREQUENCIES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="fd-invest">Investment date</label>
                <input
                  id="fd-invest"
                  type="date"
                  value={form.investment_date}
                  onChange={(e) => setForm((p) => ({ ...p, investment_date: e.target.value }))}
                  required
                  disabled={openingFieldsLocked}
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-maturity">Maturity date</label>
                <input
                  id="fd-maturity"
                  type="date"
                  value={form.maturity_date}
                  onChange={(e) => setForm((p) => ({ ...p, maturity_date: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-nominee">Nominee</label>
                <input
                  id="fd-nominee"
                  value={form.nominee_name}
                  onChange={(e) => setForm((p) => ({ ...p, nominee_name: e.target.value }))}
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-status">Status</label>
                <select
                  id="fd-status"
                  value={form.status}
                  onChange={(e) => setForm((p) => ({ ...p, status: e.target.value }))}
                >
                  {STATUSES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="fd-comment">Comment</label>
                <textarea
                  id="fd-comment"
                  value={form.comment}
                  onChange={(e) => setForm((p) => ({ ...p, comment: e.target.value }))}
                  rows={2}
                />
              </div>
              <div className="fd-form__actions">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={submitting || createBlockedByLedger}
                >
                  {submitting ? 'Saving…' : editing ? 'Save changes' : 'Create'}
                </Button>
                <Button type="button" variant="secondary" onClick={() => setModalOpen(false)}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {interestModalOpen && interestFd ? (
        <div
          className="fd-modal-backdrop"
          role="presentation"
          onClick={closeInterestModal}
        >
          <div
            className="fd-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fd-interest-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="fd-interest-modal-title">Record interest payment</h2>
            <p className="settings-hint fd-form__note">
              Net interest is credited to {interestFd.bank_account_name}. FD portfolio value
              stays principal-only.
            </p>
            {interestFormError ? <WarningBanner severity="error" message={interestFormError} /> : null}
            <form onSubmit={handleInterestSubmit} className="fd-form" noValidate>
              <div className="form-group">
                <label htmlFor="fd-int-date">Payment date</label>
                <input
                  id="fd-int-date"
                  type="date"
                  value={interestForm.payment_date}
                  onChange={(e) =>
                    setInterestForm((p) => ({ ...p, payment_date: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-int-gross">Gross interest</label>
                <input
                  id="fd-int-gross"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={interestForm.gross_interest}
                  onChange={(e) =>
                    setInterestForm((p) => ({ ...p, gross_interest: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-int-tax">Tax withheld (TDS)</label>
                <input
                  id="fd-int-tax"
                  type="number"
                  step="0.01"
                  min="0"
                  value={interestForm.tax_withheld}
                  onChange={(e) =>
                    setInterestForm((p) => ({ ...p, tax_withheld: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-int-net">Net interest (display only)</label>
                <input
                  id="fd-int-net"
                  value={
                    displayNetInterest == null
                      ? ''
                      : `${displayNetInterest} ${interestFd.currency}`
                  }
                  readOnly
                  disabled
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-int-comment">Comment (optional)</label>
                <textarea
                  id="fd-int-comment"
                  value={interestForm.comment}
                  onChange={(e) =>
                    setInterestForm((p) => ({ ...p, comment: e.target.value }))
                  }
                  rows={2}
                />
              </div>
              <div className="fd-form__actions">
                <Button type="submit" variant="primary" disabled={interestSubmitting}>
                  {interestSubmitting ? 'Saving…' : 'Record payment'}
                </Button>
                <Button type="button" variant="secondary" onClick={closeInterestModal}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {settlementModalOpen && settlementFd ? (
        <div
          className="fd-modal-backdrop"
          role="presentation"
          onClick={closeSettlementModal}
        >
          <div
            className="fd-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fd-settlement-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="fd-settlement-modal-title">Record settlement</h2>
            <p className="settings-hint fd-form__note">
              Proceeds credit {settlementFd.bank_account_name}. FD principal leaves portfolio
              value after settlement; bank cash is not included in portfolio totals yet.
            </p>
            {settlementFormError ? (
              <WarningBanner severity="error" message={settlementFormError} />
            ) : null}
            <form onSubmit={handleSettlementSubmit} className="fd-form" noValidate>
              <div className="form-group">
                <label htmlFor="fd-settle-type">Settlement type</label>
                <select
                  id="fd-settle-type"
                  value={settlementForm.settlement_type}
                  onChange={(e) =>
                    setSettlementForm((p) => ({ ...p, settlement_type: e.target.value }))
                  }
                >
                  <option value="MATURITY">Maturity</option>
                  <option value="CLOSURE">Closure</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-date">Settlement date</label>
                <input
                  id="fd-settle-date"
                  type="date"
                  value={settlementForm.settlement_date}
                  onChange={(e) =>
                    setSettlementForm((p) => ({ ...p, settlement_date: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-principal">Principal returned</label>
                <input
                  id="fd-settle-principal"
                  type="number"
                  step="0.01"
                  min="0"
                  value={settlementForm.principal_returned}
                  onChange={(e) =>
                    setSettlementForm((p) => ({ ...p, principal_returned: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-gross">Gross final interest</label>
                <input
                  id="fd-settle-gross"
                  type="number"
                  step="0.01"
                  min="0"
                  value={settlementForm.gross_interest}
                  onChange={(e) =>
                    setSettlementForm((p) => ({ ...p, gross_interest: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-tax">Tax withheld (TDS)</label>
                <input
                  id="fd-settle-tax"
                  type="number"
                  step="0.01"
                  min="0"
                  value={settlementForm.tax_withheld}
                  onChange={(e) =>
                    setSettlementForm((p) => ({ ...p, tax_withheld: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-net">Net interest (display only)</label>
                <input
                  id="fd-settle-net"
                  value={
                    displaySettlementNet == null
                      ? ''
                      : `${displaySettlementNet} ${settlementFd.currency}`
                  }
                  readOnly
                  disabled
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-total">Total net proceeds (display only)</label>
                <input
                  id="fd-settle-total"
                  value={
                    displayTotalProceeds == null
                      ? ''
                      : `${displayTotalProceeds} ${settlementFd.currency}`
                  }
                  readOnly
                  disabled
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-settle-comment">Comment (optional)</label>
                <textarea
                  id="fd-settle-comment"
                  value={settlementForm.comment}
                  onChange={(e) =>
                    setSettlementForm((p) => ({ ...p, comment: e.target.value }))
                  }
                  rows={2}
                />
              </div>
              <div className="fd-form__actions">
                <Button type="submit" variant="primary" disabled={settlementSubmitting}>
                  {settlementSubmitting ? 'Saving…' : 'Record settlement'}
                </Button>
                <Button type="button" variant="secondary" onClick={closeSettlementModal}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {renewalModalOpen && renewalFd ? (
        <div
          className="fd-modal-backdrop"
          role="presentation"
          onClick={closeRenewalModal}
        >
          <div
            className="fd-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fd-renewal-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="fd-renewal-modal-title">Renew fixed deposit</h2>
            <p className="settings-hint fd-form__note">
              Directly renewed principal will not pass through the bank account. Only cash
              payout/net received amounts are credited to bank cash.
            </p>
            <WarningBanner
              severity="warning"
              message="Bank cash is still not included in portfolio value. Renewed FD principal replaces the old FD principal in Debt allocation."
            />
            {renewalFormError ? (
              <WarningBanner severity="error" message={renewalFormError} />
            ) : null}
            <form onSubmit={handleRenewalSubmit} className="fd-form" noValidate>
              <div className="form-group">
                <label htmlFor="fd-renew-date">Renewal date</label>
                <input
                  id="fd-renew-date"
                  type="date"
                  value={renewalForm.renewal_date}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, renewal_date: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-acct">New deposit account number</label>
                <input
                  id="fd-renew-acct"
                  value={renewalForm.new_deposit_account_number}
                  onChange={(e) =>
                    setRenewalForm((p) => ({
                      ...p,
                      new_deposit_account_number: e.target.value,
                    }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-principal">New principal amount</label>
                <input
                  id="fd-renew-principal"
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={renewalForm.new_principal_amount}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, new_principal_amount: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-rate">New interest rate (%)</label>
                <input
                  id="fd-renew-rate"
                  type="number"
                  step="0.01"
                  min="0"
                  value={renewalForm.new_interest_rate_percent}
                  onChange={(e) =>
                    setRenewalForm((p) => ({
                      ...p,
                      new_interest_rate_percent: e.target.value,
                    }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-payout">New payout frequency</label>
                <select
                  id="fd-renew-payout"
                  value={renewalForm.new_interest_payout_frequency}
                  onChange={(e) =>
                    setRenewalForm((p) => ({
                      ...p,
                      new_interest_payout_frequency: e.target.value,
                    }))
                  }
                >
                  {PAYOUT_FREQUENCIES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-invest">New investment date</label>
                <input
                  id="fd-renew-invest"
                  type="date"
                  value={renewalForm.new_investment_date}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, new_investment_date: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-maturity">New maturity date</label>
                <input
                  id="fd-renew-maturity"
                  type="date"
                  value={renewalForm.new_maturity_date}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, new_maturity_date: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-gross">Gross interest</label>
                <input
                  id="fd-renew-gross"
                  type="number"
                  step="0.01"
                  min="0"
                  value={renewalForm.gross_interest}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, gross_interest: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-tax">Tax withheld (TDS)</label>
                <input
                  id="fd-renew-tax"
                  type="number"
                  step="0.01"
                  min="0"
                  value={renewalForm.tax_withheld}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, tax_withheld: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-net">Net interest (display only)</label>
                <input
                  id="fd-renew-net"
                  value={
                    displayRenewalNet == null
                      ? ''
                      : `${displayRenewalNet} ${renewalFd.currency}`
                  }
                  readOnly
                  disabled
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-payout-amt">Cash payout amount</label>
                <input
                  id="fd-renew-payout-amt"
                  type="number"
                  step="0.01"
                  min="0"
                  value={renewalForm.cash_payout_amount}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, cash_payout_amount: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-nominee">Nominee</label>
                <input
                  id="fd-renew-nominee"
                  value={renewalForm.nominee_name}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, nominee_name: e.target.value }))
                  }
                />
              </div>
              <div className="form-group">
                <label htmlFor="fd-renew-comment">Comment (optional)</label>
                <textarea
                  id="fd-renew-comment"
                  value={renewalForm.comment}
                  onChange={(e) =>
                    setRenewalForm((p) => ({ ...p, comment: e.target.value }))
                  }
                  rows={2}
                />
              </div>
              <div className="fd-form__actions">
                <Button type="submit" variant="primary" disabled={renewalSubmitting}>
                  {renewalSubmitting ? 'Saving…' : 'Record renewal'}
                </Button>
                <Button type="button" variant="secondary" onClick={closeRenewalModal}>
                  Cancel
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
