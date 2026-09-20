/**
 * Fallow API Client
 * Handles HTTP requests and Server-Sent Events (SSE) streaming for pipeline traces.
 */

const API_BASE = '/api';

/**
 * Fetch supported demo districts.
 */
export async function getDistricts() {
  const res = await fetch(`${API_BASE}/districts`);
  if (!res.ok) throw new Error(`Failed to fetch districts: ${res.statusText}`);
  return res.json();
}

/**
 * Fetch seasonal forecast and anomaly status for a district.
 */
export async function getForecast(districtId, season = 'kharif') {
  const res = await fetch(`${API_BASE}/forecast/${districtId}?season=${season}`);
  if (!res.ok) throw new Error(`Failed to fetch forecast: ${res.statusText}`);
  return res.json();
}

/**
 * Fetch a single citation passage by ID.
 */
export async function getCitation(passageId) {
  const res = await fetch(`${API_BASE}/citation/${passageId}`);
  if (!res.ok) throw new Error(`Failed to fetch citation ${passageId}: ${res.statusText}`);
  return res.json();
}

/**
 * Check backend health status.
 */
export async function getHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) return { status: 'offline' };
  return res.json();
}

/**
 * Stream advisory pipeline execution via SSE.
 * 
 * Callbacks:
 * - onStageStart: ({ agent, message })
 * - onTrace: (TraceEntry)
 * - onForecast: (ForecastResult)
 * - onComplete: (PipelineResponse)
 * - onError: (error)
 */
export function streamAdvisory(profile, { onStageStart, onTrace, onForecast, onComplete, onError }) {
  const controller = new AbortController();

  fetch(`${API_BASE}/advisory?stream=true`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(profile),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Pipeline failed with HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data: ')) {
            const jsonStr = trimmed.substring(6);
            try {
              const event = JSON.parse(jsonStr);
              if (event.type === 'stage_start' && onStageStart) {
                onStageStart(event.data);
              } else if (event.type === 'trace' && onTrace) {
                onTrace(event.data);
              } else if (event.type === 'forecast' && onForecast) {
                onForecast(event.data);
              } else if (event.type === 'complete' && onComplete) {
                onComplete(event.data);
              } else if (event.type === 'error' && onError) {
                onError(event.data);
              }
            } catch (err) {
              console.warn('Failed to parse SSE event:', jsonStr, err);
            }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError' && onError) {
        onError({ error: err.message });
      }
    });

  return () => controller.abort();
}
