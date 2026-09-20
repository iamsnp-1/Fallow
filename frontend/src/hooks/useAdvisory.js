import { useState, useEffect, useCallback } from 'react';
import { getDistricts, getForecast, getCitation, streamAdvisory } from '../api/client';

export function useAdvisory() {
  const [districts, setDistricts] = useState([]);
  const [formData, setFormData] = useState({
    district_id: 'IN-MH-AUR',
    district_name: 'Aurangabad',
    land_size_acres: 2.5,
    irrigation_access: 'rainfed',
    season: 'kharif',
    language: 'hi',
    crop_history: ['cotton', 'bajra'],
  });

  const [forecast, setForecast] = useState(null);
  const [isLoadingForecast, setIsLoadingForecast] = useState(false);

  // Pipeline stream states
  const [isRunning, setIsRunning] = useState(false);
  const [currentStage, setCurrentStage] = useState(null);
  const [traces, setTraces] = useState([]);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [error, setError] = useState(null);

  // Citation viewer modal
  const [selectedCitation, setSelectedCitation] = useState(null);
  const [isLoadingCitation, setIsLoadingCitation] = useState(false);

  // 1. Fetch districts on mount
  useEffect(() => {
    getDistricts()
      .then((data) => {
        setDistricts(data);
        if (data.length > 0) {
          const first = data[0];
          setFormData((prev) => ({
            ...prev,
            district_id: first.district_id,
            district_name: first.name,
            language: first.available_languages[0] || 'hi',
          }));
        }
      })
      .catch((err) => console.error('Failed to load districts:', err));
  }, []);

  // 2. Fetch forecast when district or season changes (UI beat before running advisory)
  useEffect(() => {
    if (!formData.district_id) return;
    setIsLoadingForecast(true);
    getForecast(formData.district_id, formData.season)
      .then((data) => {
        setForecast(data);
        setIsLoadingForecast(false);
      })
      .catch((err) => {
        console.warn('Forecast fetch warning:', err);
        setIsLoadingForecast(false);
      });
  }, [formData.district_id, formData.season]);

  // Handle form updates
  const updateFormField = useCallback((field, value) => {
    setFormData((prev) => {
      const updated = { ...prev, [field]: value };
      if (field === 'district_id') {
        const found = districts.find((d) => d.district_id === value);
        if (found) {
          updated.district_name = found.name;
          if (!found.available_languages.includes(prev.language)) {
            updated.language = found.available_languages[0] || 'en';
          }
        }
      }
      return updated;
    });
  }, [districts]);

  // Execute pipeline via SSE streaming
  const executePipeline = useCallback(() => {
    setIsRunning(true);
    setTraces([]);
    setCurrentStage({ agent: 'forecast', message: 'Initiating pipeline...' });
    setPipelineResult(null);
    setError(null);

    const abortFn = streamAdvisory(formData, {
      onStageStart: (data) => {
        setCurrentStage(data);
      },
      onTrace: (traceEntry) => {
        setTraces((prev) => {
          const existing = prev.findIndex((t) => t.agent === traceEntry.agent);
          if (existing >= 0) {
            const next = [...prev];
            next[existing] = traceEntry;
            return next;
          }
          return [...prev, traceEntry];
        });
      },
      onForecast: (forecastData) => {
        setForecast(forecastData);
      },
      onComplete: (completeResponse) => {
        setPipelineResult(completeResponse);
        setIsRunning(false);
        setCurrentStage(null);
      },
      onError: (errData) => {
        setError(errData.error || 'Pipeline execution failed.');
        setIsRunning(false);
        setCurrentStage(null);
      },
    });

    return abortFn;
  }, [formData]);

  // Citation lookup
  const openCitation = useCallback(async (passageId) => {
    // Check if passage is in current advisory citation lookup first
    if (pipelineResult?.advisory?.citations?.[passageId]) {
      setSelectedCitation(pipelineResult.advisory.citations[passageId]);
      return;
    }

    setIsLoadingCitation(true);
    try {
      const cit = await getCitation(passageId);
      setSelectedCitation(cit);
    } catch (e) {
      console.error('Failed to load citation:', e);
    } finally {
      setIsLoadingCitation(false);
    }
  }, [pipelineResult]);

  const closeCitation = useCallback(() => {
    setSelectedCitation(null);
  }, []);

  const selectedDistrict = districts.find((d) => d.district_id === formData.district_id);

  return {
    districts,
    formData,
    selectedDistrict,
    updateFormField,
    forecast,
    isLoadingForecast,
    isRunning,
    currentStage,
    traces,
    pipelineResult,
    error,
    executePipeline,
    selectedCitation,
    openCitation,
    closeCitation,
    isLoadingCitation,
  };
}
