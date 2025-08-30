/**
 * Collaboration Indicator - Show active users and real-time collaboration
 */
import React, { useState, useEffect } from 'react';
import { observer } from 'mobx-react-lite';
import { useStore } from '../../stores/useStore';
import { CommunicationProtocol } from '../../services/CommunicationManager';
import './RealTimeFeatures.css';

const CollaborationIndicator: React.FC = observer(() => {
  const store = useStore();
  const [showUserList, setShowUserList] = useState(false);
  const [broadcastMessage, setBroadcastMessage] = useState('');
  const [showBroadcastForm, setShowBroadcastForm] = useState(false);

  const activeUsers = Array.from(store.collaboration.activeUsers.values());
  
  const getConnectionStatusIcon = () => {
    switch (store.connectionState) {
      case 'CONNECTED': return '🟢';
      case 'CONNECTING': return '🟡';
      case 'RECONNECTING': return '🟠';
      case 'FAILED': return '🔴';
      case 'DISCONNECTED':
      default: return '⚪';
    }
  };

  const getProtocolIcon = () => {
    return store.currentProtocol === CommunicationProtocol.WEBSOCKET ? '🔄' : '📡';
  };

  const formatLastSeen = (lastSeen: Date) => {
    const diff = Date.now() - lastSeen.getTime();
    if (diff < 60000) return 'now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m`;
    return `${Math.floor(diff / 3600000)}h`;
  };

  const handleSendBroadcast = async () => {
    if (broadcastMessage.trim() && store.currentProtocol === CommunicationProtocol.WEBSOCKET) {
      await store.sendBroadcastMessage(broadcastMessage.trim());
      setBroadcastMessage('');
      setShowBroadcastForm(false);
    }
  };

  const handleSwitchProtocol = () => {
    const newProtocol = store.currentProtocol === CommunicationProtocol.SSE 
      ? CommunicationProtocol.WEBSOCKET 
      : CommunicationProtocol.SSE;
    store.switchCommunicationProtocol(newProtocol);
  };

  return (
    <div className="collaboration-indicator">
      {/* Connection Status */}
      <div className="connection-status">
        <span 
          className="status-icon" 
          title={`${store.connectionState} (${store.currentProtocol})`}
        >
          {getConnectionStatusIcon()}
        </span>
        <button 
          className="protocol-switch"
          onClick={handleSwitchProtocol}
          title={`Switch from ${store.currentProtocol} to ${store.currentProtocol === CommunicationProtocol.SSE ? 'WebSocket' : 'SSE'}`}
        >
          {getProtocolIcon()}
        </button>
      </div>

      {/* Active Users */}
      <div className="active-users">
        <button 
          className="users-button"
          onClick={() => setShowUserList(!showUserList)}
          title={`${store.activeUsersCount} active users`}
        >
          👥 {store.activeUsersCount}
        </button>
        
        {showUserList && (
          <div className="users-dropdown">
            <div className="dropdown-header">
              <h4>Active Users</h4>
              <button 
                className="close-btn"
                onClick={() => setShowUserList(false)}
              >
                ✕
              </button>
            </div>
            <div className="users-list">
              {activeUsers.length === 0 ? (
                <div className="no-users">No other users online</div>
              ) : (
                activeUsers.map(user => (
                  <div key={user.userId} className="user-item">
                    <div className="user-info">
                      <span className="user-name">{user.name}</span>
                      <span className="user-view">{user.currentView}</span>
                    </div>
                    <div className="user-meta">
                      <span className="last-seen">
                        {formatLastSeen(user.lastSeen)}
                      </span>
                      {user.cursor && (
                        <span 
                          className="cursor-indicator" 
                          title={`Cursor at ${user.cursor.x}, ${user.cursor.y}`}
                        >
                          🖱️
                        </span>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {/* Broadcast Messages */}
      {store.currentProtocol === CommunicationProtocol.WEBSOCKET && (
        <div className="broadcast-controls">
          <button 
            className="broadcast-button"
            onClick={() => setShowBroadcastForm(!showBroadcastForm)}
            title="Send broadcast message"
          >
            📢
          </button>
          
          {showBroadcastForm && (
            <div className="broadcast-form">
              <input
                type="text"
                placeholder="Broadcast message..."
                value={broadcastMessage}
                onChange={(e) => setBroadcastMessage(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSendBroadcast()}
                autoFocus
              />
              <button onClick={handleSendBroadcast} disabled={!broadcastMessage.trim()}>
                Send
              </button>
              <button onClick={() => setShowBroadcastForm(false)}>
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {/* Recent Broadcasts Indicator */}
      {store.recentBroadcastsCount > 0 && (
        <div 
          className="recent-broadcasts"
          title={`${store.recentBroadcastsCount} recent broadcasts`}
        >
          <span className="broadcast-count">{store.recentBroadcastsCount}</span>
        </div>
      )}
    </div>
  );
});

export default CollaborationIndicator;