"""
TeamBuilder: AI-powered team composition engine.

Analyzes research problems and suggests optimal virtual lab team configurations.
LLM calls are abstracted via a callable `llm_func` for easy mocking in tests.
When no llm_func is provided, uses template-based heuristics.
"""

from typing import Callable, Dict, List, Optional

from app.schemas.onboarding import (
    AgentSuggestion,
    ChatMessage,
    DomainAnalysis,
    MirrorConfig,
    TeamSuggestion,
)

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
        llm_func: Optional async callable (prompt, history) -> response string.
                  When None, uses template-based heuristics.
    """

    def __init__(self, llm_func: Optional[LLMFunc] = None):
        self.llm_func = llm_func

    def _detect_domain(self, text: str) -> str:
        """Detect the research domain from problem description."""
        text_lower = text.lower()
        scores: Dict[str, int] = {}
        for domain, keywords in DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

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
            "Analyze this research problem and return a JSON with fields: "
            "domain, sub_domains (list), key_challenges (list), suggested_approaches (list).\n\n"
            f"Problem: {problem_description}"
        )
        response = self.llm_func(prompt, [])
        # In real implementation, parse JSON from LLM response
        # For now, fall back to template if parsing fails
        import json
        try:
            data = json.loads(response)
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
