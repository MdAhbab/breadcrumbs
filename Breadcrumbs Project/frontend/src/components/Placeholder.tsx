/*
 * A route that exists but is not built yet.
 *
 * It names the section of designs_instructions.md that specifies it, so the
 * next person to open this file knows exactly what goes here.
 */

interface Props {
  title: string;
  spec: string;
}

export function Placeholder({ title, spec }: Props) {
  return (
    <div
      style={{
        padding: 'var(--space-2xl) var(--space-xl)',
        maxWidth: 'var(--content-max)',
      }}
    >
      <p className="mono-label" style={{ color: 'var(--ink-45)', marginBottom: 'var(--space-sm)' }}>
        Not built yet
      </p>
      <h1 style={{ marginBottom: 'var(--space-md)' }}>{title}</h1>
      <p style={{ color: 'var(--ink-70)', maxWidth: '60ch', fontSize: 17, lineHeight: 1.65 }}>
        Specified in <code>frontend/designs_instructions.md</code>, {spec}. The API
        that backs this screen is running — see <code>/docs</code> on the backend.
      </p>
    </div>
  );
}
