import React from 'react';

export default function FarmerInputForm({
  formData,
  onChange,
  onSubmit,
  isLoading,
  availableLanguages,
}) {
  const languageLabels = {
    hi: 'Hindi',
    mr: 'Marathi',
    ta: 'Tamil',
    en: 'English',
    te: 'Telugu',
    kn: 'Kannada',
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
      }}
    >
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 14,
      }}>
        {/* Land Size */}
        <div className="form-group">
          <label className="form-label" htmlFor="land-size">Land size (acres)</label>
          <input
            id="land-size"
            type="number"
            min="0.5"
            max="100"
            step="0.5"
            className="form-input"
            value={formData.land_size_acres}
            onChange={(e) => onChange('land_size_acres', parseFloat(e.target.value) || 1)}
            disabled={isLoading}
            required
          />
        </div>

        {/* Irrigation */}
        <div className="form-group">
          <label className="form-label" htmlFor="irrigation-access">Irrigation access</label>
          <select
            id="irrigation-access"
            className="form-select"
            value={formData.irrigation_access}
            onChange={(e) => onChange('irrigation_access', e.target.value)}
            disabled={isLoading}
          >
            <option value="rainfed">Rainfed</option>
            <option value="borewell">Borewell</option>
            <option value="canal">Canal</option>
            <option value="mixed">Mixed</option>
          </select>
        </div>

        {/* Season */}
        <div className="form-group">
          <label className="form-label" htmlFor="season-select">Season</label>
          <select
            id="season-select"
            className="form-select"
            value={formData.season}
            onChange={(e) => onChange('season', e.target.value)}
            disabled={isLoading}
          >
            <option value="kharif">Kharif (Jun–Oct)</option>
            <option value="rabi">Rabi (Nov–Feb)</option>
            <option value="zaid">Zaid (Mar–May)</option>
          </select>
        </div>

        {/* Language */}
        <div className="form-group">
          <label className="form-label" htmlFor="language-select">Language</label>
          <select
            id="language-select"
            className="form-select"
            value={formData.language}
            onChange={(e) => onChange('language', e.target.value)}
            disabled={isLoading}
          >
            {(availableLanguages || ['hi', 'mr', 'ta', 'en']).map((lang) => (
              <option key={lang} value={lang}>
                {languageLabels[lang] || lang.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 4 }}>
        <button
          type="submit"
          className="btn-primary"
          disabled={isLoading}
          style={{ minWidth: 200, height: 42 }}
        >
          {isLoading ? 'Running pipeline…' : 'Get advisory'}
        </button>
      </div>
    </form>
  );
}
