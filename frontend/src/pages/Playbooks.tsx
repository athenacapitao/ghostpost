import { useEffect, useState, useCallback } from 'react';
import { api } from '../api/client';

// ─── Types ────────────────────────────────────────────────────────────────────

interface PlaybookMeta {
  name: string;
  title: string;
  path: string;
}

type ViewMode = 'idle' | 'view' | 'new';

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Extract a display title from the first non-empty line of markdown content. */
function extractTitle(content: string): string {
  const first = content
    .split('\n')
    .map(l => l.trim())
    .find(l => l.length > 0);
  if (!first) return 'Untitled';
  // Strip leading markdown heading markers
  return first.replace(/^#+\s*/, '');
}

/** Validate a playbook name — alphanumeric characters and hyphens only. */
function isValidName(name: string): boolean {
  return /^[a-z0-9][a-z0-9-]*$/.test(name);
}

/** Fetch plain-text playbook content directly (the api client assumes JSON). */
async function fetchPlaybookContent(name: string): Promise<string> {
  const token = localStorage.getItem('ghostpost_token');
  const headers: Record<string, string> = {};
  if (token) headers['X-API-Key'] = token;

  const res = await fetch(`/api/playbooks/${encodeURIComponent(name)}`, {
    credentials: 'include',
    headers,
  });

  if (res.status === 401) {
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(text || 'Failed to load playbook');
  }

  return res.text();
}

// ─── Sub-components ───────────────────────────────────────────────────────────

interface PlaybookListItemProps {
  playbook: PlaybookMeta;
  isSelected: boolean;
  onSelect: (name: string) => void;
}

function PlaybookListItem({ playbook, isSelected, onSelect }: PlaybookListItemProps) {
  return (
    <button
      onClick={() => onSelect(playbook.name)}
      aria-pressed={isSelected}
      aria-label={`Open playbook: ${playbook.title}`}
      className={`w-full text-left px-3 py-2.5 rounded-md transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500 ${
        isSelected
          ? 'bg-gray-800 text-white'
          : 'text-gray-300 hover:bg-gray-800/60 hover:text-white'
      }`}
    >
      <span className="block text-sm font-medium truncate">{playbook.title}</span>
      <span className="block text-xs text-gray-500 mt-0.5 truncate">{playbook.name}</span>
    </button>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Playbooks() {
  // List state
  const [playbooks, setPlaybooks] = useState<PlaybookMeta[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState('');

  // Selection / editor state
  const [mode, setMode] = useState<ViewMode>('idle');
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [contentLoading, setContentLoading] = useState(false);
  const [contentError, setContentError] = useState('');

  // Save / delete state
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');

  // New playbook form state
  const [newName, setNewName] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newNameError, setNewNameError] = useState('');

  // ── Data fetching ────────────────────────────────────────────────────────

  const loadList = useCallback(() => {
    setListLoading(true);
    setListError('');
    api
      .get<PlaybookMeta[]>('/playbooks')
      .then(setPlaybooks)
      .catch((e: unknown) => {
        setListError(e instanceof Error ? e.message : 'Failed to load playbooks');
      })
      .finally(() => setListLoading(false));
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const loadContent = useCallback(async (name: string) => {
    setContentLoading(true);
    setContentError('');
    setActionError('');
    setActionSuccess('');
    try {
      const text = await fetchPlaybookContent(name);
      setContent(text);
    } catch (e: unknown) {
      setContentError(e instanceof Error ? e.message : 'Failed to load content');
    } finally {
      setContentLoading(false);
    }
  }, []);

  // ── Selection ────────────────────────────────────────────────────────────

  const handleSelect = useCallback(
    (name: string) => {
      if (selectedName === name && mode === 'view') return;
      setMode('view');
      setSelectedName(name);
      loadContent(name);
      // Reset new-form state when switching to view
      setNewName('');
      setNewContent('');
      setNewNameError('');
    },
    [selectedName, mode, loadContent],
  );

  const handleNewClick = () => {
    setMode('new');
    setSelectedName(null);
    setContent('');
    setNewName('');
    setNewContent('');
    setNewNameError('');
    setActionError('');
    setActionSuccess('');
  };

  // ── Save (create or update) ───────────────────────────────────────────────

  const handleSave = async () => {
    setActionError('');
    setActionSuccess('');
    setSaving(true);
    try {
      await api.put<{ message: string }>(`/playbooks/${encodeURIComponent(selectedName!)}`, {
        content,
      });
      setActionSuccess('Playbook saved.');
      // Refresh list in case title changed
      loadList();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Failed to save playbook');
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    setNewNameError('');
    setActionError('');
    setActionSuccess('');

    const trimmedName = newName.trim().toLowerCase();
    if (!trimmedName) {
      setNewNameError('Name is required.');
      return;
    }
    if (!isValidName(trimmedName)) {
      setNewNameError('Use lowercase letters, numbers, and hyphens only. Must start with a letter or number.');
      return;
    }
    if (!newContent.trim()) {
      setActionError('Content cannot be empty.');
      return;
    }

    setSaving(true);
    try {
      await api.post<{ message: string }>(`/playbooks?name=${encodeURIComponent(trimmedName)}`, {
        content: newContent,
      });
      setActionSuccess(`Playbook "${trimmedName}" created.`);
      loadList();
      // Switch to view mode for the new playbook
      setMode('view');
      setSelectedName(trimmedName);
      setContent(newContent);
      setNewName('');
      setNewContent('');
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Failed to create playbook');
    } finally {
      setSaving(false);
    }
  };

  // ── Delete ────────────────────────────────────────────────────────────────

  const handleDelete = async () => {
    if (!selectedName) return;
    const confirmed = window.confirm(`Delete playbook "${selectedName}"? This cannot be undone.`);
    if (!confirmed) return;

    setDeleting(true);
    setActionError('');
    setActionSuccess('');
    try {
      await api.delete<{ message: string }>(`/playbooks/${encodeURIComponent(selectedName)}`);
      setPlaybooks(prev => prev.filter(p => p.name !== selectedName));
      setMode('idle');
      setSelectedName(null);
      setContent('');
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : 'Failed to delete playbook');
    } finally {
      setDeleting(false);
    }
  };

  // ── Shared class strings ──────────────────────────────────────────────────

  const inputClass =
    'w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500';

  const btnPrimary =
    'px-4 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-blue-400 transition-colors';

  const btnDanger =
    'px-4 py-1.5 bg-red-700 text-white text-sm rounded hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-red-400 transition-colors';

  const btnSecondary =
    'px-4 py-1.5 bg-gray-800 text-gray-200 text-sm rounded hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-gray-500 border border-gray-700 transition-colors';

  // ── Render ────────────────────────────────────────────────────────────────

  const editorTitle = mode === 'view' && content ? extractTitle(content) : null;

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      {/* ── Left panel: playbook list ────────────────────────────────────── */}
      <aside
        className="w-64 shrink-0 flex flex-col gap-2"
        aria-label="Playbooks list"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <h1 className="text-base font-bold text-gray-100">Playbooks</h1>
          <button
            onClick={handleNewClick}
            aria-label="Create new playbook"
            className="text-xs px-2.5 py-1 bg-blue-600 text-white rounded hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400 transition-colors"
          >
            + New
          </button>
        </div>

        {/* List body */}
        <div className="flex-1 overflow-y-auto rounded-lg border border-gray-800 bg-gray-900 p-1.5 space-y-0.5">
          {listLoading ? (
            <p className="text-xs text-gray-500 px-2 py-3" aria-live="polite">
              Loading...
            </p>
          ) : listError ? (
            <p className="text-xs text-red-400 px-2 py-3" role="alert">
              {listError}
            </p>
          ) : playbooks.length === 0 ? (
            <p className="text-xs text-gray-500 px-2 py-3">
              No playbooks yet. Create one to get started.
            </p>
          ) : (
            playbooks.map(p => (
              <PlaybookListItem
                key={p.name}
                playbook={p}
                isSelected={selectedName === p.name && mode === 'view'}
                onSelect={handleSelect}
              />
            ))
          )}
        </div>
      </aside>

      {/* ── Right panel: editor / new form / idle ────────────────────────── */}
      <section className="flex-1 min-w-0 flex flex-col" aria-label="Playbook editor">
        {/* IDLE state */}
        {mode === 'idle' && (
          <div className="flex-1 flex items-center justify-center rounded-lg border border-gray-800 bg-gray-900">
            <p className="text-sm text-gray-500">
              Select a playbook to view or edit, or create a new one.
            </p>
          </div>
        )}

        {/* VIEW / EDIT state */}
        {mode === 'view' && (
          <div className="flex-1 flex flex-col gap-3 min-h-0">
            {/* Title bar */}
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                {contentLoading ? (
                  <span className="text-sm text-gray-500" aria-live="polite">Loading...</span>
                ) : (
                  <>
                    <h2 className="text-base font-semibold text-gray-100 truncate">
                      {editorTitle ?? selectedName}
                    </h2>
                    <span className="text-xs text-gray-500">{selectedName}</span>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleSave}
                  disabled={saving || contentLoading || !!contentError}
                  aria-busy={saving}
                  className={btnPrimary}
                >
                  {saving ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={handleDelete}
                  disabled={deleting || contentLoading}
                  aria-busy={deleting}
                  className={btnDanger}
                >
                  {deleting ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>

            {/* Feedback messages */}
            {actionError && (
              <p className="text-sm text-red-400" role="alert">
                {actionError}
              </p>
            )}
            {actionSuccess && (
              <p className="text-sm text-green-400" role="status">
                {actionSuccess}
              </p>
            )}

            {/* Content area */}
            {contentLoading ? (
              <div
                className="flex-1 rounded-lg border border-gray-800 bg-gray-900 flex items-center justify-center"
                aria-live="polite"
              >
                <span className="text-sm text-gray-500">Loading content...</span>
              </div>
            ) : contentError ? (
              <div className="flex-1 rounded-lg border border-red-900 bg-gray-900 flex items-center justify-center">
                <p className="text-sm text-red-400" role="alert">
                  {contentError}
                </p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col min-h-0">
                <label htmlFor="playbook-editor" className="sr-only">
                  Playbook markdown content
                </label>
                <textarea
                  id="playbook-editor"
                  value={content}
                  onChange={e => {
                    setContent(e.target.value);
                    setActionSuccess('');
                  }}
                  spellCheck={false}
                  className={`flex-1 resize-none font-mono text-sm ${inputClass}`}
                  aria-label={`Markdown editor for ${selectedName}`}
                />
              </div>
            )}
          </div>
        )}

        {/* NEW PLAYBOOK form */}
        {mode === 'new' && (
          <div className="flex-1 flex flex-col gap-4 rounded-lg border border-gray-800 bg-gray-900 p-5 min-h-0">
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-100">New Playbook</h2>
              <button
                onClick={() => setMode('idle')}
                aria-label="Cancel new playbook"
                className={btnSecondary}
              >
                Cancel
              </button>
            </div>

            {/* Name field */}
            <div>
              <label htmlFor="new-playbook-name" className="block text-xs text-gray-500 mb-1">
                Name <span className="text-gray-600">(lowercase letters, numbers, hyphens)</span>
              </label>
              <input
                id="new-playbook-name"
                type="text"
                value={newName}
                onChange={e => {
                  setNewName(e.target.value);
                  setNewNameError('');
                }}
                placeholder="e.g. investor-outreach"
                className={inputClass}
                aria-describedby={newNameError ? 'new-name-error' : undefined}
                aria-invalid={!!newNameError}
              />
              {newNameError && (
                <p id="new-name-error" className="mt-1 text-xs text-red-400" role="alert">
                  {newNameError}
                </p>
              )}
            </div>

            {/* Content field */}
            <div className="flex flex-col flex-1 min-h-0">
              <label htmlFor="new-playbook-content" className="block text-xs text-gray-500 mb-1">
                Content <span className="text-gray-600">(Markdown)</span>
              </label>
              <textarea
                id="new-playbook-content"
                value={newContent}
                onChange={e => {
                  setNewContent(e.target.value);
                  setActionSuccess('');
                }}
                placeholder={'# Playbook Title\n\nDescribe the workflow steps here...'}
                spellCheck={false}
                className={`flex-1 resize-none font-mono text-sm ${inputClass}`}
              />
            </div>

            {/* Feedback */}
            {actionError && (
              <p className="text-sm text-red-400" role="alert">
                {actionError}
              </p>
            )}
            {actionSuccess && (
              <p className="text-sm text-green-400" role="status">
                {actionSuccess}
              </p>
            )}

            {/* Submit */}
            <div>
              <button
                onClick={handleCreate}
                disabled={saving}
                aria-busy={saving}
                className={btnPrimary}
              >
                {saving ? 'Creating...' : 'Create Playbook'}
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
