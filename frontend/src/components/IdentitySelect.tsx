import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { ResearchIdentity } from '../api/client';

interface IdentitySelectProps {
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export default function IdentitySelect({ value, onChange, className }: IdentitySelectProps) {
  const [identities, setIdentities] = useState<ResearchIdentity[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get<ResearchIdentity[]>('/research/identities')
      .then(data => {
        setIdentities(Array.isArray(data) ? data : []);
        setLoaded(true);
      })
      .catch(() => setLoaded(true));
  }, []);

  const selectClass = className || 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500';

  return (
    <select value={value} onChange={e => onChange(e.target.value)} className={selectClass}>
      <option value="default">Default Identity</option>
      {loaded && identities.map(id => (
        <option key={id.id} value={id.id}>
          {id.sender_name} ({id.company_name})
        </option>
      ))}
    </select>
  );
}
