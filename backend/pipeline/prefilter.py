import re

def is_checkable_claim(text: str) -> bool:
    """
    Fast heuristic filter (<1ms) to reject obvious non-claims.
    Returns True if it might be a claim, False if it should be rejected.
    """
    text = text.strip()
    
    # 1. Length Check: Claims usually require subject, verb, and object.
    words = text.split()
    if len(words) < 3:
        return False
        
    # 2. Interrogative Check: Questions are not claims.
    if text.endswith('?'):
        return False
        
    # 3. Subjective/Conversational Prefix Check
    # Catches: "I think", "In my opinion", "Happy birthday", "Good morning"
    subjective_patterns = re.compile(
        r"^(i think|i feel|in my opinion|i guess|honestly|happy|good morning|hello|hi|thanks)\b", 
        re.IGNORECASE
    )
    if subjective_patterns.match(text):
        return False
        
    # 4. Command/Imperative Check
    # Catches: "Click here", "Subscribe to my channel"
    imperative_patterns = re.compile(
        r"^(click|subscribe|buy|download|follow|please|dont forget)\b",
        re.IGNORECASE
    )
    if imperative_patterns.match(text):
        return False

    # If it passes all heuristics, send it to the LLM (Layer 2)
    return True