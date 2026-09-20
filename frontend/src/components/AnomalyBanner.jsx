import React from 'react';

export default function AnomalyBanner({ forecast }) {
  if (!forecast) return null;

  const isAnomaly = forecast.anomaly_flag;
  const isDeficit = forecast.deviation_pct < 0;
  const absDev = Math.abs(forecast.deviation_pct).toFixed(1);

  if (!isAnomaly) {
    return (
      <div
        role="status"
        style={{
          background: 'var(--color-success-bg)',
          border: '1px solid var(--color-success)',
          borderRadius: 3,
          padding: '12px 16px',
        }}
      >
        <strong style={{ color: 'var(--color-success)' }}>Near-normal rainfall expected</strong>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 4 }}>
          Projected {forecast.projected_rainfall_mm} mm is within {absDev}% of the {forecast.baseline_years}-year mean ({forecast.historical_mean_mm} mm). Standard crop cycles apply.
        </p>
      </div>
    );
  }

  const borderColor = isDeficit ? 'var(--color-danger)' : 'var(--color-info)';
  const bgColor = isDeficit ? 'var(--color-danger-bg)' : 'var(--color-info-bg)';
  const textColor = isDeficit ? 'var(--color-danger)' : 'var(--color-info)';

  return (
    <div
      role="alert"
      style={{
        background: bgColor,
        border: `1px solid ${borderColor}`,
        borderLeft: `4px solid ${borderColor}`,
        borderRadius: 3,
        padding: '14px 16px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <strong style={{ color: textColor }}>
          {isDeficit ? 'Rainfall deficit detected' : 'Rainfall surplus detected'}
        </strong>
        <span className={`badge ${isDeficit ? 'badge-danger' : 'badge-info'}`}>
          {forecast.deviation_pct > 0 ? `+${absDev}%` : `−${absDev}%`}
        </span>
        <span className="badge badge-warning">
          Confidence: {forecast.confidence}
        </span>
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginTop: 8, lineHeight: 1.5 }}>
        Projected rainfall is <strong>{forecast.projected_rainfall_mm} mm</strong> vs the {forecast.baseline_years}-year mean of <strong>{forecast.historical_mean_mm} mm</strong>.
        {isDeficit
          ? ' Water-intensive crops carry higher economic risk. Consider short-duration, drought-tolerant alternatives.'
          : ' Waterlogging-resistant varieties may reduce risk.'}
      </p>
    </div>
  );
}
