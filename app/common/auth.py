import hashlib
import json
from flask import current_app
from authlib.jose import JsonWebEncryption, JoseError

def get_jwe_key():
    """Derive a 32-byte key from the application secret."""
    secret = current_app.config.get('SECRET_KEY')
    if not secret:
        raise ValueError("SECRET_KEY must be set in app config")
    # SHA-256 produces 32 bytes, perfect for A256KW
    return hashlib.sha256(secret.encode()).digest()

def create_jwe(payload):
    """
    Create a JWE token.

    Args:
        payload (dict): Data to encrypt.

    Returns:
        bytes: The JWE token string (bytes).
    """
    jwe = JsonWebEncryption()
    protected = {'alg': 'A256KW', 'enc': 'A256CBC-HS512'}
    key = get_jwe_key()
    # Serialize dict to json string then bytes
    payload_bytes = json.dumps(payload).encode('utf-8')
    return jwe.serialize_compact(protected, payload_bytes, key)

def decrypt_jwe(token):
    """
    Decrypt a JWE token.

    Args:
        token (bytes or str): The JWE token.

    Returns:
        dict: The decrypted payload or None if invalid.
    """
    try:
        jwe = JsonWebEncryption()
        key = get_jwe_key()
        if isinstance(token, str):
            token = token.encode('utf-8')
        data = jwe.deserialize_compact(token, key)
        # data['payload'] is bytes, need to decode and parse json
        return json.loads(data['payload'].decode('utf-8'))
    except JoseError as e:
        current_app.logger.warning("JWE decryption failed: %s", e)
        return None
    except Exception:
        current_app.logger.exception("Unexpected error during JWE decryption")
        return None
