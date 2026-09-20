import React from 'react';

export default function DistrictSelector({ districts, selectedDistrictId, onSelectDistrict, disabled }) {
  return (
    <fieldset style={{ border: 'none', padding: 0 }}>
      <legend className="form-label" style={{ marginBottom: 8 }}>
        District
      </legend>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
        gap: 10,
      }}>
        {districts.map((d) => {
          const isSelected = d.district_id === selectedDistrictId;

          return (
            <button
              key={d.district_id}
              type="button"
              onClick={() => !disabled && onSelectDistrict(d.district_id)}
              disabled={disabled}
              aria-pressed={isSelected}
              style={{
                cursor: disabled ? 'not-allowed' : 'pointer',
                background: isSelected ? 'var(--color-info-bg)' : 'var(--bg-surface-alt)',
                border: isSelected
                  ? '2px solid var(--color-action)'
                  : '1px solid var(--border-default)',
                borderRadius: 3,
                padding: '12px 14px',
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                textAlign: 'left',
                fontFamily: 'var(--font-body)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <strong style={{ fontSize: '1rem' }}>{d.name}</strong>
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: 8 }}>{d.state}</span>
                </div>
                {isSelected && (
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--color-action)' }}>Selected</span>
                )}
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span className="badge badge-neutral">{d.agro_climatic_zone}</span>
              </div>

              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Typical crops: {d.typical_crops.slice(0, 4).join(', ')}
              </div>
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
