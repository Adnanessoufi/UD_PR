export default function UniversityEmblem({ className = '' }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 72 78"
      fill="none"
      role="img"
      aria-label="University of Debrecen inspired emblem"
    >
      <path
        d="M25 12 20 4l9 4 7-7 7 7 9-4-5 8-11 4-11-4Z"
        fill="#B8952F"
        stroke="#87681D"
        strokeWidth="1.3"
      />
      <path
        d="M17 18c-7 8-9 24-1 38M55 18c7 8 9 24 1 38"
        stroke="#B8952F"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M14 25 7 20m7 13-9-3m9 12-9 1m12 8-7 6m48-32 7-5m-7 13 9-3m-9 12 9 1m-12 8 7 6"
        stroke="#B8952F"
        strokeWidth="2"
        strokeLinecap="round"
      />
      <path
        d="M36 15 55 20v23c0 14-7 23-19 31-12-8-19-17-19-31V20l19-5Z"
        fill="#00543F"
        stroke="#B8952F"
        strokeWidth="3"
      />
      <path
        d="M36 20 50 24v19c0 10-5 18-14 24-9-6-14-14-14-24V24l14-4Z"
        stroke="#F1E4A8"
        strokeWidth="1.5"
      />
      <circle cx="36" cy="40" r="12" fill="#F4F0DC" stroke="#B8952F" strokeWidth="2" />
      <path
        d="M30 33v10c0 4 2 6 6 6s6-2 6-6V33"
        stroke="#00543F"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path d="M25 27h22M29 55h14" stroke="#B8952F" strokeWidth="1.5" />
    </svg>
  )
}
