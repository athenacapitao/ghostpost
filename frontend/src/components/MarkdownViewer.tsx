import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownViewerProps {
  content: string;
  className?: string;
}

export default function MarkdownViewer({ content, className = '' }: MarkdownViewerProps) {
  return (
    <div className={`markdown-viewer ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold text-gray-100 mb-4 mt-6 first:mt-0 pb-2 border-b border-gray-800">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold text-gray-200 mb-3 mt-5">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-medium text-gray-300 mb-2 mt-4">{children}</h3>,
          h4: ({ children }) => <h4 className="text-sm font-medium text-gray-300 mb-2 mt-3">{children}</h4>,
          p: ({ children }) => <p className="text-sm text-gray-300 mb-3 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="list-disc list-inside text-sm text-gray-300 mb-3 space-y-1 ml-2">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside text-sm text-gray-300 mb-3 space-y-1 ml-2">{children}</ol>,
          li: ({ children }) => <li className="text-sm text-gray-300">{children}</li>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline underline-offset-2">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-gray-700 pl-4 my-3 text-gray-400 italic">{children}</blockquote>
          ),
          code: ({ className: codeClassName, children }) => {
            const isBlock = codeClassName?.includes('language-');
            if (isBlock) {
              return (
                <pre className="bg-gray-950 border border-gray-800 rounded-lg p-4 my-3 overflow-x-auto">
                  <code className="text-sm text-gray-300 font-mono">{children}</code>
                </pre>
              );
            }
            return <code className="bg-gray-800 text-gray-300 px-1.5 py-0.5 rounded text-sm font-mono">{children}</code>;
          },
          pre: ({ children }) => <>{children}</>,
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full text-sm border border-gray-800 rounded">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-800/50">{children}</thead>,
          th: ({ children }) => <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 text-sm text-gray-300 border-t border-gray-800">{children}</td>,
          hr: () => <hr className="border-gray-800 my-4" />,
          strong: ({ children }) => <strong className="font-semibold text-gray-200">{children}</strong>,
          em: ({ children }) => <em className="text-gray-400">{children}</em>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
