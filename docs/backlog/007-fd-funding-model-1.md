# 007 — FD-FUNDING-MODEL-1: FD funding decoupling + historical bank balance seed

**Status:** Done (2026-06-29)

**Depends on:** CASH-MODEL-REFINE-1 (006)

## Goal

Bank accounts fund FDs without portfolio link. When as-of bank balance is insufficient for a backdated FD, user can explicitly seed historical balance before FD create.

## Implemented

- FD create explicit portfolio + bank funding (if not already from 006)
- `POST /api/v1/bank-accounts/{id}/seed-balance` → `MANUAL_DEPOSIT`
- FD create modal: insufficient balance panel + inline seed flow
- Docs updated

## Deferred

- Broker-funded FD
- Partial mixed funding
- Combined seed+create in one transaction
