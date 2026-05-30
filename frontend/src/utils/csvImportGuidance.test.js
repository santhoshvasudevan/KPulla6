import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  getSampleMutualFundCsvContent,
  downloadSampleMutualFundCsv,
  SAMPLE_MF_CSV_FILENAME,
  STOCK_CSV_COLUMNS,
  MF_CSV_REQUIRED_COLUMNS,
} from './csvImportGuidance';

describe('csvImportGuidance', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:sample'),
      revokeObjectURL: vi.fn(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('exposes stock and MF column guidance strings', () => {
    expect(STOCK_CSV_COLUMNS).toMatch(/ASSET SYMBOL/);
    expect(MF_CSV_REQUIRED_COLUMNS).toMatch(/Scheme Code/);
    expect(MF_CSV_REQUIRED_COLUMNS).toMatch(/Folio Number/);
  });

  it('sample MF CSV includes header and one BUY row', () => {
    const content = getSampleMutualFundCsvContent();
    expect(content).toContain('Scheme Code,Scheme Name,Folio Number');
    expect(content.trim().split('\n')).toHaveLength(2);
    expect(content).toMatch(/^BUY,/m);
  });

  it('downloadSampleMutualFundCsv triggers a client-side download', () => {
    const click = vi.fn();
    const appendChild = vi.spyOn(document.body, 'appendChild').mockImplementation((node) => {
      node.click = click;
      return node;
    });
    const removeChild = vi.spyOn(document.body, 'removeChild').mockImplementation(() => {});

    downloadSampleMutualFundCsv();

    expect(URL.createObjectURL).toHaveBeenCalled();
    const blob = URL.createObjectURL.mock.calls[0][0];
    expect(blob.type).toBe('text/csv;charset=utf-8');
    expect(appendChild).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
    const anchor = appendChild.mock.calls[0][0];
    expect(anchor.download).toBe(SAMPLE_MF_CSV_FILENAME);
    expect(removeChild).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:sample');

    appendChild.mockRestore();
    removeChild.mockRestore();
  });
});
