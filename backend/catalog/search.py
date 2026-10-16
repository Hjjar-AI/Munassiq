import re
import unicodedata
from difflib import SequenceMatcher

_TRANSLATION = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي', 'ـ': ''})


def normalize(value):
    value = unicodedata.normalize('NFKD', value).casefold().translate(_TRANSLATION)
    value = ''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(re.sub(r'[^\w\s]', ' ', value).split())


def similar_names(left, right):
    left, right = normalize(left), normalize(right)
    return bool(left and right) and (left == right or SequenceMatcher(None, left, right).ratio() >= 0.85)
