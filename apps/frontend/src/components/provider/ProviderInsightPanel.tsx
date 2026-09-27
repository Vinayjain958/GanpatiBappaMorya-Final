import React from 'react';
import { ProviderInsightResponse } from '../../api/providerIntelligenceApi';

interface ProviderInsightPanelProps {
  insights: ProviderInsightResponse | null;
}

export const ProviderInsightPanel: React.FC<ProviderInsightPanelProps> = ({ insights }) => {
  if (!insights) return null;

  return (
    <div className="provider-insight-panel">
      <h2>Trends & Segments</h2>
      
      <div className="trends">
        <h3>Activity Trends ({insights.provenance.window})</h3>
        {/* Chart placeholder */}
        <ul>
          {insights.trends.map((t, idx) => (
            <li key={idx}>
              {new Date(t.period_start).toLocaleDateString()}: 
              {t.observed.views + (t.synthetic.views || 0)} views
            </li>
          ))}
        </ul>
      </div>

      <div className="segments">
        <h3>Top Traveler Segments</h3>
        <ul>
          {insights.segments.map((s, idx) => (
            <li key={idx}>
              {s.label} ({s.segment_type}) - {s.share ? (s.share * 100).toFixed(1) : 0}%
            </li>
          ))}
        </ul>
      </div>
      
      {insights.provenance.has_synthetic_data && (
        <div className="synthetic-badge">
          Contains pre-aggregated synthetic data for demonstration.
        </div>
      )}
    </div>
  );
};
