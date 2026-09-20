import React from 'react';
import Header from './components/Header';
import DistrictSelector from './components/DistrictSelector';
import FarmerInputForm from './components/FarmerInputForm';
import AnomalyBanner from './components/AnomalyBanner';
import ForecastChart from './components/ForecastChart';
import AgentTrace from './components/AgentTrace';
import AdvisoryCard from './components/AdvisoryCard';
import AudioPlayer from './components/AudioPlayer';
import RefusalState from './components/RefusalState';
import CitationViewer from './components/CitationViewer';
import { useAdvisory } from './hooks/useAdvisory';

export default function App() {
  const {
    districts,
    formData,
    selectedDistrict,
    updateFormField,
    forecast,
    isRunning,
    currentStage,
    traces,
    pipelineResult,
    error,
    executePipeline,
    selectedCitation,
    openCitation,
    closeCitation,
  } = useAdvisory();

  const isRefusal = pipelineResult?.is_refusal;
  const advisory = pipelineResult?.advisory;
  const localized = pipelineResult?.localized;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header />

      <main style={{
        maxWidth: 960,
        margin: '0 auto',
        padding: '24px 20px 60px 20px',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
      }}>
        {/* Configuration */}
        <section className="surface">
          <DistrictSelector
            districts={districts}
            selectedDistrictId={formData.district_id}
            onSelectDistrict={(id) => updateFormField('district_id', id)}
            disabled={isRunning}
          />

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-default)', margin: '16px 0' }} />

          <FarmerInputForm
            formData={formData}
            onChange={updateFormField}
            onSubmit={executePipeline}
            isLoading={isRunning}
            availableLanguages={selectedDistrict?.available_languages}
          />
        </section>

        {/* Forecast */}
        {forecast && (
          <section className="surface">
            <AnomalyBanner forecast={forecast} />
            <div style={{ marginTop: 16 }}>
              <ForecastChart forecast={forecast} />
            </div>
          </section>
        )}

        {/* Pipeline trace */}
        {(isRunning || traces.length > 0) && (
          <section className="surface">
            <AgentTrace
              currentStage={currentStage}
              traces={traces}
              isRunning={isRunning}
            />
          </section>
        )}

        {/* Error */}
        {error && (
          <div role="alert" style={{
            background: 'var(--color-danger-bg)',
            border: '1px solid var(--color-danger)',
            borderLeft: '4px solid var(--color-danger)',
            borderRadius: 3,
            padding: '12px 16px',
            color: 'var(--text-primary)',
            fontSize: '0.9rem',
          }}>
            <strong>Pipeline error:</strong> {error}
          </div>
        )}

        {/* Refusal */}
        {isRefusal && (
          <RefusalState
            reason={pipelineResult?.refusal_reason}
            onReset={() => updateFormField('season', formData.season === 'kharif' ? 'rabi' : 'kharif')}
          />
        )}

        {/* Advisory results */}
        {!isRefusal && advisory && (
          <section style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            {localized && <AudioPlayer localized={localized} />}

            <div className="surface">
              <AdvisoryCard
                advisory={advisory}
                onSelectCitation={openCitation}
              />
            </div>
          </section>
        )}
      </main>

      {/* Citation modal */}
      <CitationViewer
        citation={selectedCitation}
        onClose={closeCitation}
      />
    </div>
  );
}
