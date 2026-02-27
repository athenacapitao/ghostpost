import type { Email } from '../api/client';

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleString();
}

function formatSize(bytes: number | null): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

export default function EmailCard({ email }: { email: Email }) {
  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 space-y-1">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {email.is_sent && (
              <span className="text-xs text-blue-400 font-medium">SENT</span>
            )}
            {email.is_draft && (
              <span className="text-xs text-yellow-400 font-medium">DRAFT</span>
            )}
            <span className="font-medium text-sm text-gray-200">
              {email.from_address || 'Unknown'}
            </span>
          </div>
          <span className="text-xs text-gray-500">{formatDate(email.date)}</span>
        </div>
        {email.to_addresses && email.to_addresses.length > 0 && (
          <div className="text-xs text-gray-500">
            To: {email.to_addresses.join(', ')}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="px-4 py-3">
        {email.body_plain ? (
          <pre className="text-sm text-gray-300 whitespace-pre-wrap font-sans leading-relaxed">
            {email.body_plain}
          </pre>
        ) : email.body_html ? (
          <div
            className="text-sm text-gray-300 prose prose-invert prose-sm max-w-none"
            dangerouslySetInnerHTML={{ __html: email.body_html }}
          />
        ) : (
          <p className="text-sm text-gray-500 italic">No content</p>
        )}
      </div>

      {/* Attachments */}
      {email.attachments.length > 0 && (
        <div className="px-4 py-2 border-t border-gray-800 flex flex-wrap gap-2">
          {email.attachments.map(att => (
            <a
              key={att.id}
              href={`/api/attachments/${att.id}/download`}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-gray-800 text-xs text-gray-300 hover:bg-gray-700 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              {att.filename || 'attachment'}
              {att.size && <span className="text-gray-500">({formatSize(att.size)})</span>}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
