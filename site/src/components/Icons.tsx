import type { CSSProperties, ReactNode } from 'react';

type IconProps = {
  size?: number;
  className?: string;
  style?: CSSProperties;
};

function IconBase({
  size = 20,
  className,
  style,
  children,
}: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      style={style}
    >
      {children}
    </svg>
  );
}

export function Github(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M9 19c-4 1.5-4-2-5-2.5" />
      <path d="M15 22v-3.5c0-1 .1-1.4-.5-2 2.8-.3 5.5-1.4 5.5-6A4.6 4.6 0 0 0 18.7 7 4.3 4.3 0 0 0 18.6 4s-1-.3-3.4 1.3a11.7 11.7 0 0 0-6.2 0C6.6 3.7 5.6 4 5.6 4a4.3 4.3 0 0 0-.1 3A4.6 4.6 0 0 0 4 10.5c0 4.6 2.8 5.7 5.5 6-.5.5-.8 1.1-.8 2V22" />
    </IconBase>
  );
}

export function Twitter(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M22 4.5c-.8.4-1.6.6-2.5.7.9-.5 1.5-1.3 1.8-2.3-.8.5-1.8.9-2.8 1.1A4.3 4.3 0 0 0 11 7.1c0 .3 0 .7.1 1A12.3 12.3 0 0 1 2.2 3.6a4.3 4.3 0 0 0 1.3 5.8c-.7 0-1.4-.2-2-.5v.1c0 2.1 1.5 3.8 3.5 4.2-.4.1-.8.2-1.2.2-.3 0-.6 0-.8-.1.6 1.8 2.2 3 4.1 3A8.7 8.7 0 0 1 2 18.1c-.3 0-.7 0-1-.1A12.2 12.2 0 0 0 7.6 20c7.9 0 12.2-6.5 12.2-12.2v-.6c.8-.6 1.6-1.4 2.2-2.2Z" />
    </IconBase>
  );
}

export function Menu(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </IconBase>
  );
}

export function X(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </IconBase>
  );
}

export function Copy(props: IconProps) {
  return (
    <IconBase {...props}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </IconBase>
  );
}

export function Check(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="m20 6-11 11-5-5" />
    </IconBase>
  );
}

export function Search(props: IconProps) {
  return (
    <IconBase {...props}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </IconBase>
  );
}

export function BookOpen(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 7v14" />
      <path d="M3 5.5A3.5 3.5 0 0 1 6.5 2H12v17H6.5A3.5 3.5 0 0 0 3 22Z" />
      <path d="M21 5.5A3.5 3.5 0 0 0 17.5 2H12v17h5.5A3.5 3.5 0 0 1 21 22Z" />
    </IconBase>
  );
}

export function Shield(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
    </IconBase>
  );
}

export function FileCheck(props: IconProps) {
  return (
    <IconBase {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
      <path d="M14 2v6h6" />
      <path d="m9 15 2 2 4-4" />
    </IconBase>
  );
}
