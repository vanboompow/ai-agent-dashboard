import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { Agent } from '../../stores/RootStore';
import './AgentRadar.css';

interface AgentRadarProps {
  agents: Agent[];
}

interface AgentPosition {
  x: number;
  y: number;
  timestamp: number;
}

interface AgentTrail {
  [agentId: string]: AgentPosition[];
}

const AgentRadar: React.FC<AgentRadarProps> = ({ agents }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [agentTrails, setAgentTrails] = useState<AgentTrail>({});
  const [zoomTransform, setZoomTransform] = useState<d3.ZoomTransform | null>(null);
  const [hoveredAgent, setHoveredAgent] = useState<Agent | null>(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  // Update agent trails when agents change
  useEffect(() => {
    const currentTime = Date.now();
    const newTrails = { ...agentTrails };
    
    agents.forEach(agent => {
      const radian = (agent.angle * Math.PI) / 180;
      const x = Math.cos(radian) * (250 * agent.distance);
      const y = Math.sin(radian) * (250 * agent.distance);
      
      if (!newTrails[agent.agentId]) {
        newTrails[agent.agentId] = [];
      }
      
      const lastPosition = newTrails[agent.agentId][newTrails[agent.agentId].length - 1];
      if (!lastPosition || 
          Math.abs(lastPosition.x - x) > 5 || 
          Math.abs(lastPosition.y - y) > 5) {
        newTrails[agent.agentId].push({ x, y, timestamp: currentTime });
        
        // Keep only last 10 positions and remove old ones (older than 30 seconds)
        newTrails[agent.agentId] = newTrails[agent.agentId]
          .filter(pos => currentTime - pos.timestamp < 30000)
          .slice(-10);
      }
    });
    
    setAgentTrails(newTrails);
  }, [agents]);
  
  const handleMouseMove = useCallback((event: MouseEvent) => {
    setMousePosition({ x: event.clientX, y: event.clientY });
  }, []);
  
  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    return () => document.removeEventListener('mousemove', handleMouseMove);
  }, [handleMouseMove]);

  useEffect(() => {
    if (!svgRef.current) return;

    const width = 600;
    const height = 600;
    const centerX = width / 2;
    const centerY = height / 2;
    const maxRadius = 250;

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);
      
    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => {
        setZoomTransform(event.transform);
        mainGroup.attr('transform', event.transform);
      });
      
    svg.call(zoom);
    
    // Main group for all content
    const mainGroup = svg.append('g');
    
    if (zoomTransform) {
      mainGroup.attr('transform', zoomTransform);
    }

    // Create radar background
    const radarGroup = mainGroup.append('g')
      .attr('transform', `translate(${centerX}, ${centerY})`);
      
    // Add sector labels
    const sectors = [
      { angle: 0, label: 'PROCESSING', color: '#00ff88' },
      { angle: 90, label: 'ANALYSIS', color: '#0088ff' },
      { angle: 180, label: 'COMMUNICATION', color: '#ff8800' },
      { angle: 270, label: 'MONITORING', color: '#ff0088' }
    ];
    
    sectors.forEach(sector => {
      const radian = (sector.angle * Math.PI) / 180;
      const labelRadius = maxRadius + 30;
      radarGroup.append('text')
        .attr('x', Math.cos(radian) * labelRadius)
        .attr('y', Math.sin(radian) * labelRadius)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', sector.color)
        .attr('font-size', '12px')
        .attr('font-weight', 'bold')
        .attr('font-family', 'JetBrains Mono')
        .text(sector.label);
    });

    // Draw concentric circles with grid labels
    const circles = [0.25, 0.5, 0.75, 1];
    const circleLabels = ['25%', '50%', '75%', '100%'];
    
    circles.forEach((ratio, index) => {
      const circle = radarGroup.append('circle')
        .attr('r', maxRadius * ratio)
        .attr('fill', 'none')
        .attr('stroke', '#00ff00')
        .attr('stroke-width', 1)
        .attr('opacity', 0.3)
        .attr('stroke-dasharray', index === circles.length - 1 ? 'none' : '5,5');
        
      // Add range labels
      radarGroup.append('text')
        .attr('x', maxRadius * ratio + 5)
        .attr('y', -5)
        .attr('fill', '#00ff00')
        .attr('font-size', '10px')
        .attr('font-family', 'JetBrains Mono')
        .attr('opacity', 0.7)
        .text(circleLabels[index]);
    });

    // Draw radial grid lines
    const gridLines = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330];
    gridLines.forEach(angle => {
      const radian = (angle * Math.PI) / 180;
      radarGroup.append('line')
        .attr('x1', 0)
        .attr('y1', 0)
        .attr('x2', Math.cos(radian) * maxRadius)
        .attr('y2', Math.sin(radian) * maxRadius)
        .attr('stroke', '#00ff00')
        .attr('stroke-width', angle % 90 === 0 ? 2 : 1)
        .attr('opacity', angle % 90 === 0 ? 0.4 : 0.15)
        .attr('stroke-dasharray', angle % 90 === 0 ? 'none' : '3,3');
    });

    // Draw sweep line with gradient (rotating)
    const defs = svg.append('defs');
    const gradient = defs.append('linearGradient')
      .attr('id', 'sweepGradient')
      .attr('x1', '0%')
      .attr('x2', '100%');
    
    gradient.append('stop')
      .attr('offset', '0%')
      .attr('stop-color', '#00ff00')
      .attr('stop-opacity', 0.8);
    
    gradient.append('stop')
      .attr('offset', '100%')
      .attr('stop-color', '#00ff00')
      .attr('stop-opacity', 0.1);
    
    const sweepGroup = radarGroup.append('g');
    
    // Create sweep fan
    const sweepFan = sweepGroup.append('path')
      .attr('d', `M 0,0 L ${maxRadius},0 A ${maxRadius},${maxRadius} 0 0,1 ${maxRadius * Math.cos(Math.PI / 6)},${maxRadius * Math.sin(Math.PI / 6)} Z`)
      .attr('fill', 'url(#sweepGradient)')
      .attr('opacity', 0.3);

    // Animate sweep
    const animateSweep = () => {
      sweepGroup
        .transition()
        .duration(6000)
        .ease(d3.easeLinear)
        .attrTween('transform', () => d3.interpolateString('rotate(0)', 'rotate(360)'))
        .on('end', animateSweep);
    };
    animateSweep();

    // Draw agent trails
    Object.entries(agentTrails).forEach(([agentId, trail]) => {
      if (trail.length < 2) return;
      
      const agent = agents.find(a => a.agentId === agentId);
      if (!agent) return;
      
      const line = d3.line<AgentPosition>()
        .x(d => d.x)
        .y(d => d.y)
        .curve(d3.curveCardinal.tension(0.5));
      
      radarGroup.append('path')
        .datum(trail)
        .attr('class', 'agent-trail')
        .attr('d', line)
        .attr('fill', 'none')
        .attr('stroke', () => {
          switch(agent.status) {
            case 'working': return '#00ff00';
            case 'idle': return '#ffff00';
            case 'error': return '#ff0000';
            default: return '#888888';
          }
        })
        .attr('stroke-width', 2)
        .attr('opacity', 0.4)
        .attr('stroke-dasharray', '3,3');
        
      // Add trail fade effect
      trail.forEach((pos, index) => {
        const age = (Date.now() - pos.timestamp) / 30000; // normalize to 0-1
        const opacity = Math.max(0.1, 1 - age);
        
        radarGroup.append('circle')
          .attr('cx', pos.x)
          .attr('cy', pos.y)
          .attr('r', 2)
          .attr('fill', agent.status === 'working' ? '#00ff00' : '#888888')
          .attr('opacity', opacity * 0.5);
      });
    });
    
    // Draw agents with smooth transitions
    const agentGroups = radarGroup.selectAll('.agent')
      .data(agents, (d: any) => d.agentId);
      
    const agentEnter = agentGroups.enter()
      .append('g')
      .attr('class', 'agent')
      .attr('transform', d => {
        const radian = (d.angle * Math.PI) / 180;
        const x = Math.cos(radian) * (maxRadius * d.distance);
        const y = Math.sin(radian) * (maxRadius * d.distance);
        return `translate(${x}, ${y})`;
      })
      .style('opacity', 0);
      
    const agentUpdate = agentEnter.merge(agentGroups as any);
    
    // Smooth transition to new positions
    agentUpdate.transition()
      .duration(500)
      .ease(d3.easeCircle)
      .attr('transform', d => {
        const radian = (d.angle * Math.PI) / 180;
        const x = Math.cos(radian) * (maxRadius * d.distance);
        const y = Math.sin(radian) * (maxRadius * d.distance);
        return `translate(${x}, ${y})`;
      })
      .style('opacity', 1);
      
    agentGroups.exit()
      .transition()
      .duration(300)
      .style('opacity', 0)
      .remove();

    // Agent outer ring (pulsing effect)
    agentEnter.append('circle')
      .attr('class', 'agent-pulse-ring')
      .attr('r', 12)
      .attr('fill', 'none')
      .attr('stroke-width', 2)
      .attr('opacity', 0);
      
    // Agent dots with enhanced styling
    agentEnter.append('circle')
      .attr('class', 'agent-dot')
      .attr('r', 8)
      .attr('stroke-width', 2)
      .attr('stroke', '#000000');
      
    // Update agent styling
    agentUpdate.select('.agent-dot')
      .attr('fill', d => {
        switch(d.status) {
          case 'working': return '#00ff00';
          case 'idle': return '#ffff00';
          case 'error': return '#ff0000';
          default: return '#888888';
        }
      });
      
    agentUpdate.select('.agent-pulse-ring')
      .attr('stroke', d => {
        switch(d.status) {
          case 'working': return '#00ff00';
          case 'idle': return '#ffff00';
          case 'error': return '#ff0000';
          default: return '#888888';
        }
      });
      
    // Add pulsing animation for working agents
    agentUpdate.filter(d => d.status === 'working')
      .select('.agent-pulse-ring')
      .transition()
      .duration(1000)
      .ease(d3.easeCircle)
      .attr('r', 20)
      .attr('opacity', 0.7)
      .transition()
      .duration(1000)
      .attr('r', 12)
      .attr('opacity', 0)
      .on('end', function() {
        d3.select(this).transition().duration(0).attr('r', 12);
      });

    // Agent labels
    agentEnter.append('text')
      .attr('class', 'agent-label')
      .attr('x', 0)
      .attr('y', -18)
      .attr('text-anchor', 'middle')
      .attr('fill', '#00ff00')
      .attr('font-size', '10px')
      .attr('font-weight', 'bold')
      .attr('font-family', 'JetBrains Mono')
      .attr('text-shadow', '0 0 3px #000000');
      
    agentUpdate.select('.agent-label')
      .text(d => d.agentId);
      
    // Agent status indicator
    agentEnter.append('text')
      .attr('class', 'agent-status')
      .attr('x', 0)
      .attr('y', 25)
      .attr('text-anchor', 'middle')
      .attr('font-size', '8px')
      .attr('font-family', 'JetBrains Mono')
      .attr('text-shadow', '0 0 3px #000000');
      
    agentUpdate.select('.agent-status')
      .attr('fill', d => {
        switch(d.status) {
          case 'working': return '#00ff00';
          case 'idle': return '#ffff00';
          case 'error': return '#ff0000';
          default: return '#888888';
        }
      })
      .text(d => d.status.toUpperCase());

    // Enhanced interaction
    agentUpdate
      .style('cursor', 'pointer')
      .on('mouseenter', (event, d) => {
        setHoveredAgent(d);
        
        // Highlight agent
        d3.select(event.currentTarget)
          .select('.agent-dot')
          .transition()
          .duration(150)
          .attr('r', 12)
          .attr('stroke-width', 3);
          
        // Show connection lines to related agents
        if (d.currentTask) {
          const relatedAgents = agents.filter(a => a.taskCategory === d.taskCategory && a.agentId !== d.agentId);
          relatedAgents.forEach(relatedAgent => {
            const radian1 = (d.angle * Math.PI) / 180;
            const x1 = Math.cos(radian1) * (maxRadius * d.distance);
            const y1 = Math.sin(radian1) * (maxRadius * d.distance);
            
            const radian2 = (relatedAgent.angle * Math.PI) / 180;
            const x2 = Math.cos(radian2) * (maxRadius * relatedAgent.distance);
            const y2 = Math.sin(radian2) * (maxRadius * relatedAgent.distance);
            
            radarGroup.append('line')
              .attr('class', 'connection-line')
              .attr('x1', x1)
              .attr('y1', y1)
              .attr('x2', x2)
              .attr('y2', y2)
              .attr('stroke', '#00ffff')
              .attr('stroke-width', 1)
              .attr('opacity', 0)
              .attr('stroke-dasharray', '2,2')
              .transition()
              .duration(300)
              .attr('opacity', 0.6);
          });
        }
      })
      .on('mouseleave', (event, d) => {
        setHoveredAgent(null);
        
        // Reset agent appearance
        d3.select(event.currentTarget)
          .select('.agent-dot')
          .transition()
          .duration(150)
          .attr('r', 8)
          .attr('stroke-width', 2);
          
        // Remove connection lines
        radarGroup.selectAll('.connection-line')
          .transition()
          .duration(200)
          .attr('opacity', 0)
          .remove();
      })
      .on('click', (event, d) => {
        console.log('Agent clicked:', d);
        // Could dispatch action to focus on this agent
      });

    // Center hub with system status
    const centerGroup = radarGroup.append('g')
      .attr('class', 'center-hub');
      
    centerGroup.append('circle')
      .attr('r', 15)
      .attr('fill', '#000000')
      .attr('stroke', '#00ff00')
      .attr('stroke-width', 2)
      .attr('opacity', 0.8);
      
    centerGroup.append('circle')
      .attr('r', 8)
      .attr('fill', '#00ff00')
      .attr('opacity', 0.6);
      
    centerGroup.append('text')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('fill', '#00ff00')
      .attr('font-size', '8px')
      .attr('font-weight', 'bold')
      .attr('font-family', 'JetBrains Mono')
      .text('HUB');
      
    // System status ring
    const systemStatus = agents.filter(a => a.status === 'working').length / Math.max(agents.length, 1);
    const statusArc = d3.arc()
      .innerRadius(18)
      .outerRadius(22)
      .startAngle(0)
      .endAngle(systemStatus * 2 * Math.PI);
      
    centerGroup.append('path')
      .attr('d', statusArc)
      .attr('fill', systemStatus > 0.7 ? '#00ff00' : systemStatus > 0.3 ? '#ffff00' : '#ff0000')
      .attr('opacity', 0.8);

  }, [agents, agentTrails, zoomTransform]);

  return (
    <div className="radar-wrapper">
      <svg ref={svgRef}></svg>
      
      {/* Enhanced Tooltip */}
      {hoveredAgent && (
        <div 
          ref={tooltipRef}
          className="agent-tooltip"
          style={{
            position: 'fixed',
            left: mousePosition.x + 15,
            top: mousePosition.y - 10,
            pointerEvents: 'none',
            zIndex: 1000
          }}
        >
          <div className="tooltip-header">
            <span className="tooltip-id">{hoveredAgent.agentId}</span>
            <span className={`tooltip-status status-${hoveredAgent.status}`}>
              {hoveredAgent.status.toUpperCase()}
            </span>
          </div>
          <div className="tooltip-body">
            <div className="tooltip-row">
              <span className="tooltip-label">Category:</span>
              <span className="tooltip-value">{hoveredAgent.taskCategory}</span>
            </div>
            <div className="tooltip-row">
              <span className="tooltip-label">Task:</span>
              <span className="tooltip-value">{hoveredAgent.currentTask || 'None'}</span>
            </div>
            <div className="tooltip-row">
              <span className="tooltip-label">Runtime:</span>
              <span className="tooltip-value">{hoveredAgent.elapsedTime}s</span>
            </div>
            <div className="tooltip-row">
              <span className="tooltip-label">Position:</span>
              <span className="tooltip-value">
                {hoveredAgent.angle.toFixed(1)}° / {(hoveredAgent.distance * 100).toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      )}
      
      {/* Zoom Controls */}
      <div className="radar-controls">
        <button 
          className="zoom-btn"
          onClick={() => {
            const svg = d3.select(svgRef.current!);
            svg.transition().duration(300).call(
              (svg.property('__zoom') as any).transform,
              d3.zoomIdentity.scale(0.5)
            );
          }}
          title="Zoom Out"
        >
          −
        </button>
        <button 
          className="zoom-btn"
          onClick={() => {
            const svg = d3.select(svgRef.current!);
            svg.transition().duration(300).call(
              (svg.property('__zoom') as any).transform,
              d3.zoomIdentity
            );
          }}
          title="Reset Zoom"
        >
          ⌂
        </button>
        <button 
          className="zoom-btn"
          onClick={() => {
            const svg = d3.select(svgRef.current!);
            svg.transition().duration(300).call(
              (svg.property('__zoom') as any).transform,
              d3.zoomIdentity.scale(1.5)
            );
          }}
          title="Zoom In"
        >
          +
        </button>
      </div>
      
      {/* Legend */}
      <div className="radar-legend">
        <div className="legend-item">
          <div className="legend-dot working"></div>
          <span>Working</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot idle"></div>
          <span>Idle</span>
        </div>
        <div className="legend-item">
          <div className="legend-dot error"></div>
          <span>Error</span>
        </div>
        <div className="legend-item">
          <div className="legend-trail"></div>
          <span>Movement Trail</span>
        </div>
      </div>
    </div>
  );
};

export default AgentRadar;