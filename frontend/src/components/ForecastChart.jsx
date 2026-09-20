import React, { useState } from 'react';

export default function ForecastChart({ forecast }) {
  const [hoveredIndex, setHoveredIndex] = useState(null);

  if (!forecast || !forecast.forecast_data || !forecast.historical_data) {
    return (
      <div style={{ padding: 20, color: 'var(--text-muted)', fontSize: '0.85rem' }}>
        No rainfall data available.
      </div>
    );
  }

  const months = forecast.forecast_data.map(d => d.month);
  const forecastVals = forecast.forecast_data.map(d => d.rainfall_mm);
  const histVals = forecast.historical_data.map(d => d.rainfall_mm);

  const maxVal = Math.max(...forecastVals, ...histVals, 100);
  const chartHeight = 170;
  const labelHeight = 24;
  const usableHeight = chartHeight - labelHeight;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Precipitation: projected vs historical</h3>

        <div style={{ display: 'flex', alignItems: 'center', gap: 14, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 10, height: 10, background: 'var(--color-action)', borderRadius: 1, display: 'inline-block' }} />
            Projected ({forecast.projected_rainfall_mm} mm)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{ width: 10, height: 10, background: 'var(--border-strong)', borderRadius: 1, display: 'inline-block' }} />
            {forecast.baseline_years}-yr mean ({forecast.historical_mean_mm} mm)
          </span>
        </div>
      </div>

      <div style={{
        position: 'relative',
        background: 'var(--bg-surface-alt)',
        borderRadius: 3,
        padding: '14px 10px 4px 10px',
        border: '1px solid var(--border-default)',
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-around',
          height: chartHeight,
          gap: 8,
        }}>
          {months.map((month, idx) => {
            const fVal = forecastVals[idx] || 0;
            const hVal = histVals[idx] || 0;
            const fHeight = (fVal / maxVal) * usableHeight;
            const hHeight = (hVal / maxVal) * usableHeight;
            const isHovered = hoveredIndex === idx;

            return (
              <div
                key={month}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  height: '100%',
                  justifyContent: 'flex-end',
                  cursor: 'default',
                  position: 'relative',
                }}
              >
                {/* Tooltip */}
                {isHovered && (
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'var(--text-primary)',
                    color: 'var(--text-inverse)',
                    borderRadius: 2,
                    padding: '4px 8px',
                    fontSize: '0.72rem',
                    whiteSpace: 'nowrap',
                    zIndex: 10,
                    pointerEvents: 'none',
                  }}>
                    <div>Proj: <strong>{fVal} mm</strong></div>
                    <div>Hist: <strong>{hVal} mm</strong></div>
                  </div>
                )}

                <div style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: 3,
                  width: '100%',
                  maxWidth: 42,
                  height: usableHeight,
                }}>
                  {/* Historical bar */}
                  <div
                    style={{
                      flex: 1,
                      height: `${Math.max(hHeight, 3)}px`,
                      background: 'var(--border-strong)',
                      borderRadius: '2px 2px 0 0',
                      opacity: isHovered ? 1 : 0.6,
                      transition: 'opacity 0.1s ease',
                    }}
                  />
                  {/* Projected bar */}
                  <div
                    style={{
                      flex: 1,
                      height: `${Math.max(fHeight, 3)}px`,
                      background: 'var(--color-action)',
                      borderRadius: '2px 2px 0 0',
                      opacity: isHovered ? 1 : 0.8,
                      transition: 'opacity 0.1s ease',
                    }}
                  />
                </div>

                <div style={{
                  height: labelHeight,
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: '0.74rem',
                  fontWeight: isHovered ? 600 : 400,
                  color: isHovered ? 'var(--text-primary)' : 'var(--text-muted)',
                }}>
                  {month}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
