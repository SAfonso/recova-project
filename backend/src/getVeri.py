# import hashlib
# import base64
# import secrets
# 
# # Configuración
# CLIENT_ID = "OC-AZxxCtQyCnVQ"
# REDIRECT_URI = "https://n8n.machango.org/rest/oauth2-callback"
# 
# # 1. Generamos el Verifier (El secreto que nos faltaba)
# verifier = secrets.token_urlsafe(80)
# # 2. Generamos el Challenge (Lo que enviamos a Canva)
# challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().replace('=', '')
# 
# # 3. Construimos el enlace de autorización
# url = (
#     f"https://www.canva.com/api/oauth/authorize"
#     f"?code_challenge_method=s256"
#     f"&response_type=code"
#     f"&client_id={CLIENT_ID}"
#     f"&redirect_uri={REDIRECT_URI}"
#     f"&scope=design:meta:read%20design:content:read%20design:content:write"
#     f"&code_challenge={challenge}"
# )
# 
# print(f"1. COPIA ESTE VERIFIER (Guárdalo bien):\n{verifier}\n")
# print(f"2. PINCHA EN ESTE ENLACE Y AUTORIZA:\n{url}")