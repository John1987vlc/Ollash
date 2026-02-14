"""
Extended Preference Manager for Phase 3: Memory & Learning

Handles user communication preferences, agent behavior customization,
and personalized interaction styles based on user history and feedback.

Key Features:
- Track communication style preferences (concise, detailed, formal, casual)
- Manage interaction preferences (code examples, visuals, verbose).
- Store complexity levels (beginner, intermediate, expert)
- Persist preferences across sessions
- Apply preferences to outgoing agent responses
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional
from enum import Enum
from datetime import datetime


logger = logging.getLogger(__name__)


class CommunicationStyle(Enum):
    """User's preferred communication style."""
    CONCISE = "concise"          # Short, to-the-point responses
    DETAILED = "detailed"        # Comprehensive, thorough explanations
    FORMAL = "formal"            # Professional, structured language
    CASUAL = "casual"            # Friendly, conversational tone
    TECHNICAL = "technical"      # Highly specific, technical terminology
    CONVERSATIONAL = "conversational"  # Natural, dialogue-like


class ComplexityLevel(Enum):
    """User's experience level."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class InteractionPreference(Enum):
    """Type of content user prefers."""
    CODE_EXAMPLES = "code_examples"
    DIAGRAMS = "diagrams"
    STRUCTURED_TEXT = "structured_text"
    BULLET_POINTS = "bullet_points"
    STEP_BY_STEP = "step_by_step"


class EnumEncoder(json.JSONEncoder):
    """Custom JSON encoder for Enum values."""
    def default(self, obj):
        if isinstance(obj, (CommunicationStyle, ComplexityLevel, InteractionPreference)):
            return obj.value
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


@dataclass
class CommunicationProfile:
    """User's communication preferences."""
    style: CommunicationStyle = field(default=CommunicationStyle.DETAILED)
    complexity: ComplexityLevel = field(default=ComplexityLevel.INTERMEDIATE)
    interaction_prefs: List[InteractionPreference] = field(
        default_factory=lambda: [
            InteractionPreference.CODE_EXAMPLES,
            InteractionPreference.DIAGRAMS
        ]
    )
    max_response_length: int = field(default=2000)
    use_examples: bool = field(default=True)
    use_visuals: bool = field(default=True)
    use_analogies: bool = field(default=True)
    prefer_spanish: bool = field(default=True)
    verbose_explanations: bool = field(default=True)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PreferenceProfile:
    """Complete user preference profile."""
    user_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # Communication preferences
    communication: CommunicationProfile = field(default_factory=CommunicationProfile)
    
    # Feature preferences
    features_enabled: Dict[str, bool] = field(default_factory=lambda: {
        "cross_reference": True,
        "knowledge_graph": True,
        "decision_memory": True,
        "artifacts": True,
        "feedback_refinement": True
    })
    
    # Customized settings
    custom_settings: Dict[str, Any] = field(default_factory=dict)
    
    # Interaction history
    total_interactions: int = 0
    total_feedback_given: int = 0
    positive_feedback_count: int = 0
    negative_feedback_count: int = 0
    
    # Learned behaviors
    learned_keywords: List[str] = field(default_factory=list)
    frequently_used_commands: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


class PreferenceManagerExtended:
    """
    Extended preference manager for learning and customization.
    
    Responsibilities:
    - Load/save user preference profiles
    - Track communication style evolution
    - Manage interaction preferences
    - Suggest behavior adjustments based on feedback
    - Apply preferences to responses
    """
    
    def __init__(self, workspace_root: Path = None):
        """
        Initialize preference manager.
        
        Args:
            workspace_root: Root path for preference storage
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.prefs_dir = self.workspace_root / "knowledge_workspace" / "preferences"
        self.prefs_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache of loaded profiles
        self._profiles: Dict[str, PreferenceProfile] = {}
    
    def create_profile(self, user_id: str) -> PreferenceProfile:
        """
        Create a new preference profile.
        
        Args:
            user_id: Unique user identifier
            
        Returns:
            New preference profile
        """
        profile = PreferenceProfile(user_id=user_id)
        self.save_profile(profile)
        self._profiles[user_id] = profile
        logger.info(f"Created preference profile for user {user_id}")
        return profile
    
    def get_profile(self, user_id: str) -> PreferenceProfile:
        """
        Retrieve user preference profile.
        
        Args:
            user_id: User identifier
            
        Returns:
            Preference profile or creates new if doesn't exist
        """
        # Check cache
        if user_id in self._profiles:
            return self._profiles[user_id]
        
        # Try to load from file
        profile_path = self.prefs_dir / f"{user_id}.json"
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profile = self._deserialize_profile(data)
                    self._profiles[user_id] = profile
                    return profile
            except Exception as e:
                logger.error(f"Error loading profile for {user_id}: {e}")
        
        # Create new profile
        return self.create_profile(user_id)
    
    def save_profile(self, profile: PreferenceProfile) -> bool:
        """
        Save preference profile to disk.
        
        Args:
            profile: Profile to save
            
        Returns:
            Success status
        """
        try:
            profile.last_modified = datetime.now().isoformat()
            profile_path = self.prefs_dir / f"{profile.user_id}.json"
            
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(profile), f, indent=2, ensure_ascii=False, cls=EnumEncoder)
            
            self._profiles[profile.user_id] = profile
            logger.info(f"Saved profile for user {profile.user_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving profile: {e}")
            return False
    
    def update_communication_style(
        self,
        user_id: str,
        style: CommunicationStyle = None,
        complexity: ComplexityLevel = None,
        **kwargs
    ) -> PreferenceProfile:
        """
        Update communication preferences.
        
        Args:
            user_id: User identifier
            style: New communication style
            complexity: New complexity level
            **kwargs: Other preferences to update
            
        Returns:
            Updated profile
        """
        profile = self.get_profile(user_id)
        
        if style:
            profile.communication.style = style
        if complexity:
            profile.communication.complexity = complexity
        
        # Update other preferences
        for key, value in kwargs.items():
            if hasattr(profile.communication, key):
                setattr(profile.communication, key, value)
        
        profile.communication.last_updated = datetime.now().isoformat()
        self.save_profile(profile)
        
        logger.info(f"Updated communication style for {user_id}: {style}")
        return profile
    
    def add_interaction(
        self,
        user_id: str,
        feedback_type: str = None,
        keywords: List[str] = None,
        command: str = None
    ) -> PreferenceProfile:
        """
        Record user interaction and feedback.
        
        Args:
            user_id: User identifier
            feedback_type: "positive", "negative", or None
            keywords: Keywords used in interaction
            command: Command or action performed
            
        Returns:
            Updated profile
        """
        profile = self.get_profile(user_id)
        
        # Track interaction
        profile.total_interactions += 1
        
        # Track feedback
        if feedback_type:
            profile.total_feedback_given += 1
            if feedback_type == "positive":
                profile.positive_feedback_count += 1
            elif feedback_type == "negative":
                profile.negative_feedback_count += 1
        
        # Track keywords
        if keywords:
            for kw in keywords:
                if kw not in profile.learned_keywords:
                    profile.learned_keywords.append(kw)
                else:
                    profile.learned_keywords.remove(kw)
                    profile.learned_keywords.append(kw)  # Move to end
        
        # Track commands
        if command:
            if command not in profile.frequently_used_commands:
                profile.frequently_used_commands.append(command)
            else:
                profile.frequently_used_commands.remove(command)
                profile.frequently_used_commands.append(command)
        
        # Keep only top 20
        profile.learned_keywords = profile.learned_keywords[-20:]
        profile.frequently_used_commands = profile.frequently_used_commands[-20:]
        
        self.save_profile(profile)
        return profile
    
    def get_recommendations(self, user_id: str) -> Dict[str, Any]:
        """
        Generate preference recommendations based on history.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary of recommendations
        """
        profile = self.get_profile(user_id)
        recommendations = {
            "style_recommendation": None,
            "complexity_recommendation": None,
            "feature_recommendations": [],
            "confidence": 0.0
        }
        
        if profile.total_interactions < 5:
            return recommendations  # Not enough data
        
        # Analyze feedback ratio
        total_feedback = profile.positive_feedback_count + profile.negative_feedback_count
        if total_feedback > 0:
            positive_ratio = profile.positive_feedback_count / total_feedback
            
            # If mostly positive feedback, prefer current settings
            if positive_ratio > 0.75:
                recommendations["confidence"] = positive_ratio
            # If mixed, suggest slight adjustments
            elif positive_ratio < 0.4 and profile.communication.style == CommunicationStyle.DETAILED:
                recommendations["style_recommendation"] = CommunicationStyle.CONCISE
                recommendations["confidence"] = 0.6
        
        # Recommend complexity based on commands used
        expert_keywords = {"architecture", "optimization", "algorithm", "performance", "scale"}
        if profile.learned_keywords:
            overlap = len(expert_keywords & set(profile.learned_keywords))
            if overlap > 3:
                recommendations["complexity_recommendation"] = ComplexityLevel.EXPERT
                recommendations["confidence"] = 0.7
        
        return recommendations
    
    def apply_preferences_to_response(
        self,
        user_id: str,
        response: str,
        content_type: str = "text"
    ) -> str:
        """
        Transform response to match user preferences.
        
        Args:
            user_id: User identifier
            response: Original response
            content_type: Type of content ("text", "code", "explanation")
            
        Returns:
            Modified response
        """
        profile = self.get_profile(user_id)
        
        style = profile.communication.style
        complexity = profile.communication.complexity
        
        # Apply style transformations
        if style == CommunicationStyle.CONCISE:
            # Remove verbose explanations
            response = self._make_concise(response)
        
        elif style == CommunicationStyle.FORMAL:
            # Capitalize, use professional language
            response = self._make_formal(response)
        
        elif style == CommunicationStyle.CASUAL:
            # Add friendly tone markers
            response = self._make_casual(response)
        
        # Apply complexity transformations
        if complexity == ComplexityLevel.BEGINNER:
            response = self._simplify_for_beginner(response)
        elif complexity == ComplexityLevel.EXPERT:
            response = self._add_technical_depth(response)
        
        return response
    
    def _make_concise(self, text: str) -> str:
        """Remove verbose parts from text."""
        lines = text.split('\n')
        # Remove intro/outro lines about to explain
        filtered = [
            l for l in lines
            if not any(x in l.lower() for x in [
                "let me explain",
                "to clarify",
                "in other words",
                "essentially"
            ])
        ]
        return '\n'.join(filtered)
    
    def _make_formal(self, text: str) -> str:
        """Make text more formal."""
        text = text.replace("you should", "it is recommended that one")
        text = text.replace("gonna", "will")
        text = text.replace("gimme", "provide me with")
        return text
    
    def _make_casual(self, text: str) -> str:
        """Make text more casual."""
        text = text.replace("However,", "Though,")
        text = text.replace("Furthermore,", "Plus,")
        text = text.replace("Additionally,", "Also,")
        return text
    
    def _simplify_for_beginner(self, text: str) -> str:
        """Remove advanced concepts."""
        # Would remove/simplify technical jargon
        return text
    
    def _add_technical_depth(self, text: str) -> str:
        """Add technical details for experts."""
        # Would add implementation details, algorithms, etc.
        return text
    
    def _deserialize_profile(self, data: Dict[str, Any]) -> PreferenceProfile:
        """Deserialize profile from JSON."""
        # Convert enum strings back to enums and reconstruct CommunicationProfile
        if "communication" in data:
            comm = data["communication"]
            if isinstance(comm, dict):
                if isinstance(comm.get("style"), str):
                    comm["style"] = CommunicationStyle(comm["style"])
                if isinstance(comm.get("complexity"), str):
                    comm["complexity"] = ComplexityLevel(comm["complexity"])
                if "interaction_prefs" in comm:
                    comm["interaction_prefs"] = [
                        InteractionPreference(p) if isinstance(p, str) else p
                        for p in comm["interaction_prefs"]
                    ]
                # Convert dict to CommunicationProfile object
                data["communication"] = CommunicationProfile(**comm)
        
        return PreferenceProfile(**data)
    
    def get_all_profiles(self) -> Dict[str, PreferenceProfile]:
        """
        Get all preference profiles.
        
        Returns:
            Dictionary of all profiles
        """
        profiles = {}
        for profile_file in self.prefs_dir.glob("*.json"):
            try:
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profile = self._deserialize_profile(data)
                    profiles[profile.user_id] = profile
            except Exception as e:
                logger.error(f"Error loading profile {profile_file}: {e}")
        
        return profiles
    
    def export_profile(self, user_id: str, format: str = "json") -> str:
        """
        Export user profile.
        
        Args:
            user_id: User identifier
            format: Export format (json, markdown)
            
        Returns:
            Exported profile as string
        """
        profile = self.get_profile(user_id)
        
        if format == "json":
            return json.dumps(asdict(profile), indent=2, ensure_ascii=False, cls=EnumEncoder)
        
        elif format == "markdown":
            md = f"# Preference Profile: {user_id}\n\n"
            md += f"**Created**: {profile.created_at}\n"
            md += f"**Last Modified**: {profile.last_modified}\n\n"
            
            md += "## Communication Style\n"
            md += f"- Style: {profile.communication.style.value}\n"
            md += f"- Complexity: {profile.communication.complexity.value}\n"
            md += f"- Use Examples: {profile.communication.use_examples}\n"
            md += f"- Use Visuals: {profile.communication.use_visuals}\n\n"
            
            md += "## Statistics\n"
            md += f"- Total Interactions: {profile.total_interactions}\n"
            md += f"- Positive Feedback: {profile.positive_feedback_count}\n"
            md += f"- Negative Feedback: {profile.negative_feedback_count}\n\n"
            
            md += "## Learned Keywords\n"
            if profile.learned_keywords:
                md += ", ".join(profile.learned_keywords) + "\n\n"
            
            md += "## Frequently Used Commands\n"
            if profile.frequently_used_commands:
                md += "- " + "\n- ".join(profile.frequently_used_commands)
            
            return md
        
        return ""
