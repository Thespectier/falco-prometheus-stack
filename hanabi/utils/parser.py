import re

# Regex patterns for attribute tokenization/generalization

# 1. UUID Pattern: e.g. 123e4567-e89b-12d3-a456-426614174000 (relaxed boundaries)
_UUID_PATTERN = re.compile(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)

# 2. IPv4 Pattern: Matches valid IP addresses
_IP_PATTERN = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
)

# 3. Hash/Hex Pattern: Matches long hex strings typical of hashes (e.g. md5, sha1, sha256)
#    Removes \b boundaries to catch hashes embedded in paths, replaces with <hash>
_HASH_PATTERN = re.compile(r'(?<![g-zG-Z])[0-9a-fA-F]{32,}(?![g-zG-Z])')

# 4. Short Hex Pattern: Matches shorter hex strings without \b to catch them in paths
#    Uses negative lookbehinds/lookaheads to ensure we don't just match part of a normal word
_HEX_PATTERN = re.compile(r'(?<![a-zA-Z])[0-9a-fA-F]{8,31}(?![a-zA-Z])')

# 5. Digit Pattern: Matches sequences of 5 or more digits without strict \b
_DIGIT_PATTERN = re.compile(r'(?<![a-zA-Z])\d{5,}(?![a-zA-Z])')

# 6. Date Pattern: Matches YYYY-MM-DD, YYYYMMDD, etc. commonly found in filenames
_DATE_PATTERN = re.compile(r'(?<!\d)20\d{2}[-_]?\d{2}[-_]?\d{2}(?!\d)')

# 7. Random Alphanumeric Pattern: Matches common 6-char random alphanumeric suffixes
#    used by tempfile like mktemp (e.g., .b4Ofdv, .Whvbww)
_RANDOM_SUFFIX_PATTERN = re.compile(r'(?<=\.)[a-zA-Z0-9]{6}(?=$|/)')

def tokenize_attribute(attr: str) -> str:
    """
    Tokenize attribute string for generalization to reduce false positives.
    
    Applies the following transformations in order:
    1. UUID -> '<uuid>'
    2. IP addresses -> '<ip>'
    3. Dates (YYYY-MM-DD) -> '<date>'
    4. Hashes (>=32 hex chars) -> '<hash>'
    5. Hex strings (8-31 chars) -> '<hex>'
    6. Digit strings (>=5 chars) -> '<num>'
    7. Random 6-char suffixes -> '<random>'
    
    Args:
        attr: Original attribute string
        
    Returns:
        Tokenized attribute string
    """
    if not attr:
        return attr

    # Handle numeric/non-string types gracefully
    if not isinstance(attr, str):
        attr = str(attr)

    # 1. Replace UUID with '<uuid>'
    result = _UUID_PATTERN.sub('<uuid>', attr)
    
    # 2. Replace IP addresses with '<ip>'
    result = _IP_PATTERN.sub('<ip>', result)
    
    # 3. Replace Date strings with '<date>'
    result = _DATE_PATTERN.sub('<date>', result)

    # 4. Replace long hashes with '<hash>'
    result = _HASH_PATTERN.sub('<hash>', result)

    # 5. Replace remaining hex strings (8-31 chars) with '<hex>'
    result = _HEX_PATTERN.sub('<hex>', result)

    # 6. Replace digit strings (>=5 chars) with '<num>'
    result = _DIGIT_PATTERN.sub('<num>', result)

    # 7. Replace random 6-char alphanumeric suffixes with '<random>'
    result = _RANDOM_SUFFIX_PATTERN.sub('<random>', result)

    return result
