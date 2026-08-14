import { useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import type { AxiosInstance } from 'axios';
import { errorMessage } from '../../api/errorMessage';
import { useToast } from '../../context/ToastContext';

// The #85 investor profile: 4 dimensions the #88 fit engine scores against.
// Every option here maps to a stored enum (backend/models.py InvestorProfile).
export type Goal = 'income' | 'growth' | 'preservation';
export type Risk = 'low' | 'med' | 'high';
export type Horizon = 'short' | 'medium' | 'long';

export interface Profile {
  goal: Goal;
  risk: Risk;
  horizon: Horizon;
  sector_prefs: string[];
  is_default?: boolean;
}

const GOALS: [Goal, string][] = [
  ['income', 'Income'], ['growth', 'Growth'], ['preservation', 'Preservation'],
];
const RISKS: [Risk, string][] = [['low', 'Low'], ['med', 'Medium'], ['high', 'High']];
const HORIZONS: [Horizon, string][] = [
  ['short', 'Short'], ['medium', 'Medium'], ['long', 'Long'],
];

// The neutral cold-start defaults — mirror backend profile_service.NEUTRAL so an
// unset user opens the quiz pre-filled with the same object the engine assumed.
const DEFAULTS: Profile = {
  goal: 'growth', risk: 'med', horizon: 'medium', sector_prefs: [], is_default: true,
};

// This project ships no Tailwind (see index.css — hand-rolled semantic classes +
// CSS vars). So the modal chrome is styled inline against those vars; the buttons
// reuse the real .btn-primary/.btn-secondary classes.
const overlay: CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 50, display: 'flex',
  alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.4)',
};
const panel: CSSProperties = {
  background: 'var(--bg-secondary)', color: 'var(--text-primary)',
  border: '1px solid var(--border-color)', borderRadius: 8,
  width: '100%', maxWidth: 440, padding: 24,
  display: 'flex', flexDirection: 'column', gap: 16,
};

interface Props {
  client: AxiosInstance;
  open: boolean;
  onClose: () => void;
  onSaved?: (p: Profile) => void;
  initial?: Profile;
}

/**
 * Single-screen onboarding quiz (#85). A controlled modal: the host (Layout's
 * nudge, or Settings) owns `open`. Sector preferences are rank-ordered — the
 * order the user adds them in is the order #88 derives weights from ([0] = top).
 */
export default function ProfileQuiz({ client, open, onClose, onSaved, initial }: Props) {
  const toast = useToast();
  const base = initial ?? DEFAULTS;
  const [goal, setGoal] = useState<Goal>(base.goal);
  const [risk, setRisk] = useState<Risk>(base.risk);
  const [horizon, setHorizon] = useState<Horizon>(base.horizon);
  const [sectors, setSectors] = useState<string[]>(base.sector_prefs);
  const [allSectors, setAllSectors] = useState<string[]>([]);
  const [pick, setPick] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    client
      .get('/profile/sectors')
      .then((res) => setAllSectors(res.data as string[]))
      .catch((err) => toast.error(errorMessage(err, 'Failed to load sectors')));
  }, [open, client, toast]);

  if (!open) return null;

  const available = allSectors.filter((s) => !sectors.includes(s));

  const addSector = () => {
    if (pick && !sectors.includes(pick)) setSectors([...sectors, pick]);
    setPick('');
  };
  const removeSector = (s: string) => setSectors(sectors.filter((x) => x !== s));
  const move = (i: number, delta: number) => {
    const j = i + delta;
    if (j < 0 || j >= sectors.length) return;
    const next = [...sectors];
    [next[i], next[j]] = [next[j], next[i]];
    setSectors(next);
  };

  const save = async () => {
    setSaving(true);
    try {
      const { data } = await client.put('/profile/me', {
        goal, risk, horizon, sector_prefs: sectors,
      });
      toast.success('Profile saved');
      onSaved?.(data as Profile);
      onClose();
    } catch (err) {
      toast.error(errorMessage(err, 'Failed to save profile'));
    } finally {
      setSaving(false);
    }
  };

  const radioGroup = <T extends string>(
    legend: string, opts: [T, string][], value: T, set: (v: T) => void,
  ) => (
    <fieldset style={{ border: 0, padding: 0, margin: 0 }}>
      <legend style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>{legend}</legend>
      <div style={{ display: 'flex', gap: 16 }}>
        {opts.map(([v, label]) => (
          <label key={v} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 14 }}>
            <input
              type="radio"
              name={legend}
              checked={value === v}
              onChange={() => set(v)}
            />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );

  return (
    <div role="dialog" aria-label="Investor profile" style={overlay}>
      <div style={panel}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Build your investor profile</h2>
        <p className="text-secondary" style={{ fontSize: 14, margin: 0 }}>
          Tells us how to tailor fit scores and recommendations. Not financial advice.
        </p>

        {radioGroup('Goal', GOALS, goal, setGoal)}
        {radioGroup('Risk tolerance', RISKS, risk, setRisk)}
        {radioGroup('Time horizon', HORIZONS, horizon, setHorizon)}

        <div>
          <label htmlFor="sector-pick" style={{ fontSize: 14, fontWeight: 600 }}>
            Add a preferred sector
          </label>
          <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
            <select
              id="sector-pick"
              aria-label="Add a preferred sector"
              value={pick}
              onChange={(e) => setPick(e.target.value)}
              style={{
                flex: 1, border: '1px solid var(--border-color)', borderRadius: 4,
                padding: '4px 8px', fontSize: 14, background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
              }}
            >
              <option value="">Select…</option>
              {available.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button type="button" onClick={addSector} className="btn-secondary">
              Add sector
            </button>
          </div>
          <ol style={{ marginTop: 8, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 4 }}>
            {sectors.map((s, i) => (
              <li key={s} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
                <span className="text-secondary">{i + 1}.</span>
                <span style={{ flex: 1 }}>{s}</span>
                <button type="button" aria-label={`Move ${s} up`} onClick={() => move(i, -1)}>↑</button>
                <button type="button" aria-label={`Move ${s} down`} onClick={() => move(i, 1)}>↓</button>
                <button type="button" aria-label={`Remove ${s}`} onClick={() => removeSector(s)}>✕</button>
              </li>
            ))}
          </ol>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, paddingTop: 8 }}>
          <button type="button" onClick={onClose} className="btn-secondary">Skip</button>
          <button type="button" onClick={save} disabled={saving} className="btn-primary">
            {saving ? 'Saving…' : 'Save profile'}
          </button>
        </div>
      </div>
    </div>
  );
}
