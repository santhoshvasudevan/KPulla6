import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  createFixedDepositInterestPayment,
  fetchFixedDepositDetail,
  updateFixedDepositInterestPayment,
} from '../api';
import {
  AppCard,
  AppTable,
  AppTableCell,
  AppTableHeaderCell,
  Button,
  CurrencyValue,
  DataTableShell,
  ErrorState,
  KpiCard,
  LoadingState,
  PageHeader,
  StatusBadge,
  WarningBanner,
} from '../components/ui';
import FixedDepositInterestPaymentForm, {
  newInterestClientRequestId,
} from '../components/FixedDepositInterestPaymentForm';
import {
  FixedDepositPayoutResolveModal,
  FixedDepositPayoutReviewSummary,
} from '../components/FixedDepositPayoutReview';
import {
  fdDisplayMaturitySource,
  fdDisplayMaturityValue,
  fdDisplayTotalInterest,
  fdIsCompounded,
  fdIsPayout,
  fdMaturityValueSourceBadgeProps,
  fdPayoutLabel,
  fdStatusBadgeProps,
} from '../utils/fdDisplay';
import { formatCurrency } from '../utils/formatters';
import '../components/FixedDepositInterestPaymentForm.css';
import './FixedDepositDetail.css';

const SECTION_NAV = [
  { href: '#fd-detail-overview', label: 'Overview' },
  { href: '#fd-detail-schedule', label: 'Interest schedule' },
  { href: '#fd-detail-calculation', label: 'Calculation' },
];
const PAYOUT_NAV_ITEM = { href: '#fd-detail-final-payout', label: 'Final payout' };

function DetailRow({ label, children }) {
  return (
    <div className="fd-detail__row">
      <dt className="fd-detail__row-label">{label}</dt>
      <dd className="fd-detail__row-value">{children}</dd>
    </div>
  );
}

function scheduleStatusBadge(status) {
  if (status === 'RECORDED') return { status: 'ok', label: 'Recorded' };
  if (status === 'OVERDUE') return { status: 'warning', label: 'Not recorded' };
  if (status === 'UPCOMING') return { status: 'neutral', label: 'Upcoming' };
  return { status: 'neutral', label: 'Maturity accrual' };
}

function emptyActualForm() {
  return {
    payment_date: '',
    gross_interest: '',
    tax_withheld: '0',
    comment: '',
  };
}

export default function FixedDepositDetail() {
  const { fdId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [financialYear, setFinancialYear] = useState('');
  const [actualModalOpen, setActualModalOpen] = useState(false);
  const [actualForm, setActualForm] = useState(emptyActualForm);
  const [actualFormError, setActualFormError] = useState('');
  const [actualSaving, setActualSaving] = useState(false);
  const [editingPaymentId, setEditingPaymentId] = useState(null);
  const [scheduleContext, setScheduleContext] = useState(null);
  const [actualClientRequestId, setActualClientRequestId] = useState('');
  const [resolveTarget, setResolveTarget] = useState(null);
  const [status, setStatus] = useState('');

  const loadData = useCallback(() => {
    if (!fdId) return;
    setLoading(true);
    setError('');
    const query = financialYear ? { financial_year: financialYear } : {};
    fetchFixedDepositDetail(fdId, query)
      .then((payload) => {
        setData(payload);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [fdId, financialYear]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const fd = data?.fixed_deposit;
  const currency = fd?.currency || 'INR';
  const termTotals = data?.term_totals || {};
  const fySummary = data?.financial_year_summary;
  const calc = data?.detailed_calculation;
  const schedule = data?.expected_interest_schedule || [];
  const finalPayout = data?.pending_payout || null;
  const sectionNav = finalPayout ? [...SECTION_NAV, PAYOUT_NAV_ITEM] : SECTION_NAV;

  const handleDiscrepancyResolved = () => {
    setResolveTarget(null);
    setStatus('Payout discrepancy marked resolved.');
    loadData();
  };

  const openRecordActual = (row) => {
    setEditingPaymentId(null);
    setScheduleContext(row);
    setActualClientRequestId(newInterestClientRequestId());
    setActualForm({
      payment_date: row.expected_payout_date,
      gross_interest: String(row.expected_gross_interest ?? ''),
      tax_withheld: '0',
      comment: '',
    });
    setActualFormError('');
    setActualModalOpen(true);
  };

  const openEditActual = (row, payment) => {
    setEditingPaymentId(payment.id);
    setScheduleContext(row);
    setActualClientRequestId('');
    setActualForm({
      payment_date: payment.payment_date,
      gross_interest: String(payment.gross_interest ?? ''),
      tax_withheld: String(payment.tax_withheld ?? '0'),
      comment: payment.comment || '',
    });
    setActualFormError('');
    setActualModalOpen(true);
  };

  const closeActualModal = () => {
    setActualModalOpen(false);
    setEditingPaymentId(null);
    setScheduleContext(null);
    setActualClientRequestId('');
    setActualFormError('');
  };

  const saveActual = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    const gross = parseFloat(actualForm.gross_interest);
    const tax = parseFloat(actualForm.tax_withheld || '0');
    if (!actualForm.payment_date) {
      setActualFormError('Actual credited date is required.');
      return;
    }
    if (Number.isNaN(gross) || gross <= 0) {
      setActualFormError('Gross interest must be greater than zero.');
      return;
    }
    if (Number.isNaN(tax) || tax < 0) {
      setActualFormError('Tax withheld must be zero or positive.');
      return;
    }
    if (tax > gross) {
      setActualFormError('Tax withheld cannot exceed gross interest.');
      return;
    }

    const payload = {
      payment_date: actualForm.payment_date,
      gross_interest: String(gross),
      tax_withheld: String(tax),
    };
    if (actualForm.comment.trim()) {
      payload.comment = actualForm.comment.trim();
    }
    if (!editingPaymentId) {
      payload.client_request_id = actualClientRequestId || newInterestClientRequestId();
    }

    setActualSaving(true);
    setActualFormError('');
    try {
      if (editingPaymentId) {
        await updateFixedDepositInterestPayment(editingPaymentId, payload);
      } else {
        await createFixedDepositInterestPayment(fdId, payload);
      }
      closeActualModal();
      loadData();
    } catch (err) {
      setActualFormError(err.message);
    } finally {
      setActualSaving(false);
    }
  };

  if (loading) {
    return <LoadingState message="Loading fixed deposit detail…" />;
  }
  if (error) {
    return (
      <ErrorState title="Unable to load fixed deposit" message={error} onRetry={loadData} />
    );
  }
  if (!fd) return null;

  const statusBadge = fdStatusBadgeProps(fd.status);
  const displayMaturity = fdDisplayMaturityValue(fd);
  const displayTotalInterest = fdDisplayTotalInterest(fd);
  const maturitySource = fdDisplayMaturitySource(fd);
  const compounded = fdIsCompounded(fd);
  const payout = fdIsPayout(fd);

  return (
    <div className="fd-detail">
      <p className="fd-detail__breadcrumb">
        <Link to="/fixed-deposits" className="fd-detail__breadcrumb-link">
          ← Fixed Deposits
        </Link>
      </p>

      <header className="fd-detail__hero" id="fd-detail-overview">
        <PageHeader
          title="Fixed Deposit Detail"
          subtitle={`${fd.institution_name} · ${fd.deposit_account_number}`}
          actions={<StatusBadge {...statusBadge} />}
        />
      </header>

      {data.warnings?.length ? (
        <div className="fd-detail__warnings">
          {data.warnings.map((warning) => (
            <WarningBanner key={warning} severity="warning" message={warning} />
          ))}
        </div>
      ) : null}
      {status ? <WarningBanner severity="success" message={status} /> : null}

      <nav className="fd-detail-section-nav" aria-label="Fixed deposit detail sections">
        {sectionNav.map((item) => (
          <a key={item.href} href={item.href} className="fd-detail-section-nav__link">
            {item.label}
          </a>
        ))}
      </nav>

      <div className="fd-detail-kpi-grid">
        <KpiCard label="Principal" value={<CurrencyValue value={fd.principal_amount} currency={currency} />} />
        <KpiCard
          label="Expected total interest"
          value={
            displayTotalInterest != null ? (
              <CurrencyValue value={displayTotalInterest} currency={currency} />
            ) : (
              '—'
            )
          }
        />
        <KpiCard
          label="Actual gross interest"
          value={<CurrencyValue value={termTotals.actual_gross_interest ?? 0} currency={currency} />}
        />
        <KpiCard
          label="Tax withheld"
          value={<CurrencyValue value={termTotals.tax_withheld ?? 0} currency={currency} />}
        />
        <KpiCard
          label="Total net interest"
          value={<CurrencyValue value={termTotals.actual_net_interest ?? 0} currency={currency} />}
          helperText="Confirmed interest for this term (cash + reinvested)"
        />
        <div data-testid="fd-detail-interest-paid">
          <KpiCard
            label="Interest paid to bank"
            value={
              termTotals.interest_cash_amount == null ? (
                <span data-testid="fd-detail-interest-paid-unavailable">Unavailable</span>
              ) : (
                <CurrencyValue value={termTotals.interest_cash_amount} currency={currency} />
              )
            }
            helperText={
              termTotals.interest_cash_amount == null
                ? 'Legacy renewal split unknown'
                : 'Cash credited to the linked bank account'
            }
          />
        </div>
        <div data-testid="fd-detail-interest-reinvested">
          <KpiCard
            label="Interest reinvested"
            value={
              termTotals.reinvested_interest_amount == null ? (
                <span data-testid="fd-detail-interest-reinvested-unavailable">Unavailable</span>
              ) : (
                <CurrencyValue value={termTotals.reinvested_interest_amount} currency={currency} />
              )
            }
            helperText={
              termTotals.reinvested_interest_amount == null
                ? 'Legacy renewal split unknown'
                : 'Retained in a renewed principal'
            }
          />
        </div>
        <KpiCard
          label={compounded ? 'Expected maturity value' : 'Principal at maturity'}
          value={
            displayMaturity != null ? (
              <CurrencyValue value={displayMaturity} currency={currency} />
            ) : (
              '—'
            )
          }
        />
      </div>

      <AppCard title="FD details" className="fd-detail-card">
        <dl className="fd-detail__details-grid">
          <DetailRow label="Portfolio">{fd.portfolio_name}</DetailRow>
          <DetailRow label="Institution">{fd.institution_name}</DetailRow>
          <DetailRow label="Deposit account">{fd.deposit_account_number}</DetailRow>
          <DetailRow label="Bank account">{fd.bank_account_name}</DetailRow>
          <DetailRow label="Principal">
            <CurrencyValue value={fd.principal_amount} currency={currency} />
          </DetailRow>
          <DetailRow label="Currency">{fd.currency}</DetailRow>
          <DetailRow label="Rate">{fd.interest_rate_percent}%</DetailRow>
          <DetailRow label="Payout frequency">
            {fdPayoutLabel(fd.interest_payout_frequency)}
          </DetailRow>
          <DetailRow label="Investment date">{fd.investment_date}</DetailRow>
          <DetailRow label="Maturity date">{fd.maturity_date}</DetailRow>
          <DetailRow label="Nominee">{fd.nominee_name || '—'}</DetailRow>
          <DetailRow label="Status">
            <StatusBadge {...statusBadge} />
          </DetailRow>
          <DetailRow label={compounded ? 'Expected maturity value' : 'Maturity value'}>
            {displayMaturity != null ? (
              <>
                <CurrencyValue value={displayMaturity} currency={currency} />
                {payout ? <span className="fd-detail__inline-note"> (principal returned)</span> : null}
              </>
            ) : (
              '—'
            )}
          </DetailRow>
          <DetailRow label="Estimate source">
            <StatusBadge {...fdMaturityValueSourceBadgeProps(maturitySource, fd)} />
            {fd.maturity_estimate_method_label ? (
              <span className="fd-detail__inline-note"> · {fd.maturity_estimate_method_label}</span>
            ) : null}
          </DetailRow>
        </dl>
      </AppCard>

      <AppCard title="Financial year filter" className="fd-detail-card">
        <div className="fd-detail__fy-filter">
          <label htmlFor="fd-detail-fy">Indian financial year</label>
          <select
            id="fd-detail-fy"
            value={financialYear}
            onChange={(e) => setFinancialYear(e.target.value)}
          >
            <option value="">All (full term)</option>
            {(data.financial_year_options || []).map((fy) => (
              <option key={fy} value={fy}>
                FY {fy}
              </option>
            ))}
          </select>
        </div>
        {fySummary ? (
          <div className="fd-detail__fy-summary" data-testid="fd-detail-fy-summary">
            <p>
              FY {fySummary.financial_year}: expected{' '}
              {formatCurrency(fySummary.expected_gross_interest_fy, currency)} · actual{' '}
              {formatCurrency(fySummary.actual_gross_interest_fy, currency)} · tax{' '}
              {formatCurrency(fySummary.tax_withheld_fy, currency)} · net{' '}
              {formatCurrency(fySummary.actual_net_interest_fy, currency)}
              {' · paid to bank '}
              {fySummary.interest_cash_amount_fy == null
                ? 'Unavailable'
                : formatCurrency(fySummary.interest_cash_amount_fy, currency)}
              {' · reinvested '}
              {fySummary.reinvested_interest_amount_fy == null
                ? 'Unavailable'
                : formatCurrency(fySummary.reinvested_interest_amount_fy, currency)}
            </p>
          </div>
        ) : null}
      </AppCard>

      <section id="fd-detail-schedule">
        <DataTableShell
          title="Expected interest schedule"
          subtitle="Forecast only — record actual credits when interest is credited to your bank account"
          dense
          empty={schedule.length === 0}
          emptyTitle={compounded ? 'No periodic payout schedule' : 'No schedule generated'}
          emptyDescription={
            compounded
              ? 'Compounded FDs accrue interest to maturity; use settlement when the FD matures.'
              : 'Check FD dates and payout frequency.'
          }
        >
          {schedule.length > 0 ? (
            <AppTable compact>
              <thead>
                <tr>
                  <AppTableHeaderCell>Expected payout</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Expected gross</AppTableHeaderCell>
                  <AppTableHeaderCell>Actual credited</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Actual gross</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Tax withheld</AppTableHeaderCell>
                  <AppTableHeaderCell numeric>Net credited</AppTableHeaderCell>
                  <AppTableHeaderCell>Credited to</AppTableHeaderCell>
                  <AppTableHeaderCell>Status</AppTableHeaderCell>
                  <AppTableHeaderCell>Actions</AppTableHeaderCell>
                </tr>
              </thead>
              <tbody>
                {schedule.map((row) => {
                  const payment = row.matched_payment;
                  const canRecord =
                    row.schedule_row_type === 'PAYOUT' &&
                    !payment &&
                    fd.status !== 'CLOSED' &&
                    fd.status !== 'MATURED_SETTLED' &&
                    fd.status !== 'CANCELLED';
                  return (
                    <tr key={`${row.period_index}-${row.expected_payout_date}`}>
                      <AppTableCell>{row.expected_payout_date}</AppTableCell>
                      <AppTableCell numeric>
                        <CurrencyValue value={row.expected_gross_interest} currency={currency} />
                      </AppTableCell>
                      <AppTableCell>{payment?.payment_date || '—'}</AppTableCell>
                      <AppTableCell numeric>
                        {payment ? (
                          <CurrencyValue value={payment.gross_interest} currency={currency} />
                        ) : (
                          '—'
                        )}
                      </AppTableCell>
                      <AppTableCell numeric>
                        {payment ? (
                          <CurrencyValue value={payment.tax_withheld} currency={currency} />
                        ) : (
                          '—'
                        )}
                      </AppTableCell>
                      <AppTableCell numeric>
                        {payment ? (
                          <CurrencyValue value={payment.net_interest} currency={currency} />
                        ) : (
                          '—'
                        )}
                      </AppTableCell>
                      <AppTableCell>{payment?.bank_account_name || fd.bank_account_name}</AppTableCell>
                      <AppTableCell>
                        <StatusBadge {...scheduleStatusBadge(row.status)} />
                      </AppTableCell>
                      <AppTableCell>
                        {payment ? (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => openEditActual(row, payment)}
                          >
                            Edit actual
                          </Button>
                        ) : canRecord ? (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => openRecordActual(row)}
                          >
                            Record actual
                          </Button>
                        ) : (
                          '—'
                        )}
                      </AppTableCell>
                    </tr>
                  );
                })}
              </tbody>
            </AppTable>
          ) : null}
        </DataTableShell>
      </section>

      <section id="fd-detail-calculation">
        <AppCard title="Detailed calculation" className="fd-detail-card">
          {calc ? (
            <dl className="fd-detail__details-grid">
              <DetailRow label="Principal">
                <CurrencyValue value={calc.principal} currency={currency} />
              </DetailRow>
              <DetailRow label="Interest rate">{calc.interest_rate_percent}%</DetailRow>
              <DetailRow label="Tenure">
                {calc.tenure_days} days ({Number(calc.tenure_years_fractional).toFixed(4)} years)
              </DetailRow>
              <DetailRow label="Payout frequency">
                {fdPayoutLabel(calc.payout_frequency)}
              </DetailRow>
              <DetailRow label="Day-count method">{calc.day_count_method}</DetailRow>
              <DetailRow label="Period basis">{calc.period_generation_basis}</DetailRow>
              {calc.expected_periodic_interest != null ? (
                <DetailRow label="Expected periodic interest">
                  <CurrencyValue value={calc.expected_periodic_interest} currency={currency} />
                </DetailRow>
              ) : null}
              {calc.expected_total_interest != null ? (
                <DetailRow label="Expected total interest">
                  <CurrencyValue value={calc.expected_total_interest} currency={currency} />
                </DetailRow>
              ) : null}
              {calc.expected_maturity_value != null ? (
                <DetailRow label={compounded ? 'Expected maturity value' : 'Principal at maturity'}>
                  <CurrencyValue value={calc.expected_maturity_value} currency={currency} />
                </DetailRow>
              ) : null}
            </dl>
          ) : null}
          <p className="fd-detail__approx-note">{calc?.approximation_note}</p>
        </AppCard>
      </section>

      {finalPayout ? (
        <section id="fd-detail-final-payout">
          <AppCard title="Final maturity payout" className="fd-detail-card">
            <FixedDepositPayoutReviewSummary payout={finalPayout} onResolve={setResolveTarget} />
          </AppCard>
        </section>
      ) : null}

      {resolveTarget ? (
        <FixedDepositPayoutResolveModal
          payout={resolveTarget}
          termLabel={`${fd.institution_name} / ${fd.deposit_account_number}`}
          onClose={() => setResolveTarget(null)}
          onResolved={handleDiscrepancyResolved}
          backdropClassName="fd-detail-modal-backdrop"
          modalClassName="fd-detail-modal"
        />
      ) : null}

      {actualModalOpen ? (
        <div className="fd-detail-modal-backdrop" role="presentation" onClick={closeActualModal}>
          <div
            className="fd-detail-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="fd-actual-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <FixedDepositInterestPaymentForm
              title={
                editingPaymentId ? 'Edit actual interest credit' : 'Record actual interest credit'
              }
              form={actualForm}
              onChange={setActualForm}
              onSubmit={saveActual}
              onCancel={closeActualModal}
              submitting={actualSaving}
              error={actualFormError}
              currency={currency}
              bankAccountName={fd.bank_account_name}
              suggested={
                scheduleContext
                  ? {
                      expected_payout_date: scheduleContext.expected_payout_date,
                      expected_gross_interest: scheduleContext.expected_gross_interest,
                    }
                  : null
              }
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
