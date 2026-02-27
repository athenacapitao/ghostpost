import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, uploadBatchCSV } from '../api/client';
import type { BatchImportPreview, BatchImportResult, ResearchIdentity } from '../api/client';

const CSV_EXAMPLE = `company,contact_name,email,role,cc,goal,industry,country
Acme Corp,John Silva,john@acme.pt,CEO,manager@acme.pt,Partnership outreach,Tech,PT
Beta Lda,Sara Costa,sara@beta.io,CTO,,Tech collaboration,SaaS,PT`;

type Tab = 'paste' | 'upload';

export default function ResearchImport() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<Tab>('paste');
  const [csvText, setCsvText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [batchName, setBatchName] = useState('');
  const [identity, setIdentity] = useState('default');
  const [language, setLanguage] = useState('pt-PT');
  const [goalDefault, setGoalDefault] = useState('');

  const [identities, setIdentities] = useState<ResearchIdentity[]>([]);
  const [preview, setPreview] = useState<BatchImportPreview | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<ResearchIdentity[]>('/research/identities').then(setIdentities).catch(() => {});
  }, []);

  const buildDefaults = () => {
    const d: Record<string, string> = {};
    if (identity && identity !== 'default') d.identity = identity;
    if (language) d.language = language;
    if (goalDefault) d.goal = goalDefault;
    return Object.keys(d).length > 0 ? JSON.stringify(d) : undefined;
  };

  const handlePreview = async () => {
    setError('');
    setPreview(null);
    setLoading(true);
    try {
      const result = await uploadBatchCSV({
        file: tab === 'upload' ? file || undefined : undefined,
        csvText: tab === 'paste' ? csvText : undefined,
        defaults: buildDefaults(),
        name: batchName || undefined,
        dryRun: true,
      }) as BatchImportPreview;
      setPreview(result);
    } catch (e: any) {
      setError(e.message || 'Preview failed');
    } finally {
      setLoading(false);
    }
  };

  const handleStartBatch = async () => {
    if (!preview) return;
    setError('');
    setStarting(true);
    try {
      const defaults = buildDefaults();
      const result = await api.post<BatchImportResult>('/research/batch', {
        name: batchName || 'CSV Import',
        companies: preview.companies,
        defaults: defaults ? JSON.parse(defaults) : undefined,
      });
      navigate(`/research/batch/${result.batch_id}`);
    } catch (e: any) {
      setError(e.message || 'Failed to start batch');
    } finally {
      setStarting(false);
    }
  };

  const canPreview = tab === 'paste' ? csvText.trim().length > 0 : !!file;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Batch Import</h1>
        <button
          onClick={() => navigate('/research')}
          className="text-sm text-gray-400 hover:text-white"
        >
          Back to Research
        </button>
      </div>

      {/* Example format */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <p className="text-sm text-gray-400 mb-2">Example CSV format:</p>
        <pre className="text-xs text-gray-300 font-mono whitespace-pre overflow-x-auto">{CSV_EXAMPLE}</pre>
        <p className="text-xs text-gray-500 mt-2">
          Columns: company, contact_name, email, role, goal, industry, country, cc, notes.
          Headers are auto-detected (EN/PT aliases supported). Only "company" is required.
        </p>
      </div>

      {/* Tab toggle */}
      <div className="flex gap-1 bg-gray-900 rounded-lg p-1 w-fit">
        {(['paste', 'upload'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => { setTab(t); setPreview(null); setError(''); }}
            className={`px-4 py-1.5 rounded-md text-sm transition-colors ${
              tab === t ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'
            }`}
          >
            {t === 'paste' ? 'Paste CSV' : 'Upload File'}
          </button>
        ))}
      </div>

      {/* Input area */}
      {tab === 'paste' ? (
        <textarea
          value={csvText}
          onChange={e => { setCsvText(e.target.value); setPreview(null); }}
          placeholder={CSV_EXAMPLE}
          rows={10}
          className="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm font-mono text-gray-200 placeholder:text-gray-600 focus:outline-none focus:border-gray-500 resize-y"
        />
      ) : (
        <div
          onClick={() => fileRef.current?.click()}
          className="w-full bg-gray-900 border border-gray-700 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-gray-500 transition-colors"
        >
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={e => { setFile(e.target.files?.[0] || null); setPreview(null); }}
          />
          {file ? (
            <p className="text-sm text-gray-200">{file.name} ({(file.size / 1024).toFixed(1)} KB)</p>
          ) : (
            <p className="text-sm text-gray-400">Click to select a .csv file</p>
          )}
        </div>
      )}

      {/* Batch defaults */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <p className="text-sm font-medium text-gray-300">Batch Defaults</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Batch Name</label>
            <input
              value={batchName}
              onChange={e => setBatchName(e.target.value)}
              placeholder="CSV Import"
              className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Identity</label>
            <select
              value={identity}
              onChange={e => setIdentity(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
            >
              <option value="default">default</option>
              {identities.map(id => (
                <option key={id.id} value={id.id}>{id.id} ({id.company_name})</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Language</label>
            <select
              value={language}
              onChange={e => setLanguage(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
            >
              <option value="pt-PT">pt-PT</option>
              <option value="en">en</option>
              <option value="es">es</option>
              <option value="fr">fr</option>
              <option value="auto">auto</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Default Goal</label>
            <input
              value={goalDefault}
              onChange={e => setGoalDefault(e.target.value)}
              placeholder="Fallback goal for rows without one"
              className="w-full bg-gray-800 border border-gray-700 rounded px-2.5 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-gray-500"
            />
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3">
        <button
          onClick={handlePreview}
          disabled={!canPreview || loading}
          className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:opacity-40 disabled:cursor-not-allowed text-sm rounded-lg transition-colors"
        >
          {loading ? 'Parsing...' : 'Preview'}
        </button>
        <button
          onClick={handleStartBatch}
          disabled={!preview || preview.companies.length === 0 || starting}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-sm rounded-lg transition-colors"
        >
          {starting ? 'Starting...' : `Start Batch${preview ? ` (${preview.total})` : ''}`}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/30 border border-red-800 rounded-lg p-3 text-sm text-red-300">{error}</div>
      )}

      {/* Preview results */}
      {preview && (
        <div className="space-y-3">
          {preview.warnings.length > 0 && (
            <div className="bg-yellow-900/20 border border-yellow-800/50 rounded-lg p-3">
              <p className="text-xs font-medium text-yellow-400 mb-1">Warnings</p>
              {preview.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-300/80">- {w}</p>
              ))}
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800 text-left text-xs text-gray-500">
                  <th className="py-2 pr-3">#</th>
                  <th className="py-2 pr-3">Company</th>
                  <th className="py-2 pr-3">Contact</th>
                  <th className="py-2 pr-3">Email</th>
                  <th className="py-2 pr-3">Role</th>
                  <th className="py-2 pr-3">CC</th>
                  <th className="py-2 pr-3">Goal</th>
                  <th className="py-2 pr-3">Industry</th>
                  <th className="py-2 pr-3">Country</th>
                </tr>
              </thead>
              <tbody>
                {preview.companies.map((c, i) => (
                  <tr key={i} className="border-b border-gray-800/50 text-gray-300">
                    <td className="py-1.5 pr-3 text-gray-500">{i + 1}</td>
                    <td className="py-1.5 pr-3 font-medium text-gray-200">{c.company_name}</td>
                    <td className="py-1.5 pr-3">{c.contact_name || '-'}</td>
                    <td className="py-1.5 pr-3 text-gray-400">{c.contact_email || '-'}</td>
                    <td className="py-1.5 pr-3">{c.contact_role || '-'}</td>
                    <td className="py-1.5 pr-3 text-gray-400">{c.cc || '-'}</td>
                    <td className="py-1.5 pr-3">{c.goal || '-'}</td>
                    <td className="py-1.5 pr-3">{c.industry || '-'}</td>
                    <td className="py-1.5 pr-3">{c.country || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="text-xs text-gray-500">
            Column mapping: {Object.entries(preview.column_mapping).map(([k, v]) => `${k} -> ${v}`).join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}
