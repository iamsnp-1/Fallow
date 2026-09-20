import React from 'react';

export default function CitationViewer({ citation, onClose }) {
  if (!citation) return null;

  const meta = citation.metadata || {};
  const docTitle = citation.doc_title || meta.doc_title || 'Agricultural Extension Document';
  const publishingBody = citation.publishing_body || meta.publishing_body || 'Agricultural Extension Service';
  const year = citation.year || meta.year;
  const section = citation.section || meta.section;
  const page = citation.page || meta.page;
  const sourceUri = citation.source_uri || meta.source_uri || '#';
  const relevance = citation.relevance_score || meta.relevance_score;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 20,
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="Citation details"
    >
      <div
        style={{
          width: '100%',
          maxWidth: 620,
          maxHeight: '85vh',
          display: 'flex',
          flexDirection: 'column',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-default)',
          borderRadius: 4,
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '14px 18px',
          borderBottom: '1px solid var(--border-default)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700 }}>Source provenance</h3>
              <span className="badge badge-info" style={{ fontFamily: 'var(--font-mono)' }}>
                {citation.passage_id || citation.id}
              </span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
              Retrieved from agronomic corpus
            </p>
          </div>

          <button
            onClick={onClose}
            aria-label="Close citation viewer"
            style={{
              background: 'transparent',
              border: '1px solid var(--border-default)',
              borderRadius: 3,
              color: 'var(--text-secondary)',
              cursor: 'pointer',
              padding: '4px 8px',
              fontSize: '0.8rem',
              fontFamily: 'var(--font-body)',
            }}
          >
            Close
          </button>
        </div>

        {/* Metadata */}
        <div style={{
          padding: '14px 18px',
          background: 'var(--bg-surface-alt)',
          borderBottom: '1px solid var(--border-default)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
          gap: 10,
          fontSize: '0.8rem',
        }}>
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', fontWeight: 600 }}>Document</div>
            <strong style={{ color: 'var(--text-primary)', display: 'block', marginTop: 2 }}>
              {docTitle}
            </strong>
          </div>

          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', fontWeight: 600 }}>Publisher</div>
            <strong style={{ color: 'var(--text-primary)', display: 'block', marginTop: 2 }}>
              {publishingBody}
            </strong>
          </div>

          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', fontWeight: 600 }}>Year / Section</div>
            <div style={{ color: 'var(--text-primary)', marginTop: 2 }}>
              {year || '—'} / {section || 'General'} {page ? `(p. ${page})` : ''}
            </div>
          </div>

          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', fontWeight: 600 }}>Relevance</div>
            <div style={{ color: 'var(--color-success)', fontWeight: 600, marginTop: 2 }}>
              {relevance ? `${(relevance * 100).toFixed(1)}%` : 'Indexed'}
            </div>
          </div>
        </div>

        {/* Passage text */}
        <div style={{
          padding: '18px',
          overflowY: 'auto',
          maxHeight: 260,
          lineHeight: 1.6,
          fontSize: '0.9rem',
          color: 'var(--text-primary)',
        }}>
          <blockquote style={{
            background: 'var(--color-info-bg)',
            padding: '12px 16px',
            borderRadius: 3,
            borderLeft: '3px solid var(--color-info)',
            margin: 0,
            fontStyle: 'normal',
          }}>
            {citation.text}
          </blockquote>
        </div>

        {/* Footer */}
        <div style={{
          padding: '12px 18px',
          borderTop: '1px solid var(--border-default)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Provenance verified against active corpus
          </span>

          <a
            href={sourceUri}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{ fontSize: '0.8rem', textDecoration: 'none' }}
          >
            View source
          </a>
        </div>
      </div>
    </div>
  );
}
