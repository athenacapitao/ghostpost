import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

interface Identity {
  identity_id: string;
  company_name: string;
  sender_name: string;
  sender_title: string;
  sender_email: string;
  website?: string;
  industry?: string;
  tagline?: string;
  sender_phone?: string;
  sender_linkedin?: string;
  calendar_link?: string;
  body?: string;
}

const emptyForm: Identity = {
  identity_id: '',
  company_name: '',
  sender_name: '',
  sender_title: '',
  sender_email: '',
  website: '',
  industry: '',
  tagline: '',
  sender_phone: '',
  sender_linkedin: '',
  calendar_link: '',
  body: '',
};

const BODY_PLACEHOLDER = `## Overview
Brief company description...

## Services
- Service 1
- Service 2

## Differentiators
What makes us unique...

## Clients
Notable clients or sectors...

## Team
Key team highlights...

## Signature
Professional sign-off template...`;

export default function Identities() {
  const [identities, setIdentities] = useState<{ id: string; company_name: string; sender_name: string; sender_email: string }[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [form, setForm] = useState<Identity>({ ...emptyForm });
  const [isNew, setIsNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadList = useCallback(async () => {
    try {
      const data = await api.get<{ id: string; company_name: string; sender_name: string; sender_email: string }[]>('/research/identities');
      setIdentities(data);
    } catch {
      setError('Failed to load identities');
    }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  const loadIdentity = async (id: string) => {
    setError('');
    setSuccess('');
    setIsNew(false);
    try {
      const data = await api.get<Identity>(`/research/identities/${id}`);
      setForm(data);
      setSelected(id);
    } catch {
      setError(`Failed to load identity: ${id}`);
    }
  };

  const startNew = () => {
    setForm({ ...emptyForm });
    setSelected(null);
    setIsNew(true);
    setError('');
    setSuccess('');
  };

  const save = async () => {
    if (!form.identity_id.trim() || !form.company_name.trim() || !form.sender_name.trim() || !form.sender_title.trim() || !form.sender_email.trim()) {
      setError('Please fill in all required fields');
      return;
    }
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      if (isNew) {
        await api.post('/research/identities', form);
        setSuccess('Identity created');
      } else {
        await api.put(`/research/identities/${selected}`, form);
        setSuccess('Identity updated');
      }
      await loadList();
      setSelected(form.identity_id);
      setIsNew(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!selected || !confirm(`Delete identity "${selected}"?`)) return;
    setDeleting(true);
    setError('');
    try {
      await api.delete(`/research/identities/${selected}`);
      setSuccess('Identity deleted');
      setSelected(null);
      setForm({ ...emptyForm });
      setIsNew(false);
      await loadList();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete');
    } finally {
      setDeleting(false);
    }
  };

  const set = (field: keyof Identity) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(prev => ({ ...prev, [field]: e.target.value }));

  const inputClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const labelClass = 'text-xs text-gray-500 block mb-1';

  return (
    <div className="flex gap-6 min-h-[calc(100vh-8rem)]">
      {/* Left: Identity list */}
      <div className="w-72 shrink-0">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold">Identities</h1>
          <button onClick={startNew} className="px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded hover:bg-blue-500 transition-colors">
            + New
          </button>
        </div>
        <div className="space-y-2">
          {identities.map(ident => (
            <button
              key={ident.id}
              onClick={() => loadIdentity(ident.id)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                selected === ident.id
                  ? 'border-blue-500 bg-gray-800'
                  : 'border-gray-800 bg-gray-900 hover:border-gray-700'
              }`}
            >
              <div className="text-sm font-medium text-gray-200">{ident.company_name}</div>
              <div className="text-xs text-gray-500">{ident.sender_name}</div>
              <div className="text-xs text-gray-600">{ident.sender_email}</div>
            </button>
          ))}
          {identities.length === 0 && (
            <p className="text-sm text-gray-600 text-center py-8">No identities yet</p>
          )}
        </div>
      </div>

      {/* Right: Form */}
      <div className="flex-1 max-w-2xl">
        {(isNew || selected) ? (
          <div className="space-y-6">
            <h2 className="text-lg font-medium">{isNew ? 'New Identity' : `Edit: ${selected}`}</h2>

            {/* Company Info */}
            <div>
              <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Company Info</h3>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Identity ID *</label>
                    <input type="text" value={form.identity_id} onChange={set('identity_id')} placeholder="my-company" className={inputClass} disabled={!isNew && !!selected} />
                    {isNew && <p className="text-xs text-gray-600 mt-1">Slug used as filename (e.g. "acme")</p>}
                  </div>
                  <div>
                    <label className={labelClass}>Company Name *</label>
                    <input type="text" value={form.company_name} onChange={set('company_name')} placeholder="Acme Corp" className={inputClass} />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className={labelClass}>Website</label>
                    <input type="text" value={form.website || ''} onChange={set('website')} placeholder="https://acme.com" className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>Industry</label>
                    <input type="text" value={form.industry || ''} onChange={set('industry')} placeholder="Technology" className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>Tagline</label>
                    <input type="text" value={form.tagline || ''} onChange={set('tagline')} placeholder="We build great things" className={inputClass} />
                  </div>
                </div>
              </div>
            </div>

            {/* Sender Info */}
            <div>
              <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Sender Info</h3>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Name *</label>
                    <input type="text" value={form.sender_name} onChange={set('sender_name')} placeholder="John Doe" className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>Title *</label>
                    <input type="text" value={form.sender_title} onChange={set('sender_title')} placeholder="CEO" className={inputClass} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Email *</label>
                    <input type="email" value={form.sender_email} onChange={set('sender_email')} placeholder="john@acme.com" className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>Phone</label>
                    <input type="text" value={form.sender_phone || ''} onChange={set('sender_phone')} placeholder="+351 912 345 678" className={inputClass} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>LinkedIn</label>
                    <input type="text" value={form.sender_linkedin || ''} onChange={set('sender_linkedin')} placeholder="https://linkedin.com/in/johndoe" className={inputClass} />
                  </div>
                  <div>
                    <label className={labelClass}>Calendar Link</label>
                    <input type="text" value={form.calendar_link || ''} onChange={set('calendar_link')} placeholder="https://cal.com/johndoe" className={inputClass} />
                  </div>
                </div>
              </div>
            </div>

            {/* Content */}
            <div>
              <h3 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-3">Content</h3>
              <label className={labelClass}>Body (Markdown)</label>
              <textarea
                value={form.body || ''}
                onChange={set('body')}
                rows={12}
                placeholder={BODY_PLACEHOLDER}
                className={`${inputClass} resize-y font-mono text-xs`}
              />
            </div>

            {error && <p className="text-sm text-red-400">{error}</p>}
            {success && <p className="text-sm text-green-400">{success}</p>}

            <div className="flex gap-3">
              <button
                onClick={save}
                disabled={saving}
                className="px-6 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 disabled:opacity-50 transition-colors"
              >
                {saving ? 'Saving...' : isNew ? 'Create Identity' : 'Save Changes'}
              </button>
              {!isNew && selected && (
                <button
                  onClick={remove}
                  disabled={deleting}
                  className="px-6 py-2.5 bg-red-900/50 text-red-400 text-sm font-medium rounded-lg hover:bg-red-900/80 disabled:opacity-50 transition-colors"
                >
                  {deleting ? 'Deleting...' : 'Delete'}
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-600">
            <p>Select an identity or create a new one</p>
          </div>
        )}
      </div>
    </div>
  );
}
