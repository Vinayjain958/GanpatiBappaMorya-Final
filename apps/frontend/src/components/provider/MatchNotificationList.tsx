import React from 'react';
import { ProviderNotificationListResponse } from '../../api/providerIntelligenceApi';

interface MatchNotificationListProps {
  notifications: ProviderNotificationListResponse | null;
  onMarkRead: (id: string) => void;
}

export const MatchNotificationList: React.FC<MatchNotificationListProps> = ({
  notifications,
  onMarkRead
}) => {
  if (!notifications || notifications.items.length === 0) {
    return <p>No recent notifications.</p>;
  }

  return (
    <div className="match-notification-list">
      {notifications.items.map((n) => (
        <div key={n.id} className={`notification-item ${n.is_read ? 'read' : 'unread'}`}>
          <div className="header">
            <h4>{n.title}</h4>
            <span className="date">{new Date(n.created_at).toLocaleDateString()}</span>
          </div>
          <p>{n.body}</p>
          {n.segment_summary && n.segment_summary.length > 0 && (
            <div className="badges">
              {n.segment_summary.map((s, idx) => (
                <span key={idx} className="badge">{s}</span>
              ))}
            </div>
          )}
          {!n.is_read && (
            <button onClick={() => onMarkRead(n.id)}>Mark as Read</button>
          )}
        </div>
      ))}
    </div>
  );
};
