import React, { useEffect, useState } from 'react';
import {
  ProviderInsightResponse,
  ProviderNotificationListResponse,
  providerIntelligenceApi
} from '../api/providerIntelligenceApi';

export const ProviderDashboard: React.FC = () => {
  const [insights, setInsights] = useState<ProviderInsightResponse | null>(null);
  const [notifications, setNotifications] = useState<ProviderNotificationListResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const [insightsData, notifData] = await Promise.all([
          providerIntelligenceApi.getInsights('30d', 'auto'),
          providerIntelligenceApi.getNotifications(false)
        ]);
        setInsights(insightsData);
        setNotifications(notifData);
      } catch (error) {
        console.error('Failed to fetch provider data', error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  if (loading) return <div>Loading...</div>;

  return (
    <div className="provider-dashboard">
      <h1>Provider Dashboard</h1>
      
      <section className="kpis">
        <h2>Key Performance Indicators (30d)</h2>
        {insights?.kpis && (
          <ul>
            <li>Views: {insights.kpis.views}</li>
            <li>Saves: {insights.kpis.saves}</li>
            <li>Booking Requests: {insights.kpis.booking_requests}</li>
            <li>Save Rate: {(insights.kpis.save_rate * 100).toFixed(1)}%</li>
          </ul>
        )}
      </section>

      <section className="insights">
        <h2>Actionable Insights</h2>
        {insights?.insights.map((insight, idx) => (
          <div key={idx} className="insight-card">
            <h3>{insight.title}</h3>
            <p>{insight.explanation}</p>
            <small>{insight.supporting_metric}</small>
          </div>
        ))}
      </section>

      <section className="notifications">
        <h2>Notifications ({notifications?.unread_count} unread)</h2>
        <ul>
          {notifications?.items.map((n) => (
            <li key={n.id} style={{ fontWeight: n.is_read ? 'normal' : 'bold' }}>
              {n.title} - {n.body}
              {!n.is_read && (
                <button onClick={() => providerIntelligenceApi.markNotificationRead(n.id)}>
                  Mark Read
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
};
