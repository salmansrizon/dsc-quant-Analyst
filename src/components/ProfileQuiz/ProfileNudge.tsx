import { useContext, useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { AuthContext } from '../../context/AuthContext';
import { errorMessage } from '../../api/errorMessage';
import { useToast } from '../../context/ToastContext';
import ProfileQuiz, { type Profile } from './ProfileQuiz';

/**
 * Global host for the #85 onboarding quiz. Mounted once in the Layout so every
 * authed page carries it. Fetches the user's profile; if it is still the neutral
 * default it auto-opens the quiz ONCE per user (localStorage guard) and shows a
 * dismissible "complete your profile" banner thereafter.
 */
export default function ProfileNudge({ client }: { client: AxiosInstance }) {
  const { user } = useContext(AuthContext);
  const toast = useToast();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (!user) return;
    client
      .get('/profile/me')
      .then((res) => {
        const p = res.data as Profile;
        setProfile(p);
        const seenKey = `profileQuizSeen:${user.id}`;
        if (p.is_default && !localStorage.getItem(seenKey)) {
          setOpen(true);
          localStorage.setItem(seenKey, '1');   // auto-open only once per user
        }
      })
      .catch((err) => toast.error(errorMessage(err, 'Failed to load profile')));
  }, [user, client, toast]);

  const needsProfile = profile?.is_default && !dismissed;

  return (
    <>
      {needsProfile && (
        <div className="bg-indigo-50 border border-indigo-100 rounded-md px-4 py-2 mb-4 flex items-center justify-between text-sm">
          <span className="text-indigo-800">
            Complete your investor profile to personalize fit scores and recommendations.
          </span>
          <span className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="font-medium text-indigo-700 hover:underline"
            >
              Set up now
            </button>
            <button
              type="button"
              aria-label="Dismiss profile reminder"
              onClick={() => setDismissed(true)}
              className="text-indigo-400 hover:text-indigo-600"
            >
              ✕
            </button>
          </span>
        </div>
      )}
      <ProfileQuiz
        client={client}
        open={open}
        initial={profile ?? undefined}
        onClose={() => setOpen(false)}
        onSaved={(p) => setProfile(p)}
      />
    </>
  );
}
