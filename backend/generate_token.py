import jwt
import datetime
import sys

try:
    secret = "development_secret_key_12345"
    payload = {
        "id": "test-user-123",
        "email": "test@example.com",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    }

    token = jwt.encode(payload, secret, algorithm="HS256")
    
    if isinstance(token, bytes):
        token = token.decode('utf-8')

    with open("backend_py/token.txt", "w") as f:
        f.write(token)
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
