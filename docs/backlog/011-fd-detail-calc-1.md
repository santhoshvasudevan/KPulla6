# FD-DETAIL-CALC-1 — Fixed Deposit detail page with interest schedule

**Branch:** `agent/011-fd-detail-calc-1`  
**Status:** Done

## Goal

Dedicated `/fixed-deposits/:id` page with expected interest schedule, actual credit recording/editing, tax withheld, Indian FY filter, and detailed calculation section.

## Implemented

- `GET /fixed-deposits/{id}/detail` composite API
- Pure schedule generator in `finance/fd_interest_schedule.py`
- `PATCH /fixed-deposit-interest-payments/{id}` with linked cash movement update
- `FixedDepositDetail.jsx` page + holdings row navigation

## Deferred

- PDF/export
- Global tax rate automation
- Explicit schedule-to-payment DB link field
- Broker credit destination
