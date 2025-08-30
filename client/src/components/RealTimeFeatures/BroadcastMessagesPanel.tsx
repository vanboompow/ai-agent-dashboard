/**
 * Broadcast Messages Panel - Display system-wide broadcast messages
 */
import React, { useState } from 'react';
import { observer } from 'mobx-react-lite';
import { useStore } from '../../stores/useStore';
import { CommunicationProtocol } from '../../services/CommunicationManager';
import './RealTimeFeatures.css';

interface BroadcastMessagesPanelProps {
  maxVisible?: number;
  showTimestamps?: boolean;
}

const BroadcastMessagesPanel: React.FC<BroadcastMessagesPanelProps> = observer(({ 
  maxVisible = 20, 
  showTimestamps = true 
}) => {
  const store = useStore();
  const [newMessage, setNewMessage] = useState('');
  const [messageType, setMessageType] = useState('info');

  const visibleMessages = store.collaboration.broadcastMessages.slice(0, maxVisible);

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString();
  };

  const getMessageIcon = (type: string) => {
    switch (type) {
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'success': return '✅';
      case 'announcement': return '📢';
      case 'info':
      default: return 'ℹ️';
    }
  };

  const getMessageClass = (type: string) => {
    return `broadcast-message message-${type}`;
  };

  const handleSendMessage = async () => {
    if (newMessage.trim() && store.currentProtocol === CommunicationProtocol.WEBSOCKET) {
      await store.sendBroadcastMessage(newMessage.trim(), messageType);
      setNewMessage('');
    }
  };

  const canSendMessages = store.currentProtocol === CommunicationProtocol.WEBSOCKET && 
                         store.connectionState === 'CONNECTED';

  return (
    <div className="broadcast-messages-panel">
      <div className="panel-header">
        <h3>
          Broadcast Messages
          {store.recentBroadcastsCount > 0 && (
            <span className="badge badge-info">{store.recentBroadcastsCount} recent</span>
          )}
        </h3>
        <div className="panel-controls">
          {store.collaboration.broadcastMessages.length > 0 && (
            <button 
              className="btn btn-sm btn-outline-secondary"
              onClick={() => store.clearBroadcastMessages()}
              title="Clear all messages"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Send Message Form (WebSocket only) */}
      {canSendMessages && (
        <div className="send-message-form">
          <div className="message-input-group">
            <select 
              value={messageType}
              onChange={(e) => setMessageType(e.target.value)}
              className="message-type-select"
            >
              <option value="info">Info</option>
              <option value="announcement">Announcement</option>
              <option value="warning">Warning</option>
              <option value="success">Success</option>
              <option value="error">Error</option>
            </select>
            
            <input
              type="text"
              placeholder="Broadcast message to all users..."
              value={newMessage}
              onChange={(e) => setNewMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
              className="message-input"
            />
            
            <button 
              onClick={handleSendMessage}
              disabled={!newMessage.trim()}
              className="send-button"
              title="Send broadcast message"
            >
              📢 Send
            </button>
          </div>
        </div>
      )}

      {!canSendMessages && store.currentProtocol === CommunicationProtocol.SSE && (
        <div className="protocol-notice">
          <span>📡 Switch to WebSocket for bidirectional messaging</span>
        </div>
      )}

      {/* Messages List */}
      <div className="messages-container">
        {visibleMessages.length === 0 ? (
          <div className="no-messages">
            <span>📭 No broadcast messages</span>
          </div>
        ) : (
          visibleMessages.map((message) => (
            <div key={message.id} className={getMessageClass(message.type)}>
              <div className="message-header">
                <span className="message-icon">{getMessageIcon(message.type)}</span>
                <span className="message-type">{message.type.toUpperCase()}</span>
                {showTimestamps && (
                  <span className="message-timestamp">
                    {formatTimestamp(message.timestamp)}
                  </span>
                )}
              </div>
              
              <div className="message-content">
                {message.message}
              </div>
            </div>
          ))
        )}
      </div>

      {store.collaboration.broadcastMessages.length > maxVisible && (
        <div className="more-messages">
          +{store.collaboration.broadcastMessages.length - maxVisible} older messages
        </div>
      )}
    </div>
  );
});

export default BroadcastMessagesPanel;