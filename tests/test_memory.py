from backend.app.conversation.memory import trim_history_by_tokens, Message

def test_trim_session_messages():
    def rough_token_count(text: str) -> int:
        return max(1, len(text) // 4)
        
    messages = [
        Message(role="system", content="A"*400), # 100 tokens
        Message(role="user", content="B"*400), # 100 tokens
        Message(role="assistant", content="C"*400), # 100 tokens
        Message(role="user", content="D"*400), # 100 tokens
        Message(role="assistant", content="E"*400) # 100 tokens
    ]
    
    # Target 350 tokens: should keep sys (100) + last user/assistant (200), skipping early ones
    # The actual implementation of trim_history_by_tokens uses rough_token_count internally inside session_tokens_used? No, wait.
    # Ah, trim_history_by_tokens doesn't take rough_token_count as an argument!
    trimmed = trim_history_by_tokens(messages, max_tokens=350)
    
    assert len(trimmed) == 3
    assert trimmed[0].role == "system"
    assert trimmed[1].content == "D"*400
    assert trimmed[2].content == "E"*400
