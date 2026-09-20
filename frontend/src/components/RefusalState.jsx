import React from 'react';

export default function RefusalState({ reason, onReset }) {
  return (
    <div
      className="surface"
      style={{
        padding: '28px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        borderLeft: '4px solid var(--color-warning)',
      }}
    >
      <div>
        <span className="badge badge-warning" style={{ marginBottom: 8, display: 'inline-block' }}>
          Advisory withheld
        </span>
        <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>
          Insufficient grounded guidance
        </h3>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginTop: 8, lineHeight: 1.55, maxWidth: 640 }}>
          {reason || 'The corpus does not contain enough peer-reviewed documents to support a confident recommendation for this agro-climatic profile. Fallow withholds unverified guidance rather than inventing advice.'}
        </p>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: 10,
      }}>
        <div style={{
          background: 'var(--bg-surface-alt)',
          border: '1px solid var(--border-default)',
          borderRadius: 3,
          padding: '10px 14px',
        }}>
          <strong style={{ fontSize: '0.85rem' }}>Kisan Call Centre</strong>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
            Toll-free 1800-180-1551 for live agronomic support.
          </p>
        </div>

        <div style={{
          background: 'var(--bg-surface-alt)',
          border: '1px solid var(--border-default)',
          borderRadius: 3,
          padding: '10px 14px',
        }}>
          <strong style={{ fontSize: '0.85rem' }}>Expand corpus</strong>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 2 }}>
            Ingest local ICAR/SAU package-of-practices bulletins.
          </p>
        </div>
      </div>

      <div>
        <button
          onClick={onReset}
          className="btn-secondary"
        >
          Try another region or season
        </button>
      </div>
    </div>
  );
}
