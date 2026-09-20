import React from 'react';
import CitationChip from './CitationChip';

export default function AdvisoryCard({ advisory, onSelectCitation }) {
  if (!advisory) return null;

  const isHedged = advisory.hedged;
  const crops = advisory.recommended || [];
  const irrigationGuidance = advisory.irrigation_guidance || [];
  const warnings = advisory.warnings || [];

  const getViabilityLabel = (viability) => {
    switch (viability?.toLowerCase()) {
      case 'good': return { text: 'High viability', cls: 'badge-success' };
      case 'poor': return { text: 'High risk', cls: 'badge-danger' };
      default: return { text: 'Moderate', cls: 'badge-warning' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Hedged notice */}
      {isHedged && (
        <div style={{
          background: 'var(--color-warning-bg)',
          border: '1px solid var(--color-warning)',
          borderLeft: '4px solid var(--color-warning)',
          borderRadius: 3,
          padding: '10px 14px',
          fontSize: '0.85rem',
          color: 'var(--text-primary)',
        }}>
          <strong>Hedged advisory:</strong> Confidence is moderate due to forecast horizon. Risk mitigation steps (staggered sowing, drought-tolerant varieties) are recommended.
        </div>
      )}

      {/* Crop recommendations */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700 }}>Ranked crop recommendations</h3>

        {crops.map((option, idx) => {
          const vBadge = getViabilityLabel(option.expected_viability);

          return (
            <div
              key={option.crop || idx}
              style={{
                background: 'var(--bg-surface)',
                border: idx === 0
                  ? '2px solid var(--color-action)'
                  : '1px solid var(--border-default)',
                borderRadius: 3,
                padding: '16px 18px',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              {/* Crop header */}
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                  <span style={{
                    fontSize: '0.85rem',
                    fontWeight: 700,
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}>
                    #{option.rank || idx + 1}
                  </span>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: 700, textTransform: 'capitalize' }}>
                    {option.crop}
                  </h4>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`badge ${vBadge.cls}`}>{vBadge.text}</span>
                  {option.water_requirement_mm && (
                    <span className="badge badge-info">{option.water_requirement_mm} mm water</span>
                  )}
                  {option.sowing_window && (
                    <span className="badge badge-neutral">{option.sowing_window}</span>
                  )}
                </div>
              </div>

              {/* Rationale with citations */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', letterSpacing: '0.02em' }}>
                  Rationale (click reference to verify source):
                </p>
                <ul style={{ listStyle: 'disc', paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {option.rationale.map((claim, cIdx) => (
                    <li
                      key={cIdx}
                      style={{
                        fontSize: '0.88rem',
                        color: 'var(--text-primary)',
                        lineHeight: 1.55,
                      }}
                    >
                      {claim.statement}
                      {' '}
                      {claim.citation_ids.map((cid) => (
                        <CitationChip
                          key={cid}
                          citationId={cid}
                          onSelect={onSelectCitation}
                        />
                      ))}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          );
        })}
      </div>

      {/* Irrigation guidance */}
      {irrigationGuidance.length > 0 && (
        <div style={{
          background: 'var(--bg-surface-alt)',
          border: '1px solid var(--border-default)',
          borderRadius: 3,
          padding: '14px 18px',
        }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 8 }}>
            Irrigation guidance
          </h4>
          <ul style={{ listStyle: 'disc', paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {irrigationGuidance.map((claim, idx) => (
              <li key={idx} style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.55 }}>
                {claim.statement}
                {' '}
                {claim.citation_ids.map((cid) => (
                  <CitationChip key={cid} citationId={cid} onSelect={onSelectCitation} />
                ))}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings */}
      {warnings.length > 0 && (
        <div style={{
          background: 'var(--color-danger-bg)',
          border: '1px solid var(--color-danger)',
          borderLeft: '4px solid var(--color-danger)',
          borderRadius: 3,
          padding: '12px 16px',
        }}>
          <strong style={{ fontSize: '0.85rem', color: 'var(--color-danger)' }}>Warnings</strong>
          <ul style={{ marginTop: 6, paddingLeft: 18, fontSize: '0.82rem', color: 'var(--text-primary)' }}>
            {warnings.map((w, idx) => (
              <li key={idx} style={{ marginTop: 2 }}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
