"""
TeamBuilder: AI-powered team composition engine.

Analyzes research problems and suggests optimal virtual lab team configurations.
LLM calls are abstracted via a callable `llm_func` for easy mocking in tests.
When no llm_func is provided, uses template-based heuristics.
"""

import json
import re
from typing import Callable, Dict, List, Optional

from app.schemas.onboarding import (
    AgentSuggestion,
    ChatMessage,
    DomainAnalysis,
    MirrorConfig,
    TeamSuggestion,
)
from app.core.lang_detect import language_instruction

# ==================== System Prompts ====================

ANALYZER_PROMPT = """You are a scientific research advisor helping to assemble a virtual lab team.

The user will describe a research problem. Your job is to:
1. Understand the scientific domain and specific problem
2. Ask 2-3 targeted clarifying questions to better understand requirements

Keep your response conversational and concise. Do NOT propose a team yet - just analyze
the problem and ask clarifying questions to understand scope, constraints, and goals.

Respond in natural text (not JSON)."""

TEAM_PROPOSER_PROMPT = """You are a scientific research advisor helping to assemble a virtual lab team.

Based on the conversation so far, propose a team of 3-5 specialists. Return your response
in the following format:

1. A brief summary paragraph explaining your team composition rationale.
2. Then a JSON block with the team details:

```json
{
  "team_name": "descriptive team name",
  "team_description": "brief description of the team's focus",
  "agents": [
    {
      "name": "Agent Name",
      "title": "Professional Title",
      "expertise": "area of expertise",
      "goal": "what this agent aims to accomplish",
      "role": "specific role in the team",
      "model": "gpt-4"
    }
  ]
}
```

Use "gpt-4" as the default model for all agents unless the user specified a preference."""

MIRROR_ADVISOR_PROMPT = """You are a scientific research advisor explaining the concept of mirror agents.

Mirror agents are duplicate team members that use a different AI model to independently
verify the primary agents' outputs. This helps catch errors, biases, and hallucinations
through cross-validation.

Briefly explain how mirror agents would benefit this team and ask the user:
1. Whether they want to enable mirror agents
2. If yes, which model should the mirrors use (suggest an alternative to the primary model)

Keep your explanation concise (2-3 sentences about the benefit, then the questions)."""

# Domain keyword → (sub_domains, challenges, approaches, agent templates)
DOMAIN_TEMPLATES: Dict[str, dict] = {
    "biology": {
        "sub_domains": ["molecular biology", "genetics", "biochemistry"],
        "challenges": ["experimental design", "data analysis", "literature review"],
        "approaches": ["computational modeling", "statistical analysis", "systematic review"],
        "agents": [
            AgentSuggestion(
                name="Principal Investigator",
                title="Senior Research Scientist",
                expertise="experimental biology and research methodology",
                goal="design rigorous experiments and oversee research direction",
                role="lead the research team, define hypotheses, and ensure scientific rigor",
                model="gpt-4",
            ),
            AgentSuggestion(
                name="Computational Biologist",
                title="Bioinformatics Specialist",
                expertise="computational biology, data analysis, and statistical modeling",
                goal="analyze biological data and build predictive models",
                role="process experimental data, run statistical analyses, and generate visualizations",
                model="gpt-4",
            ),
        ],
    },
    "machine_learning": {
        "sub_domains": ["deep learning", "NLP", "computer vision", "reinforcement learning"],
        "challenges": ["model architecture", "data preprocessing", "hyperparameter tuning"],
        "approaches": ["benchmark comparison", "ablation study", "transfer learning"],
        "agents": [
            AgentSuggestion(
                name="ML Research Lead",
                title="Machine Learning Researcher",
                expertise="deep learning architectures and optimization",
                goal="design and evaluate novel ML approaches",
                role="lead model design, define evaluation metrics, and analyze results",
                model="gpt-4",
            ),
            AgentSuggestion(
                name="Data Engineer",
                title="Data Pipeline Specialist",
                expertise="data preprocessing, feature engineering, and pipeline design",
                goal="build robust data pipelines for model training",
                role="prepare datasets, implement data augmentation, and ensure data quality",
                model="gpt-4",
            ),
        ],
    },
    "chemistry": {
        "sub_domains": ["organic chemistry", "computational chemistry", "materials science"],
        "challenges": ["molecular design", "reaction optimization", "property prediction"],
        "approaches": ["molecular simulation", "quantum chemistry", "high-throughput screening"],
        "agents": [
            AgentSuggestion(
                name="Chemistry Lead",
                title="Computational Chemist",
                expertise="molecular modeling and simulation",
                goal="design and optimize molecular structures",
                role="lead molecular design, run simulations, and interpret results",
                model="gpt-4",
            ),
            AgentSuggestion(
                name="Materials Scientist",
                title="Materials Science Researcher",
                expertise="materials properties and characterization",
                goal="predict and validate material properties",
                role="analyze material candidates, model properties, and suggest optimizations",
                model="gpt-4",
            ),
        ],
    },
    "general": {
        "sub_domains": ["research methodology", "data analysis"],
        "challenges": ["problem definition", "literature review", "result interpretation"],
        "approaches": ["systematic analysis", "computational modeling", "peer review"],
        "agents": [
            AgentSuggestion(
                name="Research Lead",
                title="Senior Researcher",
                expertise="research methodology and critical analysis",
                goal="guide the research process and ensure quality",
                role="define research questions, coordinate team efforts, and synthesize findings",
                model="gpt-4",
            ),
            AgentSuggestion(
                name="Data Analyst",
                title="Quantitative Analyst",
                expertise="statistical analysis and data visualization",
                goal="extract insights from data through rigorous analysis",
                role="perform statistical tests, create visualizations, and validate findings",
                model="gpt-4",
            ),
        ],
    },
}

# Keywords for domain detection
DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "biology": ["biology", "gene", "protein", "cell", "dna", "rna", "enzyme", "organism",
                "mutation", "genome", "sequencing", "bioinformatics", "drug", "pharmaceutical"],
    "machine_learning": ["machine learning", "deep learning", "neural network", "nlp",
                         "computer vision", "ai", "model training", "classification",
                         "regression", "transformer", "reinforcement learning", "llm"],
    "chemistry": ["chemistry", "molecule", "reaction", "compound", "synthesis",
                  "molecular", "catalyst", "polymer", "material", "crystal"],
}

# Type alias for LLM function
LLMFunc = Callable[[str, List[ChatMessage]], str]


class TeamBuilder:
    """Builds virtual lab teams based on problem analysis.

    Args:
        llm_func: Optional callable (prompt, history) -> response string.
                  When None, uses template-based heuristics.
    """

    def __init__(self, llm_func: Optional[LLMFunc] = None):
        self.llm_func = llm_func

    # ==================== Helpers ====================

    @staticmethod
    def _build_messages(
        system_prompt: str,
        history: List[ChatMessage],
        user_message: Optional[str] = None,
    ) -> List[ChatMessage]:
        """Build message list with system prompt, conversation history, and optional new user message."""
        messages = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(history)
        if user_message:
            messages.append(ChatMessage(role="user", content=user_message))
        return messages

    @staticmethod
    def _parse_team_json(content: str) -> Optional[dict]:
        """Extract team JSON from LLM response (handles markdown fences)."""
        # Try to find JSON block in markdown fences first
        fence_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Try to find raw JSON object
        brace_match = re.search(r'\{.*\}', content, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _detect_domain(self, text: str) -> str:
        """Detect the research domain from problem description."""
        text_lower = text.lower()
        scores: Dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    # ==================== LLM-Powered Methods ====================

    def generate_clarifying_response(
        self,
        message: str,
        history: List[ChatMessage],
        preferred_lang: Optional[str] = None,
    ) -> str:
        """Use LLM to analyze the problem and ask clarifying questions.

        Returns natural language response (not JSON).
        Falls back to template analysis message if no llm_func.
        preferred_lang: 'zh' or 'en' to instruct response language.
        """
        if not self.llm_func:
            analysis = self.analyze_problem(message)
            return (
                f"I've identified your research domain as **{analysis.domain}**, "
                f"covering {', '.join(analysis.sub_domains)}.\n\n"
                f"Key challenges: {', '.join(analysis.key_challenges)}.\n\n"
                "Please share any preferences for your team:\n"
                "- Preferred team size (2-5 agents)?\n"
                "- Any specific model preference (e.g., gpt-4, claude-3-opus)?\n"
                "- Any particular focus area?"
            )
        prompt = ANALYZER_PROMPT
        if preferred_lang:
            prompt = prompt + "\n\n" + language_instruction(preferred_lang)
        messages = self._build_messages(prompt, history, message)
        return self.llm_func(prompt, messages[1:])

    def propose_team(
        self,
        history: List[ChatMessage],
        feedback: Optional[str] = None,
    ) -> Optional[TeamSuggestion]:
        """Use LLM to propose a team based on conversation history.

        Returns TeamSuggestion if JSON can be parsed, None otherwise.
        If feedback is provided, it's appended as a user message requesting revision.
        """
        if not self.llm_func:
            return None

        messages = list(history)
        if feedback:
            messages.append(ChatMessage(role="user", content=feedback))

        response = self.llm_func(TEAM_PROPOSER_PROMPT, messages)
        data = self._parse_team_json(response)
        if not data:
            return None

        try:
            agents = [AgentSuggestion(**a) for a in data.get("agents", [])]
            return TeamSuggestion(
                team_name=data.get("team_name", "Research Team"),
                team_description=data.get("team_description", ""),
                agents=agents,
            )
        except Exception:
            return None

    def propose_team_with_text(
        self,
        history: List[ChatMessage],
        feedback: Optional[str] = None,
        preferred_lang: Optional[str] = None,
    ) -> tuple[Optional[TeamSuggestion], str]:
        """Like propose_team but also returns the raw LLM response text.

        Returns (TeamSuggestion or None, raw_response_text).
        preferred_lang: 'zh' or 'en' for response language.
        """
        if not self.llm_func:
            return None, ""

        messages = list(history)
        if feedback:
            messages.append(ChatMessage(role="user", content=feedback))

        prompt = TEAM_PROPOSER_PROMPT
        if preferred_lang:
            prompt = prompt + "\n\n" + language_instruction(preferred_lang)
        response = self.llm_func(prompt, messages)
        data = self._parse_team_json(response)
        if not data:
            return None, response

        try:
            agents = [AgentSuggestion(**a) for a in data.get("agents", [])]
            suggestion = TeamSuggestion(
                team_name=data.get("team_name", "Research Team"),
                team_description=data.get("team_description", ""),
                agents=agents,
            )
            return suggestion, response
        except Exception:
            return None, response

    def explain_mirrors(self, history: List[ChatMessage], preferred_lang: Optional[str] = None) -> str:
        """Use LLM to explain mirror agents and ask if user wants them.

        Falls back to static message if no llm_func.
        """
        if not self.llm_func:
            return (
                "Would you like to enable mirror agents?\n\n"
                "Mirror agents use a different AI model to independently verify "
                "the primary agents' outputs, helping catch errors and biases.\n\n"
                "If yes, which model should mirrors use? (e.g., claude-3-opus, gpt-4)"
            )
        prompt = MIRROR_ADVISOR_PROMPT
        if preferred_lang:
            prompt = prompt + "\n\n" + language_instruction(preferred_lang)
        return self.llm_func(prompt, history)

    # ==================== Template-Based Methods (Fallback) ====================

    def analyze_problem(self, problem_description: str) -> DomainAnalysis:
        """Analyze a research problem and return domain analysis.

        If llm_func is available, uses LLM for richer analysis.
        Otherwise falls back to keyword-based template matching.
        """
        if self.llm_func:
            return self._llm_analyze_problem(problem_description)

        domain = self._detect_domain(problem_description)
        template = DOMAIN_TEMPLATES[domain]
        return DomainAnalysis(
            domain=domain,
            sub_domains=template["sub_domains"],
            key_challenges=template["challenges"],
            suggested_approaches=template["approaches"],
        )

    def _llm_analyze_problem(self, problem_description: str) -> DomainAnalysis:
        """Use LLM to analyze the problem (called when llm_func is available)."""
        prompt = (
            "Analyze this research problem and return ONLY a JSON object (no markdown, no code fences) with fields: "
            "domain (string), sub_domains (list of strings), key_challenges (list of strings), "
            "suggested_approaches (list of strings).\n\n"
            f"Problem: {problem_description}"
        )
        response = self.llm_func(prompt, [])
        try:
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', response.strip())
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            data = json.loads(cleaned)
            return DomainAnalysis(**data)
        except (json.JSONDecodeError, Exception):
            domain = self._detect_domain(problem_description)
            template = DOMAIN_TEMPLATES[domain]
            return DomainAnalysis(
                domain=domain,
                sub_domains=template["sub_domains"],
                key_challenges=template["challenges"],
                suggested_approaches=template["approaches"],
            )

    def suggest_team_composition(
        self,
        analysis: DomainAnalysis,
        preferences: Optional[Dict] = None,
    ) -> TeamSuggestion:
        """Suggest a team composition based on domain analysis.

        Args:
            analysis: The domain analysis result.
            preferences: Optional user preferences (e.g., team_size, focus_area).
        """
        preferences = preferences or {}
        domain = analysis.domain
        template = DOMAIN_TEMPLATES.get(domain, DOMAIN_TEMPLATES["general"])

        agents = list(template["agents"])  # Copy template agents

        # Add a critic/reviewer agent if team_size preference allows
        team_size = preferences.get("team_size", 3)
        if team_size >= 3:
            agents.append(AgentSuggestion(
                name="Scientific Critic",
                title="Peer Reviewer",
                expertise="critical analysis, methodology review, and scientific writing",
                goal="ensure research quality through rigorous review",
                role="review proposals and findings, identify weaknesses, and suggest improvements",
                model="gpt-4",
            ))

        # Respect model preference
        preferred_model = preferences.get("model")
        if preferred_model:
            agents = [
                AgentSuggestion(**{**a.model_dump(), "model": preferred_model})
                for a in agents
            ]

        team_name = preferences.get("team_name", f"{domain.replace('_', ' ').title()} Research Team")

        return TeamSuggestion(
            team_name=team_name,
            team_description=f"A research team focused on {', '.join(analysis.sub_domains)}. "
                            f"Key challenges: {', '.join(analysis.key_challenges)}.",
            agents=agents[:team_size],
        )

    def create_mirror_agents(
        self,
        primary_agents: List[AgentSuggestion],
        mirror_model: str = "gpt-4",
    ) -> List[AgentSuggestion]:
        """Create mirror agents for the given primary agents.

        Mirror agents use a different model to cross-validate primary agent outputs.
        """
        mirrors = []
        for agent in primary_agents:
            mirror = AgentSuggestion(
                name=f"{agent.name} (Mirror)",
                title=agent.title,
                expertise=agent.expertise,
                goal=f"independently verify and cross-validate: {agent.goal}",
                role=f"mirror role - {agent.role}",
                model=mirror_model,
            )
            mirrors.append(mirror)
        return mirrors

    def auto_generate_team(
        self,
        conversation_history: List[ChatMessage],
        team_name: str,
    ) -> TeamSuggestion:
        """Generate a complete team configuration from conversation history.

        Extracts problem description from history and builds a team.
        """
        # Extract the user's problem description from conversation
        problem_parts = [
            msg.content for msg in conversation_history if msg.role == "user"
        ]
        problem_description = " ".join(problem_parts)

        analysis = self.analyze_problem(problem_description)
        return self.suggest_team_composition(analysis, {"team_name": team_name})
