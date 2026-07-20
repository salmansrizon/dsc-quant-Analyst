import { useEffect, useState } from 'react';
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

interface Props {
  client: AxiosInstance;
  open: boolean;
  onClose: () => void;
  onSaved?: (p: Profile) => void;
  initial?: Profile;
}

/**
 * Single-screen onboarding quiz (#85). A controlled modal: the host (Layout's
 * nudge, or Settings) owns `open`. Sectors preferences are rank-ordered — the
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
    <fieldset className="border-0 p-0 m-0">
      <legend className="text-sm font-medium text-gray-700 mb-1">{legend}</legend>
      <div className="flex gap-4">
        {opts.map(([v, label]) => (
          <label key={v} className="flex items-center gap-1 text-sm">
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
    <div
      role="dialog"
      aria-label="Investor profile"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6 space-y-4">
        <h2 className="text-lg font-bold text-gray-900">Build your investor profile</h2>
        <p className="text-sm text-gray-500">
          Tells us how to tailor fit scores and recommendations. Not financial advice.
        </p>

        {radioGroup('Goal', GOALS, goal, setGoal)}
        {radioGroup('Risk tolerance', RISKS, risk, setRisk)}
        {radioGroup('Time horizon', HORIZONS, horizon, setHorizon)}

        <div>
          <label htmlFor="sector-pick" className="text-sm font-medium text-gray-700">
            Add a preferred sector
          </label>
          <div className="flex gap-2 mt-1">
            <select
              id="sector-pick"
              aria-label="Add a preferred sector"
              value={pick}
              onChange={(e) => setPick(e.target.value)}
              className="flex-1 border rounded px-2 py-1 text-sm"
            >
              <option value="">Select…</option>
              {available.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={addSector}
              className="px-3 py-1 rounded bg-indigo-50 text-indigo-700 text-sm"
            >
              Add sector
            </button>
          </div>
          <ol className="mt-2 space-y-1">
            {sectors.map((s, i) => (
              <li key={s} className="flex items-center gap-2 text-sm">
                <span className="text-gray-400">{i + 1}.</span>
                <span className="flex-1">{s}</span>
                <button type="button" aria-label={`Move ${s} up`} onClick={() => move(i, -1)}>↑</button>
                <button type="button" aria-label={`Move ${s} down`} onClick={() => move(i, 1)}>↓</button>
                <button type="button" aria-label={`Remove ${s}`} onClick={() => removeSector(s)}>✕</button>
              </li>
            ))}
          </ol>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 rounded text-sm text-gray-600 hover:bg-gray-100"
          >
            Skip
          </button>
          <button
            type="button"
            onClick={save}
            disabled={saving}
            className="px-4 py-2 rounded bg-indigo-600 text-white text-sm disabled:opacity-50"
          >
            Save profile
          </button>
        </div>
      </div>
    </div>
  );
}
