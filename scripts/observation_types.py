#!/usr/bin/env python3
"""
Context Engine: Observation Type System
Categorizes knowledge entries by type for better filtering and retrieval

Types:
- decision: Architecture/design choices
- bugfix: Bug fixes and solutions
- feature: New feature implementations
- refactor: Code restructuring
- discovery: Learned facts about codebase
- change: General modifications

Inspired by claude-mem's observation taxonomy.
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path


# ============================================================================
# Observation Types
# ============================================================================

class ObservationType(Enum):
    """Categorizes knowledge entries by their nature"""
    DECISION = "decision"      # Architecture/design choices
    BUGFIX = "bugfix"          # Bug fixes and solutions
    FEATURE = "feature"        # New feature implementations
    REFACTOR = "refactor"      # Code restructuring
    DISCOVERY = "discovery"    # Learned facts about codebase
    CHANGE = "change"          # General modifications

    @classmethod
    def from_string(cls, value: str) -> 'ObservationType':
        """Convert string to ObservationType, with fallback to CHANGE"""
        value = value.lower().strip()
        for member in cls:
            if member.value == value:
                return member
        return cls.CHANGE


@dataclass
class Observation:
    """A typed knowledge entry with metadata"""
    type: ObservationType
    title: str
    content: str
    timestamp: str = ""
    files: List[str] = None
    tags: List[str] = None
    source_file: str = ""

    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.tags is None:
            self.tags = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'type': self.type.value,
            'title': self.title,
            'content': self.content,
            'timestamp': self.timestamp,
            'files': self.files,
            'tags': self.tags,
            'source_file': self.source_file
        }

    def to_yaml_entry(self) -> str:
        """Convert to YAML format"""
        files_str = ', '.join(self.files) if self.files else '[]'
        tags_str = ', '.join(self.tags) if self.tags else '[]'
        return f"""- type: {self.type.value}
  title: "{self.title}"
  timestamp: "{self.timestamp}"
  files: [{files_str}]
  tags: [{tags_str}]
  content: |
    {self.content.replace(chr(10), chr(10) + '    ')}
"""


# ============================================================================
# Classification Patterns
# ============================================================================

class ObservationClassifier:
    """
    Classifies text into observation types using pattern matching.
    Uses keyword patterns weighted by specificity.
    """

    # Patterns for each observation type (more specific patterns = higher weight)
    TYPE_PATTERNS: Dict[ObservationType, List[str]] = {
        ObservationType.DECISION: [
            r'\bdecided\b', r'\bchose\b', r'\bselected\b', r'\barchitecture\b',
            r'\bdesign\b', r'\btrade-?off\b', r'\bvs\.?\b', r'\binstead of\b',
            r'\bapproach\b', r'\bstrategy\b', r'\bprefer\b', r'\bopt(ed)?\b'
        ],
        ObservationType.BUGFIX: [
            r'\bfix(ed|es|ing)?\b', r'\bbug\b', r'\berror\b', r'\bissue\b',
            r'\bresolved\b', r'\bbroken\b', r'\bcrash\b', r'\bexception\b',
            r'\bproblem\b', r'\bfailing\b', r'\bworkaround\b', r'\bpatch\b'
        ],
        ObservationType.FEATURE: [
            r'\bimplement(ed|s|ing)?\b', r'\badd(ed|s|ing)?\b', r'\bnew\b',
            r'\bfeature\b', r'\bcreate[ds]?\b', r'\bbuild\b', r'\bintroduce\b',
            r'\benhanc(e|ed|ing)\b', r'\bextend\b', r'\bcapability\b'
        ],
        ObservationType.REFACTOR: [
            r'\brefactor\b', r'\brestructure\b', r'\breorganize\b', r'\bclean\b',
            r'\bimprove\b', r'\bsimplif(y|ied)\b', r'\bextract\b', r'\brename\b',
            r'\bmodularize\b', r'\boptimize\b', r'\bDRY\b', r'\bdedup\b'
        ],
        ObservationType.DISCOVERY: [
            r'\bfound\b', r'\bdiscover(ed|y)?\b', r'\blearn(ed|t)?\b',
            r'\brealize[ds]?\b', r'\bnotice[ds]?\b', r'\bunderstand\b',
            r'\binsight\b', r'\bturns out\b', r'\bapparently\b', r'\bTIL\b'
        ],
        ObservationType.CHANGE: [
            r'\bchang(e[ds]?|ing)\b', r'\bupdat(e[ds]?|ing)\b',
            r'\bmodif(y|ied|ies|ying)\b', r'\balter(ed)?\b', r'\badjust(ed)?\b',
            r'\btweak(ed)?\b', r'\bconfig\b', r'\bsetting\b'
        ]
    }

    # File-to-type mapping for knowledge base files
    FILE_TYPE_HINTS: Dict[str, ObservationType] = {
        'patterns': ObservationType.FEATURE,
        'failures': ObservationType.BUGFIX,
        'decisions': ObservationType.DECISION,
        'gotchas': ObservationType.DISCOVERY
    }

    def classify(self, text: str, source_file: str = "") -> ObservationType:
        """
        Classify text into an observation type.

        Args:
            text: The text content to classify
            source_file: Optional source filename for hints

        Returns:
            The most likely ObservationType
        """
        # Check file-based hints first
        if source_file:
            for file_pattern, obs_type in self.FILE_TYPE_HINTS.items():
                if file_pattern in source_file.lower():
                    return obs_type

        # Score each type based on pattern matches
        text_lower = text.lower()
        scores: Dict[ObservationType, int] = {}

        for obs_type, patterns in self.TYPE_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, text_lower))
            scores[obs_type] = score

        # Return highest scoring type, default to CHANGE if no matches
        best_type = max(scores, key=scores.get)
        return best_type if scores[best_type] > 0 else ObservationType.CHANGE

    def classify_with_confidence(self, text: str, source_file: str = "") -> tuple:
        """
        Classify text and return confidence score.

        Args:
            text: The text content to classify
            source_file: Optional source filename for hints

        Returns:
            Tuple of (ObservationType, confidence: float 0-1)
        """
        text_lower = text.lower()
        scores: Dict[ObservationType, int] = {}

        for obs_type, patterns in self.TYPE_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, text_lower))
            scores[obs_type] = score

        total_matches = sum(scores.values())
        if total_matches == 0:
            return ObservationType.CHANGE, 0.0

        best_type = max(scores, key=scores.get)
        confidence = scores[best_type] / total_matches if total_matches > 0 else 0.0

        return best_type, confidence


# ============================================================================
# Convenience Functions
# ============================================================================

def classify_knowledge_entry(title: str, content: str, source_file: str = "") -> ObservationType:
    """
    Convenience function to classify a knowledge entry.

    Args:
        title: Entry title
        content: Entry content
        source_file: Source filename (e.g., "patterns.md")

    Returns:
        The classified ObservationType
    """
    classifier = ObservationClassifier()
    combined_text = f"{title} {content}"
    return classifier.classify(combined_text, source_file)


def get_type_color(obs_type: ObservationType) -> str:
    """Get ANSI color code for observation type (for CLI output)"""
    colors = {
        ObservationType.DECISION: '\033[94m',    # Blue
        ObservationType.BUGFIX: '\033[91m',      # Red
        ObservationType.FEATURE: '\033[92m',     # Green
        ObservationType.REFACTOR: '\033[93m',    # Yellow
        ObservationType.DISCOVERY: '\033[95m',   # Magenta
        ObservationType.CHANGE: '\033[96m',      # Cyan
    }
    return colors.get(obs_type, '\033[0m')


def get_type_emoji(obs_type: ObservationType) -> str:
    """Get emoji for observation type (for visual indicators)"""
    emojis = {
        ObservationType.DECISION: '🎯',
        ObservationType.BUGFIX: '🐛',
        ObservationType.FEATURE: '✨',
        ObservationType.REFACTOR: '🔧',
        ObservationType.DISCOVERY: '💡',
        ObservationType.CHANGE: '📝',
    }
    return emojis.get(obs_type, '📝')


def parse_type_from_markdown(content: str) -> Optional[ObservationType]:
    """
    Parse observation type from markdown metadata field.

    Looks for patterns like:
    - **Type:** decision
    - Type: bugfix

    Args:
        content: Markdown content to parse

    Returns:
        ObservationType if found, None otherwise
    """
    match = re.search(r'\*?\*?Type:?\*?\*?\s*(\w+)', content, re.IGNORECASE)
    if match:
        return ObservationType.from_string(match.group(1))
    return None


# ============================================================================
# Testing
# ============================================================================

def main():
    """Test observation type classification"""
    print("Context Engine: Observation Type System")
    print()

    classifier = ObservationClassifier()

    # Test cases
    test_cases = [
        ("Decided to use JWT for authentication", "decisions.md"),
        ("Fixed the null pointer exception in user service", "failures.md"),
        ("Implemented new caching layer for API responses", "patterns.md"),
        ("Refactored the database connection pool for better performance", ""),
        ("Discovered that the config file was being parsed twice", ""),
        ("Updated the README with installation instructions", ""),
    ]

    print("Classification Results:")
    print("-" * 60)

    for text, source in test_cases:
        obs_type, confidence = classifier.classify_with_confidence(text, source)
        emoji = get_type_emoji(obs_type)
        print(f"{emoji} [{obs_type.value:10}] (conf: {confidence:.2f}) {text[:50]}...")

    print()
    print("All observation types:")
    for obs_type in ObservationType:
        emoji = get_type_emoji(obs_type)
        print(f"  {emoji} {obs_type.value}: {obs_type.name}")

    print()
    print("Done!")


if __name__ == '__main__':
    main()
