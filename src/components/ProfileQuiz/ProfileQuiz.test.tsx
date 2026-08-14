import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import ProfileQuiz from './ProfileQuiz';
import { ToastProvider } from '../../context/ToastContext';

function makeClient(): AxiosInstance {
  return {
    get: vi.fn().mockResolvedValue({ data: ['Bank', 'Pharma'] }),
    put: vi.fn().mockImplementation((_u, body) => Promise.resolve({ data: body })),
  } as unknown as AxiosInstance;
}

function renderQuiz(client: AxiosInstance, onSaved = vi.fn()) {
  return render(
    <ToastProvider>
      <ProfileQuiz client={client} open onClose={vi.fn()} onSaved={onSaved} />
    </ToastProvider>,
  );
}

describe('ProfileQuiz (#85 onboarding)', () => {
  it('PUTs the chosen profile with ranked sectors', async () => {
    const client = makeClient();
    const onSaved = vi.fn();
    renderQuiz(client, onSaved);
    // sector options load from /profile/sectors
    await screen.findByRole('option', { name: 'Bank' });

    await userEvent.click(screen.getByLabelText('Income'));      // goal
    await userEvent.selectOptions(screen.getByLabelText('Add a preferred sector'), 'Bank');
    await userEvent.click(screen.getByRole('button', { name: 'Add sector' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));

    await waitFor(() =>
      expect(client.put).toHaveBeenCalledWith(
        '/profile/me',
        expect.objectContaining({ goal: 'income', sector_prefs: ['Bank'] }),
      ),
    );
    expect(onSaved).toHaveBeenCalled();
  });
});
