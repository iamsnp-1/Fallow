import React from 'react';

const AGENT_META = {
  forecast: {
    title: 'Forecast',
    desc: 'Coordinates + Open-Meteo baseline',
  },
  research: {
    title: 'Research (RAG)',
    desc: 'ICAR / KVK agronomic search',
  },
  advisory: {
    title: 'Advisory',
    desc: 'Granite 3-8B grounded reasoning',
  },
  localization: {
    title: 'Localization',
    desc: 'Vernacular templating + TTS',
  },
};

export default function AgentTrace({ currentStage, traces, isRunning }) {
  const stageList = ['forecast', 'research', 'advisory', 'localization'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Pipeline trace</h3>
        {isRunning && (
          <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>
            Running: {currentStage?.agent || 'initializing'}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {stageList.map((stageKey) => {
          const meta = AGENT_META[stageKey];
          const traceEntry = traces.find(t => t.agent === stageKey);
          const isCurrent = currentStage?.agent === stageKey && isRunning;
          const isDone = !!traceEntry && traceEntry.status === 'ok';
          const isError = !!traceEntry && traceEntry.status === 'error';

          let statusLabel = 'Pending';
          let statusColor = 'var(--text-muted)';
          if (isDone) { statusLabel = 'Done'; statusColor = 'var(--color-success)'; }
          else if (isError) { statusLabel = 'Error'; statusColor = 'var(--color-danger)'; }
          else if (isCurrent) { statusLabel = 'Running…'; statusColor = 'var(--color-action)'; }

          return (
            <div
              key={stageKey}
              style={{
                background: isCurrent ? 'var(--color-info-bg)' : 'var(--bg-surface-alt)',
                border: isCurrent
                  ? '1px solid var(--color-action)'
                  : '1px solid var(--border-default)',
                borderRadius: 3,
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 12,
              }}
            >
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <strong style={{ fontSize: '0.85rem' }}>{meta.title}</strong>
                  <span style={{ fontSize: '0.75rem', color: statusColor, fontWeight: 600 }}>{statusLabel}</span>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {traceEntry?.message || (isCurrent && currentStage?.message) || meta.desc}
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ fontFamily: 'var(--font-mono)' }}>
                  {traceEntry?.ms ? `${traceEntry.ms}ms` : isCurrent ? '…' : '—'}
                </span>
                {traceEntry?.passages && (
                  <span className="badge badge-neutral">{traceEntry.passages} passages</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
