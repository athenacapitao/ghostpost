import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import IdentitySelect from '../components/IdentitySelect';

interface CompanyEntry {
  _id: number;
  company_name: string;
  contact_name: string;
  contact_email: string;
  contact_role: string;
  cc: string;
  country: string;
  industry: string;
}

let nextCompanyId = 1;
const makeCompany = (): CompanyEntry => ({
  _id: nextCompanyId++, company_name: '', contact_name: '', contact_email: '',
  contact_role: '', cc: '', country: '', industry: '',
});

export default function ResearchBatchNew() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [batchName, setBatchName] = useState('');
  const [companies, setCompanies] = useState<CompanyEntry[]>([makeCompany()]);
  const [jsonMode, setJsonMode] = useState(false);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState('');

  // Defaults
  const [defaults, setDefaults] = useState({
    goal: '',
    identity: 'default',
    language: 'pt-PT',
    email_tone: 'direct-value',
    auto_reply_mode: 'draft-for-approval',
  });

  const updateCompany = (index: number, field: keyof CompanyEntry, value: string) => {
    setCompanies(prev => prev.map((c, i) => i === index ? { ...c, [field]: value } : c));
  };

  const addCompany = () => setCompanies(prev => [...prev, makeCompany()]);

  const removeCompany = (index: number) => {
    if (companies.length <= 1) return;
    setCompanies(prev => prev.filter((_, i) => i !== index));
  };

  const parseJson = () => {
    setJsonError('');
    try {
      const parsed = JSON.parse(jsonText);
      if (!Array.isArray(parsed)) throw new Error('Expected a JSON array');
      const mapped = parsed.map((item: Record<string, string>) => ({
        _id: nextCompanyId++,
        company_name: item.company_name || item.company || '',
        contact_name: item.contact_name || '',
        contact_email: item.contact_email || item.email || '',
        contact_role: item.contact_role || item.role || '',
        cc: item.cc || item.cc_email || '',
        country: item.country || '',
        industry: item.industry || '',
      }));
      if (mapped.length === 0) throw new Error('Array is empty');
      setCompanies(mapped);
      setJsonMode(false);
    } catch (e: unknown) {
      setJsonError(e instanceof Error ? e.message : 'Invalid JSON');
    }
  };

  const submit = async () => {
    const validCompanies = jsonMode ? [] : companies.filter(c => c.company_name.trim());
    if (!batchName.trim() || validCompanies.length === 0) return;
    setSubmitting(true);
    setError('');
    try {
      const companiesPayload = validCompanies.map(c => {
        const entry: Record<string, string> = { company_name: c.company_name.trim() };
        if (c.contact_name.trim()) entry.contact_name = c.contact_name.trim();
        if (c.contact_email.trim()) entry.contact_email = c.contact_email.trim();
        if (c.contact_role.trim()) entry.contact_role = c.contact_role.trim();
        if (c.cc.trim()) entry.cc = c.cc.trim();
        if (c.country.trim()) entry.country = c.country.trim();
        if (c.industry.trim()) entry.industry = c.industry.trim();
        return entry;
      });

      const defaultsPayload: Record<string, string> = {};
      if (defaults.goal.trim()) defaultsPayload.goal = defaults.goal.trim();
      defaultsPayload.identity = defaults.identity;
      defaultsPayload.language = defaults.language;
      defaultsPayload.email_tone = defaults.email_tone;
      defaultsPayload.auto_reply_mode = defaults.auto_reply_mode;

      const data = await api.post<{ batch_id: number }>('/research/batch', {
        name: batchName.trim(),
        companies: companiesPayload,
        defaults: defaultsPayload,
      });
      navigate(`/research/batch/${data.batch_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to create batch');
    } finally {
      setSubmitting(false);
    }
  };

  const inputClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const selectClass = 'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500';
  const labelClass = 'text-xs text-gray-500 block mb-1';

  const validCount = companies.filter(c => c.company_name.trim()).length;

  return (
    <div className="max-w-3xl">
      <button onClick={() => navigate('/research')} className="text-sm text-gray-500 hover:text-gray-300 mb-4 flex items-center gap-1">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        Back to Research
      </button>

      <h1 className="text-xl font-semibold mb-6">New Research Batch</h1>

      <div className="space-y-6">
        {/* Batch Name */}
        <div>
          <label className={labelClass}>Batch Name *</label>
          <input type="text" value={batchName} onChange={e => setBatchName(e.target.value)} placeholder="e.g. Q1 Outreach — Tech Companies" className={inputClass} />
        </div>

        {/* Companies */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider">
              Companies {!jsonMode && `(${validCount})`}
            </h2>
            <button
              onClick={() => setJsonMode(!jsonMode)}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              {jsonMode ? 'Switch to Form' : 'Import JSON'}
            </button>
          </div>

          {jsonMode ? (
            <div className="space-y-3">
              <textarea
                value={jsonText}
                onChange={e => setJsonText(e.target.value)}
                rows={8}
                placeholder={'[\n  { "company_name": "Acme Corp", "contact_email": "john@acme.com" },\n  { "company_name": "Globex Inc" }\n]'}
                className={`${inputClass} resize-y font-mono text-xs`}
              />
              {jsonError && <p className="text-xs text-red-400">{jsonError}</p>}
              <button onClick={parseJson} className="px-4 py-2 bg-gray-800 text-gray-300 text-sm rounded-lg hover:bg-gray-700 border border-gray-700">
                Parse & Load
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {companies.map((company, i) => (
                <div key={company._id} className="bg-gray-900 border border-gray-800 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-gray-500">Company {i + 1}</span>
                    {companies.length > 1 && (
                      <button onClick={() => removeCompany(i)} className="text-xs text-red-400 hover:text-red-300">Remove</button>
                    )}
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    <input type="text" value={company.company_name} onChange={e => updateCompany(i, 'company_name', e.target.value)} placeholder="Company *" className={inputClass} />
                    <input type="text" value={company.contact_name} onChange={e => updateCompany(i, 'contact_name', e.target.value)} placeholder="Contact Name" className={inputClass} />
                    <input type="email" value={company.contact_email} onChange={e => updateCompany(i, 'contact_email', e.target.value)} placeholder="Contact Email" className={inputClass} />
                    <input type="text" value={company.contact_role} onChange={e => updateCompany(i, 'contact_role', e.target.value)} placeholder="Role" className={inputClass} />
                    <input type="text" value={company.cc} onChange={e => updateCompany(i, 'cc', e.target.value)} placeholder="CC (comma-separated)" className={inputClass} />
                    <input type="text" value={company.country} onChange={e => updateCompany(i, 'country', e.target.value)} placeholder="Country" className={inputClass} />
                    <input type="text" value={company.industry} onChange={e => updateCompany(i, 'industry', e.target.value)} placeholder="Industry" className={inputClass} />
                  </div>
                </div>
              ))}
              <button onClick={addCompany} className="w-full py-2 border border-dashed border-gray-700 rounded-lg text-sm text-gray-500 hover:text-gray-300 hover:border-gray-600 transition-colors">
                + Add Company
              </button>
            </div>
          )}
        </div>

        {/* Defaults */}
        <div>
          <h2 className="text-sm font-medium text-gray-400 uppercase tracking-wider mb-4">Defaults (all companies)</h2>
          <div className="space-y-4">
            <div>
              <label className={labelClass}>Goal</label>
              <textarea value={defaults.goal} onChange={e => setDefaults(p => ({ ...p, goal: e.target.value }))} rows={2} placeholder="Default goal for all companies" className={`${inputClass} resize-y`} />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <label className={labelClass}>Identity</label>
                <IdentitySelect value={defaults.identity} onChange={v => setDefaults(p => ({ ...p, identity: v }))} className={selectClass} />
              </div>
              <div>
                <label className={labelClass}>Language</label>
                <select value={defaults.language} onChange={e => setDefaults(p => ({ ...p, language: e.target.value }))} className={selectClass}>
                  <option value="pt-PT">pt-PT</option>
                  <option value="en">English</option>
                  <option value="auto">Auto</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>Tone</label>
                <select value={defaults.email_tone} onChange={e => setDefaults(p => ({ ...p, email_tone: e.target.value }))} className={selectClass}>
                  <option value="direct-value">Direct Value</option>
                  <option value="consultative">Consultative</option>
                  <option value="relationship-first">Relationship</option>
                  <option value="challenger-sale">Challenger</option>
                </select>
              </div>
              <div>
                <label className={labelClass}>After Send</label>
                <select value={defaults.auto_reply_mode} onChange={e => setDefaults(p => ({ ...p, auto_reply_mode: e.target.value }))} className={selectClass}>
                  <option value="draft-for-approval">Save Draft</option>
                  <option value="autonomous">Auto Send</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <button
          onClick={submit}
          disabled={submitting || !batchName.trim() || validCount === 0}
          className="w-full px-6 py-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? 'Creating Batch...' : `Start Batch (${validCount} companies)`}
        </button>
      </div>
    </div>
  );
}
