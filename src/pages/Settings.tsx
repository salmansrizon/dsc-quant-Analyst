import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { Bell } from 'lucide-react';
import { errorMessage } from '../api/errorMessage';
import { useToast } from '../context/ToastContext';

// The four channels the #78 endpoint understands, each with the payload field
// that carries its delivery target.
const CHANNELS = [
  { key: 'email', label: 'Email', field: 'email', placeholder: 'you@example.com' },
  { key: 'telegram', label: 'Telegram', field: 'telegram_chat_id', placeholder: 'chat id' },
  { key: 'whatsapp', label: 'WhatsApp', field: 'whatsapp_number', placeholder: '+8801…' },
  { key: 'web_push', label: 'Web Push', field: 'web_push_subscription', placeholder: 'subscription token' },
] as const;

interface Prefs {
  channels_enabled: string[];
  email: string | null;
  telegram_chat_id: string | null;
  whatsapp_number: string | null;
  web_push_subscription: string | null;
}

const EMPTY: Prefs = {
  channels_enabled: [],
  email: null,
  telegram_chat_id: null,
  whatsapp_number: null,
  web_push_subscription: null,
};

/**
 * Notification preferences (PRD-13/#82), wiring the #78 append-only endpoint:
 * GET/PUT /settings/notifications. Enable a channel and give it a target; the
 * alert sweep (#80) fans crossings out to every enabled channel.
 */
export default function Settings({ client }: { client: AxiosInstance }) {
  const toast = useToast();
  const [prefs, setPrefs] = useState<Prefs>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    client
      .get('/settings/notifications')
      .then((res) => setPrefs({ ...EMPTY, ...res.data }))
      .catch((err) => toast.error(errorMessage(err, 'Failed to load settings')))
      .finally(() => setLoading(false));
  }, [client, toast]);

  const enabled = (key: string) => prefs.channels_enabled.includes(key);

  const toggle = (key: string) =>
    setPrefs((p) => ({
      ...p,
      channels_enabled: enabled(key)
        ? p.channels_enabled.filter((c) => c !== key)
        : [...p.channels_enabled, key],
    }));

  const setField = (field: string, value: string) =>
    setPrefs((p) => ({ ...p, [field]: value }));

  const save = async () => {
    setSaving(true);
    try {
      const res = await client.put('/settings/notifications', prefs);
      setPrefs({ ...EMPTY, ...res.data });
      toast.success('Notification settings saved');
    } catch (err) {
      toast.error(errorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-center p-6">Loading settings…</div>;

  return (
    <div className="p-6 gap-6 flex flex-col" style={{ maxWidth: 640, margin: '0 auto' }}>
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <Bell size={24} /> Notification Settings
      </h1>
      <p className="text-secondary text-sm">
        Choose how price-alert crossings reach you. Each channel needs a target.
      </p>

      <div className="flex flex-col gap-4">
        {CHANNELS.map((ch) => (
          <div key={ch.key} className="card flex flex-col gap-3">
            <label className="flex items-center gap-3 font-semibold">
              <input
                type="checkbox"
                checked={enabled(ch.key)}
                onChange={() => toggle(ch.key)}
                aria-label={`Enable ${ch.label}`}
              />
              {ch.label}
            </label>
            <input
              type="text"
              value={(prefs[ch.field] as string) ?? ''}
              onChange={(e) => setField(ch.field, e.target.value)}
              placeholder={ch.placeholder}
              disabled={!enabled(ch.key)}
              aria-label={`${ch.label} target`}
              className="border p-2 rounded w-full"
            />
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={save}
        disabled={saving}
        className="btn-primary"
        style={{ alignSelf: 'flex-start' }}
      >
        {saving ? 'Saving…' : 'Save Settings'}
      </button>
    </div>
  );
}
