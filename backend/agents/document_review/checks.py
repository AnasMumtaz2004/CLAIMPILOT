import re
from datetime import datetime

# Anything that is not a letter or a number is ignored when comparing text
NOT_ALPHANUMERIC_RE = re.compile(r"[^a-z0-9]")
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
WORD_RE = re.compile(r"[a-z0-9]+")

# Words that do not help to tell two names apart
NAME_TITLES = ["mr", "mrs", "ms", "dr", "shri", "smt", "m", "s"]

DATE_FORMATS = [
    "%d-%b-%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%d-%B-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d.%m.%Y",
]


def normalize_alphanumeric(text):
    """Lower-case a text and keep only its letters and numbers."""
    return NOT_ALPHANUMERIC_RE.sub("", str(text).lower())


def split_words(text):
    """Split a text into lower-case words and numbers, dropping punctuation."""
    return WORD_RE.findall(str(text).lower())


def contains_words(text_words, wanted_words):
    """Return True if the wanted words appear next to each other, in order, in the text words."""
    size = len(wanted_words)
    if size == 0:
        return False

    for start in range(len(text_words) - size + 1):
        if text_words[start:start + size] == wanted_words:
            return True
    return False


def quote_in_text(quote, text):
    """Return True if the quote is found in the text. Spaces, case and punctuation are ignored."""
    # Whole words are compared, so 'Total 5' is not found in 'Total 50'
    return contains_words(split_words(text), split_words(quote))


def value_in_quote(value, quote):
    """Return True if the extracted value is part of its quote."""
    return contains_words(split_words(quote), split_words(value))


def parse_number(text):
    """Return the first number in a text as a float, or None. Commas are ignored."""
    match = NUMBER_RE.search(str(text))
    if match is None:
        return None
    return float(match.group(0).replace(",", ""))


def number_in_text(amount, text):
    """Return True if the amount is written somewhere in the text."""
    for match in NUMBER_RE.finditer(str(text)):
        found = float(match.group(0).replace(",", ""))
        if abs(found - float(amount)) < 0.005:
            return True
    return False


def amounts_equal(first, second, tolerance):
    """Return True if two amounts are the same, within the tolerance."""
    return abs(float(first) - float(second)) <= tolerance


def parse_date(text):
    """Return a date from a text such as '20-Oct-2026' or '20/10/2026', or None."""
    words = str(text).strip().split()
    if len(words) == 0:
        return None

    # The date may be followed by a time, so try the first word and the first three words
    candidates = [words[0], " ".join(words[:3])]
    for candidate in candidates:
        for date_format in DATE_FORMATS:
            try:
                return datetime.strptime(candidate, date_format).date()
            except ValueError:
                continue
    return None


def dates_close(first, second, days):
    """Return True if two dates are not more than the given number of days apart."""
    return abs((first - second).days) <= days


def name_words(name):
    """Split a name into lower-case words and drop titles such as Mr and Dr."""
    words = []
    for word in WORD_RE.findall(str(name).lower()):
        if word not in NAME_TITLES and not word.isdigit():
            words.append(word)
    return words


def word_matches(word, other_words):
    """Return True if a word is in the other list. A single letter matches any word that starts with it."""
    for other in other_words:
        if word == other:
            return True
        if len(word) == 1 and other.startswith(word):
            return True
        if len(other) == 1 and word.startswith(other):
            return True
    return False


def names_match(first, second):
    """Return True if two names can be the same person, even with initials or a different word order."""
    first_words = name_words(first)
    second_words = name_words(second)
    if len(first_words) == 0 or len(second_words) == 0:
        return False

    shorter = first_words
    longer = second_words
    if len(second_words) < len(first_words):
        shorter = second_words
        longer = first_words

    for word in shorter:
        if not word_matches(word, longer):
            return False
    return True


def address_words(address):
    """Split an address into lower-case words and numbers."""
    return WORD_RE.findall(str(address).lower())


def addresses_match(first, second):
    """Return True if every word of the shorter address is also in the longer one."""
    first_words = address_words(first)
    second_words = address_words(second)
    if len(first_words) == 0 or len(second_words) == 0:
        return False

    shorter = first_words
    longer = second_words
    if len(second_words) < len(first_words):
        shorter = second_words
        longer = first_words

    for word in shorter:
        if word not in longer:
            return False
    return True


def normalize_registration(text):
    """Write a vehicle registration number in capitals without spaces or dashes."""
    return normalize_alphanumeric(text).upper()