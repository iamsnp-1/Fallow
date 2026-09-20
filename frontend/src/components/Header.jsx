import React from 'react';

export default function Header() {
  return (
    <header style={{
      borderBottom: '1px solid var(--border-default)',
      backgroundColor: 'var(--bg-surface)',
      position: 'sticky',
      top: 0,
      zIndex: 40,
      padding: '12px 24px',
    }}>
      <div style={{
        maxWidth: 960,
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
      }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Fallow</h1>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 1 }}>
            Climate-aware crop advisory — IBM Granite + RAG provenance
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <span>Granite 3-8B</span>
          <span style={{ color: 'var(--border-strong)' }}>|</span>
          <span>ICAR / MPKV / TNAU corpus</span>
          <span style={{ color: 'var(--border-strong)' }}>|</span>
          <span>Provenance enforced</span>
        </div>
      </div>
    </header>
  );
}
