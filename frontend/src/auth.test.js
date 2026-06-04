import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from './api';

describe('API auth handling', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
    api.invalidateDashboardSummaryCache();
    api.setUnauthorizedHandler(null);
  });

  it('fetchCurrentUser calls auth me endpoint with credentials', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 1, username: 'demo', email: 'demo@example.com' }),
    });
    await api.fetchCurrentUser();
    const [, opts] = global.fetch.mock.calls[0];
    expect(global.fetch.mock.calls[0][0]).toContain('/api/v1/auth/me');
    expect(opts.credentials).toBe('include');
  });

  it('401 handling invokes unauthorized handler', async () => {
    const handler = vi.fn();
    api.setUnauthorizedHandler(handler);
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Authentication credentials were not provided.' }),
    });
    await expect(api.fetchPortfolios()).rejects.toThrow();
    expect(handler).toHaveBeenCalled();
  });
});
