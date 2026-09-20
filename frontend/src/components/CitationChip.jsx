import React from 'react';

export default function CitationChip({ citationId, onSelect }) {
  return (
    <button
      type="button"
      className="citation-chip"
      onClick={(e) => {
        e.stopPropagation();
        onSelect(citationId);
      }}
      title={`Verify source: ${citationId}`}
    >
      {citationId}
    </button>
  );
}
