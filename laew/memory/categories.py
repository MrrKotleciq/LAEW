"""Canonical memory taxonomy shared by tools, extraction and storage boundaries."""
from types import MappingProxyType


CATEGORY_DESCRIPTIONS = MappingProxyType({
    'preference': 'Likes, dislikes and preferred ways of doing things, including travel style.',
    'education': 'Studies, qualifications and formal learning.',
    'interest': 'Topics and activities of interest; does not imply proficiency.',
    'skill': 'Demonstrated abilities and proficiency.',
    'goal': 'Future intentions and desired outcomes, including travel and career goals.',
    'decision': 'Confirmed choices, including project decisions.',
    'constraint': 'Durable requirements, boundaries and limitations.',
    'fact': 'Other durable facts, including past experience and achievements.',
})
CATEGORIES = frozenset(CATEGORY_DESCRIPTIONS)
ALIASES = MappingProxyType({
    'preferences': 'preference', 'interests': 'interest', 'skills': 'skill',
    'goals': 'goal', 'decisions': 'decision', 'constraints': 'constraint', 'facts': 'fact',
})


class InvalidMemoryCategory(ValueError):
    def __init__(self):
        super().__init__('Invalid memory category. Accepted categories: '
                         + ', '.join(CATEGORY_DESCRIPTIONS)
                         + '. Correct category and retry within the existing tool-call limit; '
                         'use goal for future travel intentions or fact for other durable facts. '
                         'No memory was written.')

    def details(self):
        return {'field': 'category', 'accepted_categories': list(CATEGORY_DESCRIPTIONS),
                'retryable': True, 'action': 'Correct category and retry; no memory was written.'}


def normalize_category(value):
    """Only casing, outer whitespace and explicit singular/plural equivalents."""
    if isinstance(value, str):
        canonical = value.strip().casefold()
        canonical = ALIASES.get(canonical, canonical)
        if canonical in CATEGORIES:
            return canonical
    raise InvalidMemoryCategory()


def category_guidance():
    return ('Choose one information type, never a topic or a new category. '
            + ' '.join(f'{key}: {description}' for key, description in CATEGORY_DESCRIPTIONS.items())
            + ' Separate unrelated facts into separate proposals. Correct invalid arguments and retry; '
              'only report success after a successful tool result.')


def category_schema():
    return {'type': 'string', 'enum': list(CATEGORY_DESCRIPTIONS), 'description': category_guidance()}
