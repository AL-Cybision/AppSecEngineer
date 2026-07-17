from app.security import generate_token, hash_password, hash_token, verify_password


def test_password_hashing_and_tokens() -> None:
    encoded = hash_password("correct horse battery")
    assert "correct horse battery" not in encoded
    assert verify_password("correct horse battery", encoded)
    assert not verify_password("wrong password", encoded)
    token_a = generate_token()
    token_b = generate_token()
    assert token_a != token_b
    assert len(hash_token(token_a)) == 64
    assert token_a not in hash_token(token_a)
