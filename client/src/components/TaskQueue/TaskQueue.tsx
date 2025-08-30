import React from 'react';
import { Task } from '../../stores/RootStore';
import './TaskQueue.css';

interface TaskQueueProps {
  tasks: Task[];
}

const TaskQueue: React.FC<TaskQueueProps> = ({ tasks }) => {
  const getStatusBadgeClass = (status: string) => {
    switch(status) {
      case 'working': return 'status-working';
      case 'pending': return 'status-pending';
      case 'error': return 'status-error';
      default: return '';
    }
  };

  return (
    <div className="task-queue">
      <div className="task-header">
        <span>SECTOR</span>
        <span>WORK ORDER</span>
        <span>TPS</span>
        <span>TIME</span>
      </div>
      <div className="task-list">
        {tasks.map((task) => (
          <div key={task.task_id} className="task-item">
            <span className="task-sector">
              <span className={`status-badge ${getStatusBadgeClass(task.status)}`}>
                {task.sector}
              </span>
            </span>
            <span className="task-description">{task.description}</span>
            <span className="task-tps">{task.tps || '-'}</span>
            <span className="task-time">{task.time_elapsed || '-'}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TaskQueue;