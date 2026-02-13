"""
MirrorValidator: Compare primary and mirror agent responses for consistency.

Used to cross-validate outputs from primary agents against their mirror counterparts,
flagging significant disagreements for human review.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class ComparisonResult:
    """Result of comparing primary and mirror agent responses."""
    primary_response: str
    mirror_response: str
    similarity_score: float  # 0.0 to 1.0
    key_agreements: List[str]
    key_disagreements: List[str]
    needs_review: bool


class MirrorValidator:
    """Validates consistency between primary and mirror agent outputs."""

    def __init__(self, review_threshold: float = 0.5):
        """
        Args:
            review_threshold: Similarity score below which responses are flagged
                            for human review. Range [0.0, 1.0].
        """
        self.review_threshold = review_threshold

    def compare_responses(
        self,
        primary_response: str,
        mirror_response: str,
    ) -> ComparisonResult:
        """Compare primary and mirror agent responses.

        Uses token overlap as a simple similarity metric.
        In future, can be enhanced with LLM-based semantic comparison.
        """
        primary_tokens = set(primary_response.lower().split())
        mirror_tokens = set(mirror_response.lower().split())

        if not primary_tokens and not mirror_tokens:
            return ComparisonResult(
                primary_response=primary_response,
                mirror_response=mirror_response,
                similarity_score=1.0,
                key_agreements=[],
                key_disagreements=[],
                needs_review=False,
            )

        # Jaccard similarity
        intersection = primary_tokens & mirror_tokens
        union = primary_tokens | mirror_tokens
        similarity = len(intersection) / len(union) if union else 1.0

        # Identify key terms unique to each response (potential disagreements)
        # Filter out common stop words for more meaningful comparison
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "can", "need", "dare", "ought",
            "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again",
            "further", "then", "once", "and", "but", "or", "nor", "not", "so",
            "yet", "both", "either", "neither", "each", "every", "all", "any",
            "few", "more", "most", "other", "some", "such", "no", "only",
            "own", "same", "than", "too", "very", "just", "because", "if",
            "when", "where", "how", "what", "which", "who", "whom", "this",
            "that", "these", "those", "i", "me", "my", "we", "our", "you",
            "your", "he", "him", "his", "she", "her", "it", "its", "they",
            "them", "their",
        }

        meaningful_primary = primary_tokens - mirror_tokens - stop_words
        meaningful_mirror = mirror_tokens - primary_tokens - stop_words
        meaningful_shared = intersection - stop_words

        agreements = sorted(list(meaningful_shared))[:10]
        disagreements = sorted(list(meaningful_primary | meaningful_mirror))[:10]

        needs_review = self.should_flag_for_review(similarity)

        return ComparisonResult(
            primary_response=primary_response,
            mirror_response=mirror_response,
            similarity_score=round(similarity, 3),
            key_agreements=agreements,
            key_disagreements=disagreements,
            needs_review=needs_review,
        )

    def should_flag_for_review(self, similarity_score: float) -> bool:
        """Determine if a comparison result should be flagged for human review."""
        return similarity_score < self.review_threshold
