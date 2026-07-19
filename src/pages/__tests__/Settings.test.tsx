import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import Settings from '../Settings';
import { ToastProvider } from '../../context/ToastContext';

function makeClient(prefs: Record<string, unknown>): AxiosInstance {
  return {
    get: vi.fn().mockResolvedValue({ data: prefs }),
    put: vi.fn().mockImplementation((_url, body) => Promise.resolve({ data: body })),
  } as unknown as AxiosInstance;
}

function renderSettings(client: AxiosInstance) {
  return render(
    <ToastProvider>
      <Settings client={client} />
    </ToastProvider>,
  );
}

describe('Settings (notification prefs, #78)', () => {
  it('loads current prefs and reflects enabled channels', async () => {
    const client = makeClient({ channels_enabled: ['email'], email: 'me@x.com' });
    renderSettings(client);
    const emailToggle = await screen.findByLabelText('Enable Email');
    expect(emailToggle).toBeChecked();
    expect(screen.getByLabelText('Telegram target')).toBeDisabled();
  });

  it('PUTs the edited prefs including the newly enabled channel', async () => {
    const client = makeClient({ channels_enabled: [], email: null });
    renderSettings(client);
    await screen.findByLabelText('Enable Telegram');
    await userEvent.click(screen.getByLabelText('Enable Telegram'));
    await userEvent.type(screen.getByLabelText('Telegram target'), '12345');
    await userEvent.click(screen.getByRole('button', { name: 'Save Settings' }));
    expect(client.put).toHaveBeenCalledWith(
      '/settings/notifications',
      expect.objectContaining({ channels_enabled: ['telegram'], telegram_chat_id: '12345' }),
    );
    expect(await screen.findByText('Notification settings saved')).toBeInTheDocument();
  });
});
