interface CodeBlockProps {
  code: string;
  title?: string;
  className?: string;
  highlightedLines?: number[];
}

export default function CodeBlock({ code, title, className = '', highlightedLines = [] }: CodeBlockProps) {
  const lines = code.split('\n');

  return (
    <div
      className={`overflow-hidden rounded-md border border-zline bg-[#0A0A0A] ${className}`}
    >
      {title && (
        <div className="flex items-center gap-2 border-b border-zline px-4 py-2.5 bg-[#141414]">
          <span className="h-2.5 w-2.5 rounded-full bg-zred" />
          <span className="h-2.5 w-2.5 rounded-full bg-zamber" />
          <span className="h-2.5 w-2.5 rounded-full bg-zlime" />
          <span className="ml-2 text-caption text-zmuted">{title}</span>
        </div>
      )}
      <pre className="overflow-x-auto p-5 text-[13px] leading-[1.7] font-mono" style={{ color: '#D9E3D0' }}>
        {lines.map((line, i) => (
          <div key={i} className={highlightedLines.includes(i) ? 'text-zlime' : ''}>
            {line}
          </div>
        ))}
      </pre>
    </div>
  );
}
