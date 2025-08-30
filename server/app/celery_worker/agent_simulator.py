"""
Agent Simulator for realistic AI agent behavior simulation

This module simulates different AI agent types with realistic processing patterns,
resource consumption, costs, and failure scenarios for testing and development.
"""

import random
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Supported AI agent types with their characteristics"""
    GPT_4 = "gpt-4"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_3_5_TURBO = "gpt-3.5-turbo"
    CLAUDE_3_OPUS = "claude-3-opus"
    CLAUDE_3_SONNET = "claude-3-sonnet"
    CLAUDE_3_HAIKU = "claude-3-haiku"
    GEMINI_PRO = "gemini-pro"
    GEMINI_ULTRA = "gemini-ultra"
    LLAMA_2_70B = "llama-2-70b"
    LLAMA_2_13B = "llama-2-13b"
    MISTRAL_LARGE = "mistral-large"
    MISTRAL_MEDIUM = "mistral-medium"


@dataclass
class AgentProfile:
    """Profile containing agent characteristics and performance metrics"""
    name: str
    speed_multiplier: float  # Base processing speed (higher = faster)
    token_rate: Tuple[int, int]  # Min/max tokens per step
    cost_per_1k_tokens: float  # USD cost per 1000 tokens
    failure_rate: float  # Probability of failure per step (0-1)
    memory_intensive: bool  # Whether agent uses more memory
    specialization: List[str]  # Areas of specialization
    max_complexity: int  # Maximum complexity the agent can handle (1-10)


class AgentSimulator:
    """
    Simulates realistic AI agent behavior with different characteristics
    """
    
    # Agent profiles with realistic characteristics
    AGENT_PROFILES = {
        AgentType.GPT_4: AgentProfile(
            name="GPT-4",
            speed_multiplier=0.8,  # Slower but more thorough
            token_rate=(200, 800),
            cost_per_1k_tokens=0.03,  # $30 per 1M tokens
            failure_rate=0.02,  # 2% failure rate
            memory_intensive=True,
            specialization=["reasoning", "analysis", "creative_writing"],
            max_complexity=10
        ),
        AgentType.GPT_4_TURBO: AgentProfile(
            name="GPT-4 Turbo",
            speed_multiplier=1.2,  # Faster variant
            token_rate=(300, 1000),
            cost_per_1k_tokens=0.01,  # $10 per 1M tokens
            failure_rate=0.03,
            memory_intensive=True,
            specialization=["reasoning", "analysis", "speed"],
            max_complexity=10
        ),
        AgentType.GPT_3_5_TURBO: AgentProfile(
            name="GPT-3.5 Turbo",
            speed_multiplier=1.5,  # Fast and lightweight
            token_rate=(400, 1200),
            cost_per_1k_tokens=0.001,  # $1 per 1M tokens
            failure_rate=0.05,
            memory_intensive=False,
            specialization=["general", "speed"],
            max_complexity=7
        ),
        AgentType.CLAUDE_3_OPUS: AgentProfile(
            name="Claude 3 Opus",
            speed_multiplier=0.7,  # Thoughtful and careful
            token_rate=(150, 600),
            cost_per_1k_tokens=0.075,  # $75 per 1M tokens
            failure_rate=0.01,  # Very reliable
            memory_intensive=True,
            specialization=["analysis", "safety", "reasoning"],
            max_complexity=10
        ),
        AgentType.CLAUDE_3_SONNET: AgentProfile(
            name="Claude 3 Sonnet",
            speed_multiplier=1.0,  # Balanced performance
            token_rate=(250, 700),
            cost_per_1k_tokens=0.015,  # $15 per 1M tokens
            failure_rate=0.02,
            memory_intensive=False,
            specialization=["general", "balanced"],
            max_complexity=8
        ),
        AgentType.CLAUDE_3_HAIKU: AgentProfile(
            name="Claude 3 Haiku",
            speed_multiplier=2.0,  # Very fast
            token_rate=(500, 1500),
            cost_per_1k_tokens=0.0025,  # $2.5 per 1M tokens
            failure_rate=0.03,
            memory_intensive=False,
            specialization=["speed", "concise"],
            max_complexity=6
        ),
        AgentType.GEMINI_PRO: AgentProfile(
            name="Gemini Pro",
            speed_multiplier=1.1,
            token_rate=(300, 900),
            cost_per_1k_tokens=0.005,  # $5 per 1M tokens
            failure_rate=0.025,
            memory_intensive=False,
            specialization=["multimodal", "general"],
            max_complexity=8
        ),
        AgentType.GEMINI_ULTRA: AgentProfile(
            name="Gemini Ultra",
            speed_multiplier=0.9,
            token_rate=(200, 700),
            cost_per_1k_tokens=0.02,  # $20 per 1M tokens
            failure_rate=0.015,
            memory_intensive=True,
            specialization=["reasoning", "multimodal"],
            max_complexity=10
        ),
        AgentType.LLAMA_2_70B: AgentProfile(
            name="Llama 2 70B",
            speed_multiplier=0.6,  # Large model, slower
            token_rate=(100, 400),
            cost_per_1k_tokens=0.0,  # Open source, no direct cost
            failure_rate=0.04,
            memory_intensive=True,
            specialization=["open_source", "reasoning"],
            max_complexity=8
        ),
        AgentType.LLAMA_2_13B: AgentProfile(
            name="Llama 2 13B",
            speed_multiplier=1.3,  # Smaller, faster
            token_rate=(200, 600),
            cost_per_1k_tokens=0.0,  # Open source, no direct cost
            failure_rate=0.06,
            memory_intensive=False,
            specialization=["open_source", "speed"],
            max_complexity=6
        ),
        AgentType.MISTRAL_LARGE: AgentProfile(
            name="Mistral Large",
            speed_multiplier=0.9,
            token_rate=(180, 650),
            cost_per_1k_tokens=0.008,  # $8 per 1M tokens
            failure_rate=0.02,
            memory_intensive=True,
            specialization=["reasoning", "multilingual"],
            max_complexity=9
        ),
        AgentType.MISTRAL_MEDIUM: AgentProfile(
            name="Mistral Medium",
            speed_multiplier=1.4,
            token_rate=(300, 800),
            cost_per_1k_tokens=0.0027,  # $2.7 per 1M tokens
            failure_rate=0.035,
            memory_intensive=False,
            specialization=["general", "multilingual"],
            max_complexity=7
        ),
    }
    
    def __init__(self, agent_type: str):
        """
        Initialize agent simulator with specific agent type
        
        Args:
            agent_type: String identifier for agent type
        """
        self.agent_type_str = agent_type
        
        # Try to match agent type string to enum
        try:
            self.agent_type = AgentType(agent_type.lower())
        except ValueError:
            # Default to GPT-3.5 if unknown type
            logger.warning(f"Unknown agent type: {agent_type}, defaulting to GPT-3.5 Turbo")
            self.agent_type = AgentType.GPT_3_5_TURBO
        
        self.profile = self.AGENT_PROFILES[self.agent_type]
        self.session_id = random.randint(1000, 9999)
        
        logger.info(f"Initialized {self.profile.name} simulator (session {self.session_id})")
    
    def calculate_steps(self, complexity: int) -> int:
        """
        Calculate number of processing steps based on task complexity and agent type
        
        Args:
            complexity: Task complexity (1-10 scale)
            
        Returns:
            Number of processing steps required
        """
        # Clamp complexity to agent's maximum capability
        effective_complexity = min(complexity, self.profile.max_complexity)
        
        # Base steps calculation with some randomness
        base_steps = int(effective_complexity * random.uniform(8, 15))
        
        # Adjust for agent speed (slower agents need more steps for same quality)
        adjusted_steps = int(base_steps / self.profile.speed_multiplier)
        
        # Ensure minimum steps
        return max(adjusted_steps, 5)
    
    def process_step(self, step: int, total_steps: int, complexity: int) -> Dict[str, Any]:
        """
        Simulate processing a single step with agent-specific behavior
        
        Args:
            step: Current step number (0-based)
            total_steps: Total number of steps
            complexity: Task complexity
            
        Returns:
            Dictionary with step results
        """
        progress = (step + 1) / total_steps
        
        # Generate tokens for this step
        min_tokens, max_tokens = self.profile.token_rate
        tokens = random.randint(min_tokens, max_tokens)
        
        # Adjust tokens based on complexity and progress
        complexity_multiplier = 1.0 + (complexity / 10.0)
        tokens = int(tokens * complexity_multiplier)
        
        # Calculate processing duration
        base_duration = random.uniform(0.1, 0.8)
        
        # Slower agents take longer per step
        duration = base_duration / self.profile.speed_multiplier
        
        # Add complexity-based delay
        complexity_delay = (complexity / 10.0) * 0.5
        duration += complexity_delay
        
        # Memory-intensive agents have occasional pauses
        if self.profile.memory_intensive and random.random() < 0.1:
            duration += random.uniform(0.2, 1.0)
        
        # Generate realistic status messages
        status = self._generate_status_message(step, total_steps, progress)
        
        # Check for simulated failures
        should_fail = random.random() < self.profile.failure_rate
        
        if should_fail:
            error_message = self._generate_error_message()
            logger.warning(f"{self.profile.name} simulated failure at step {step}: {error_message}")
        
        return {
            'tokens': tokens,
            'duration': duration,
            'status': status,
            'progress': progress,
            'should_fail': should_fail,
            'error_message': error_message if should_fail else None,
            'agent_type': self.profile.name,
            'step': step,
            'total_steps': total_steps
        }
    
    def calculate_cost(self, total_tokens: int) -> float:
        """
        Calculate cost based on tokens processed
        
        Args:
            total_tokens: Total tokens processed
            
        Returns:
            Cost in USD
        """
        return (total_tokens / 1000.0) * self.profile.cost_per_1k_tokens
    
    def generate_final_result(self, tokens_processed: int, execution_time: float) -> Dict[str, Any]:
        """
        Generate final task result with agent-specific metrics
        
        Args:
            tokens_processed: Total tokens processed during task
            execution_time: Total execution time in seconds
            
        Returns:
            Dictionary with final results and metrics
        """
        cost = self.calculate_cost(tokens_processed)
        
        # Calculate performance metrics
        tokens_per_second = tokens_processed / max(execution_time, 1)
        
        # Agent-specific quality scores (simulate variation)
        quality_base = {
            AgentType.GPT_4: 0.95,
            AgentType.GPT_4_TURBO: 0.92,
            AgentType.GPT_3_5_TURBO: 0.85,
            AgentType.CLAUDE_3_OPUS: 0.96,
            AgentType.CLAUDE_3_SONNET: 0.90,
            AgentType.CLAUDE_3_HAIKU: 0.82,
            AgentType.GEMINI_PRO: 0.88,
            AgentType.GEMINI_ULTRA: 0.94,
            AgentType.LLAMA_2_70B: 0.87,
            AgentType.LLAMA_2_13B: 0.80,
            AgentType.MISTRAL_LARGE: 0.91,
            AgentType.MISTRAL_MEDIUM: 0.83,
        }.get(self.agent_type, 0.85)
        
        quality_score = quality_base + random.uniform(-0.05, 0.05)
        quality_score = max(0.0, min(1.0, quality_score))
        
        # Generate agent-specific insights
        insights = self._generate_insights(tokens_processed, execution_time)
        
        return {
            'tokens_used': tokens_processed,
            'cost_usd': round(cost, 4),
            'tokens_per_second': round(tokens_per_second, 2),
            'quality_score': round(quality_score, 3),
            'agent_profile': {
                'name': self.profile.name,
                'specialization': self.profile.specialization,
                'speed_multiplier': self.profile.speed_multiplier,
                'cost_per_1k_tokens': self.profile.cost_per_1k_tokens
            },
            'performance_metrics': {
                'efficiency_score': round(tokens_per_second * quality_score, 2),
                'cost_efficiency': round(quality_score / max(cost, 0.001), 2),
                'session_id': self.session_id
            },
            'insights': insights
        }
    
    def _generate_status_message(self, step: int, total_steps: int, progress: float) -> str:
        """Generate realistic status messages based on progress and agent type"""
        
        phase_messages = {
            "initialization": [
                "Initializing neural networks...",
                "Loading model weights...",
                "Preparing context window...",
                "Calibrating parameters...",
            ],
            "early": [
                "Analyzing input tokens...",
                "Building context understanding...",
                "Processing initial patterns...",
                "Establishing reasoning framework...",
            ],
            "middle": [
                "Deep pattern analysis in progress...",
                "Synthesizing intermediate results...",
                "Performing multi-layer reasoning...",
                "Evaluating multiple hypotheses...",
                "Cross-referencing knowledge base...",
            ],
            "late": [
                "Finalizing output generation...",
                "Optimizing response quality...",
                "Performing final validation...",
                "Compiling results...",
                "Quality assurance check...",
            ],
            "completion": [
                "Finalizing output...",
                "Preparing response delivery...",
                "Completing quality checks...",
                "Ready for output...",
            ]
        }
        
        # Add agent-specific status variations
        if self.agent_type in [AgentType.CLAUDE_3_OPUS, AgentType.CLAUDE_3_SONNET, AgentType.CLAUDE_3_HAIKU]:
            phase_messages["middle"].extend([
                "Considering safety implications...",
                "Ensuring ethical alignment...",
                "Evaluating potential harms...",
            ])
        
        if self.agent_type in [AgentType.GEMINI_PRO, AgentType.GEMINI_ULTRA]:
            phase_messages["middle"].extend([
                "Processing multimodal inputs...",
                "Integrating visual context...",
                "Analyzing multimedia patterns...",
            ])
        
        if "llama" in self.agent_type_str.lower():
            phase_messages["middle"].extend([
                "Open-source inference running...",
                "Community model processing...",
                "Distributed computation active...",
            ])
        
        # Determine current phase
        if progress < 0.1:
            phase = "initialization"
        elif progress < 0.3:
            phase = "early"
        elif progress < 0.8:
            phase = "middle"
        elif progress < 0.95:
            phase = "late"
        else:
            phase = "completion"
        
        messages = phase_messages[phase]
        base_message = random.choice(messages)
        
        # Add step information occasionally
        if random.random() < 0.3:
            return f"{base_message} (Step {step + 1}/{total_steps})"
        
        return base_message
    
    def _generate_error_message(self) -> str:
        """Generate realistic error messages for simulated failures"""
        
        error_types = [
            "Rate limit exceeded, retrying...",
            "Context window overflow, chunking required",
            "Token limit reached, truncating input",
            "Model overload, queuing request...",
            "Network timeout, attempting reconnection",
            "Memory allocation error, optimizing...",
            "Inference engine busy, scheduling retry",
            "API quota exceeded, waiting for reset",
            "Processing timeout, reducing complexity",
            "Resource constraint, optimizing parameters",
        ]
        
        # Add agent-specific error scenarios
        if self.profile.memory_intensive:
            error_types.extend([
                "Memory pressure detected, garbage collecting...",
                "Large model loading timeout",
                "GPU memory fragmentation, defragmenting...",
            ])
        
        if self.agent_type in [AgentType.LLAMA_2_70B, AgentType.LLAMA_2_13B]:
            error_types.extend([
                "Local inference engine restart required",
                "Model checkpoint loading failed",
                "Distributed processing node unavailable",
            ])
        
        return random.choice(error_types)
    
    def _generate_insights(self, tokens_processed: int, execution_time: float) -> List[str]:
        """Generate agent-specific insights about the task execution"""
        
        insights = []
        
        # Performance insights
        if execution_time > 30:
            insights.append(f"Long execution time ({execution_time:.1f}s) - consider task chunking")
        elif execution_time < 5:
            insights.append("Efficient processing - well within optimal parameters")
        
        # Token usage insights
        if tokens_processed > 10000:
            insights.append("High token usage - monitor cost implications")
        elif tokens_processed < 1000:
            insights.append("Low token usage - task may be underutilized")
        
        # Agent-specific insights
        if self.agent_type == AgentType.GPT_4:
            insights.append("GPT-4 provided high-quality reasoning with thorough analysis")
        elif self.agent_type == AgentType.CLAUDE_3_OPUS:
            insights.append("Claude Opus delivered careful, safety-conscious processing")
        elif self.agent_type == AgentType.GPT_3_5_TURBO:
            insights.append("GPT-3.5 Turbo provided cost-effective, rapid processing")
        elif "gemini" in self.agent_type_str.lower():
            insights.append("Gemini model leveraged multimodal capabilities effectively")
        elif "llama" in self.agent_type_str.lower():
            insights.append("Open-source Llama model provided transparent processing")
        
        # Specialization insights
        if "reasoning" in self.profile.specialization:
            insights.append("Agent's reasoning specialization was well-utilized")
        if "speed" in self.profile.specialization:
            insights.append("High-speed processing specialization optimized performance")
        
        return insights
    
    @classmethod
    def get_available_agents(cls) -> List[Dict[str, Any]]:
        """
        Get list of all available agent types with their characteristics
        
        Returns:
            List of dictionaries containing agent information
        """
        agents = []
        for agent_type, profile in cls.AGENT_PROFILES.items():
            agents.append({
                'type': agent_type.value,
                'name': profile.name,
                'speed_multiplier': profile.speed_multiplier,
                'cost_per_1k_tokens': profile.cost_per_1k_tokens,
                'specialization': profile.specialization,
                'max_complexity': profile.max_complexity,
                'failure_rate': profile.failure_rate,
                'memory_intensive': profile.memory_intensive
            })
        
        return sorted(agents, key=lambda x: x['cost_per_1k_tokens'])
    
    @classmethod
    def recommend_agent_for_task(cls, complexity: int, budget_usd: float = None, 
                                speed_priority: bool = False) -> str:
        """
        Recommend best agent for a given task based on requirements
        
        Args:
            complexity: Task complexity (1-10)
            budget_usd: Budget constraint in USD (optional)
            speed_priority: Whether speed is prioritized over quality
            
        Returns:
            Recommended agent type string
        """
        suitable_agents = []
        
        for agent_type, profile in cls.AGENT_PROFILES.items():
            if profile.max_complexity >= complexity:
                suitable_agents.append((agent_type, profile))
        
        if not suitable_agents:
            # Fallback to most capable agent
            return AgentType.CLAUDE_3_OPUS.value
        
        if speed_priority:
            # Sort by speed (higher speed_multiplier = faster)
            suitable_agents.sort(key=lambda x: x[1].speed_multiplier, reverse=True)
        else:
            # Sort by capability and quality (lower failure rate = better)
            suitable_agents.sort(key=lambda x: (x[1].max_complexity, -x[1].failure_rate), reverse=True)
        
        # Filter by budget if specified
        if budget_usd:
            # Estimate 5000 tokens average per task
            estimated_tokens = 5000
            affordable_agents = [
                (agent_type, profile) for agent_type, profile in suitable_agents
                if (estimated_tokens / 1000.0) * profile.cost_per_1k_tokens <= budget_usd
            ]
            if affordable_agents:
                suitable_agents = affordable_agents
        
        return suitable_agents[0][0].value


# Utility functions for testing and development
def run_agent_comparison(task_complexity: int = 5, num_trials: int = 3) -> Dict[str, Any]:
    """
    Run a comparison test of different agents on the same task
    
    Args:
        task_complexity: Task complexity to test (1-10)
        num_trials: Number of trials per agent
        
    Returns:
        Dictionary with comparison results
    """
    results = {}
    
    for agent_type in [AgentType.GPT_4, AgentType.GPT_3_5_TURBO, 
                       AgentType.CLAUDE_3_SONNET, AgentType.GEMINI_PRO]:
        
        agent_results = {
            'total_cost': 0,
            'total_time': 0,
            'total_tokens': 0,
            'quality_scores': [],
            'failures': 0
        }
        
        for trial in range(num_trials):
            simulator = AgentSimulator(agent_type.value)
            
            start_time = time.time()
            steps = simulator.calculate_steps(task_complexity)
            tokens_processed = 0
            failed = False
            
            for step in range(steps):
                step_result = simulator.process_step(step, steps, task_complexity)
                tokens_processed += step_result['tokens']
                
                if step_result['should_fail']:
                    failed = True
                    break
                
                time.sleep(step_result['duration'])
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            if not failed:
                final_result = simulator.generate_final_result(tokens_processed, execution_time)
                agent_results['total_cost'] += final_result['cost_usd']
                agent_results['total_tokens'] += final_result['tokens_used']
                agent_results['quality_scores'].append(final_result['quality_score'])
            else:
                agent_results['failures'] += 1
            
            agent_results['total_time'] += execution_time
        
        # Calculate averages
        successful_trials = num_trials - agent_results['failures']
        if successful_trials > 0:
            results[agent_type.value] = {
                'average_cost': agent_results['total_cost'] / successful_trials,
                'average_time': agent_results['total_time'] / num_trials,
                'average_tokens': agent_results['total_tokens'] / successful_trials,
                'average_quality': sum(agent_results['quality_scores']) / len(agent_results['quality_scores']),
                'failure_rate': agent_results['failures'] / num_trials,
                'successful_trials': successful_trials
            }
    
    return results


if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.INFO)
    
    # Test individual agent
    simulator = AgentSimulator("gpt-4")
    print(f"Available agents: {len(AgentSimulator.get_available_agents())}")
    print(f"Recommended for complex task: {AgentSimulator.recommend_agent_for_task(9)}")
    print(f"Recommended for speed: {AgentSimulator.recommend_agent_for_task(5, speed_priority=True)}")
    
    # Run comparison test
    print("\nRunning agent comparison test...")
    comparison = run_agent_comparison(task_complexity=6, num_trials=2)
    for agent, results in comparison.items():
        print(f"{agent}: ${results['average_cost']:.4f}, {results['average_time']:.2f}s, "
              f"quality: {results['average_quality']:.3f}")