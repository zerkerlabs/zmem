interface StatusBadgeProps {
  status: 'built' | 'alpha' | 'pending' | 'ready' | 'blocked';
}

const config = {
  built: {
    bg: 'rgba(146, 214, 111, 0.12)',
    color: '#92D66F',
    border: 'rgba(146, 214, 111, 0.25)',
    label: 'built',
  },
  ready: {
    bg: 'rgba(146, 214, 111, 0.12)',
    color: '#92D66F',
    border: 'rgba(146, 214, 111, 0.25)',
    label: 'ready',
  },
  alpha: {
    bg: 'rgba(240, 179, 90, 0.12)',
    color: '#F0B35A',
    border: 'rgba(240, 179, 90, 0.25)',
    label: 'alpha',
  },
  pending: {
    bg: 'rgba(224, 111, 98, 0.12)',
    color: '#E06F62',
    border: 'rgba(224, 111, 98, 0.25)',
    label: 'pending',
  },
  blocked: {
    bg: 'rgba(224, 111, 98, 0.12)',
    color: '#E06F62',
    border: 'rgba(224, 111, 98, 0.25)',
    label: 'blocked',
  },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const c = config[status];
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-eyebrow"
      style={{
        backgroundColor: c.bg,
        color: c.color,
        border: `1px solid ${c.border}`,
      }}
    >
      <span
        className="inline-block h-1.5 w-1.5 rounded-full"
        style={{
          backgroundColor: c.color,
          animation: 'statusPulse 2s ease-in-out infinite',
        }}
      />
      {c.label}
    </span>
  );
}
