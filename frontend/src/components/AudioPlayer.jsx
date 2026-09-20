import React, { useState, useRef } from 'react';

export default function AudioPlayer({ localized }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [copied, setCopied] = useState(false);
  const [progress, setProgress] = useState(0);
  const audioRef = useRef(null);

  if (!localized) return null;

  const audioUrl = localized.audio_url || '';
  const smsText = localized.sms_text || '';
  const language = localized.language || 'local';

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().catch(e => {
        console.warn('Audio playback failed:', e);
      });
      setIsPlaying(true);
    }
  };

  const handleTimeUpdate = () => {
    if (!audioRef.current) return;
    const current = audioRef.current.currentTime;
    const duration = audioRef.current.duration || 1;
    setProgress((current / duration) * 100);
  };

  const handleCopySMS = () => {
    if (!smsText) return;
    navigator.clipboard.writeText(smsText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-default)',
      borderRadius: 3,
      padding: '16px 18px',
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
        <div>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 600 }}>
            Voice advisory ({language})
          </h4>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
            Spoken delivery synthesized by the localization agent
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <audio
            ref={audioRef}
            src={audioUrl}
            onTimeUpdate={handleTimeUpdate}
            onEnded={() => setIsPlaying(false)}
          />
          <button
            onClick={togglePlay}
            className="btn-primary"
            style={{ padding: '7px 16px', fontSize: '0.85rem' }}
            aria-label={isPlaying ? 'Pause audio' : 'Play audio'}
          >
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{
        width: '100%',
        height: 3,
        background: 'var(--bg-inset)',
        borderRadius: 1,
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${progress}%`,
          height: '100%',
          background: 'var(--color-action)',
          transition: 'width 0.1s linear',
        }} />
      </div>

      {/* SMS fallback */}
      {smsText && (
        <div style={{
          padding: '10px 12px',
          background: 'var(--bg-surface-alt)',
          borderRadius: 3,
          border: '1px solid var(--border-default)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              SMS text
            </span>
            <button
              onClick={handleCopySMS}
              className="btn-secondary"
              style={{ padding: '2px 8px', fontSize: '0.72rem' }}
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <p style={{
            fontSize: '0.82rem',
            color: 'var(--text-primary)',
            fontFamily: 'var(--font-mono)',
            lineHeight: 1.45,
          }}>
            {smsText}
          </p>
        </div>
      )}
    </div>
  );
}
