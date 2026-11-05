import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';

const mockGetAssetReviewGames = vi.fn();
const mockGetAssetReviewCsv = vi.fn();
const mockValidateAssetReviewRow = vi.fn();
const mockUpdateAssetReviewFields = vi.fn();
const mockUpdateAssetReviewRow = vi.fn();
const mockGetAssetReviewImageUrl = vi.fn();

vi.mock('../../src/lib/api.ts', () => ({
  getAssetReviewGames: (...args) => mockGetAssetReviewGames(...args),
  getAssetReviewCsv: (...args) => mockGetAssetReviewCsv(...args),
  validateAssetReviewRow: (...args) => mockValidateAssetReviewRow(...args),
  updateAssetReviewFields: (...args) => mockUpdateAssetReviewFields(...args),
  updateAssetReviewRow: (...args) => mockUpdateAssetReviewRow(...args),
  getAssetReviewImageUrl: (...args) => mockGetAssetReviewImageUrl(...args),
}));

import AssetReviewer from '../../src/routes/asset-reviewer/+page.svelte';

describe('AssetReviewer record/image synchronization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAssetReviewGames.mockResolvedValue({
      root_name: 'documentation',
      games: [{ id: 'twilight-struggle', csv_files: ['cards.csv'] }],
    });
    mockGetAssetReviewCsv.mockResolvedValue({
      csv_name: 'cards.csv',
      fields: ['File Name', 'Validated'],
      rows: [
        { 'File Name': 'TNRnTS-10.svg', Validated: '' },
        { 'File Name': 'TNRnTS-11.svg', Validated: '' },
      ],
    });
    mockValidateAssetReviewRow.mockResolvedValue({});
    mockGetAssetReviewImageUrl.mockImplementation((_game, filename) => `/images/${filename}`);
  });

  it('shows the next record image after validating the current record', async () => {
    render(AssetReviewer);

    await fireEvent.click(screen.getByRole('button', { name: 'Load CSV' }));
    await fireEvent.click(await screen.findByRole('button', { name: 'Open CSV' }));

    await waitFor(() => expect(screen.getByText('Previewing: TNRnTS-10.svg')).toBeTruthy());
    expect(screen.getByRole('img', { name: 'Preview of TNRnTS-10.svg' }).getAttribute('src'))
      .toBe('/images/TNRnTS-10.svg');

    await fireEvent.click(screen.getByRole('button', { name: /Validated/ }));

    await waitFor(() => expect(screen.getByText('RECORD 2 OF 2')).toBeTruthy());
    expect(screen.getByText('Previewing: TNRnTS-11.svg')).toBeTruthy();
    expect(screen.getByRole('img', { name: 'Preview of TNRnTS-11.svg' }).getAttribute('src'))
      .toBe('/images/TNRnTS-11.svg');
    expect(mockValidateAssetReviewRow).toHaveBeenCalledWith('twilight-struggle', 'cards.csv', 0, true);
  });
});