# import requests
# import base64
# 
# CLIENT_ID = "OC-AZxxCtQyCnVQ"
# CLIENT_SECRET = "cnvca8PQydL23YDF5j8oXTAdCqdJ3qZJaRihii0s3Dsa9y5k92407bf5"
# 
# auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
# auth_b64 = base64.b64encode(auth_str.encode()).decode()
# 
# headers = {
#     "Authorization": f"Basic {auth_b64}",
#     "Content-Type": "application/x-www-form-urlencoded"
# }
# 
# data = {
#     "grant_type": "authorization_code",
#     "code_verifier": "PCuWP95Vnq-vx2qoWZqnMus6E0DG4Dw_vJy3wrLenMR-Cj3d7c-V0vreRR-w45bsH79IawwrPPiUzk0gH-dsKuFRs-vcZUVphuu9QdLD9Yo",
#     "code": "eyJraWQiOiI0ZDBiNDcwMS03NjNmLTQwZWYtOTNiNC00ZjMyOTBhNDFmOGUiLCJhbGciOiJSUzI1NiJ9.eyJqdGkiOiJMMUxheGNQTlZ3c29xU1pGalIzajlRIiwiY2xpZW50X2lkIjoiT0MtQVp4eEN0UXlDblZRIiwiYXVkIjoiaHR0cHM6Ly93d3cuY2FudmEuY29tIiwiaWF0IjoxNzcxNDQyODU0LCJuYmYiOjE3NzE0NDI4NTQsImV4cCI6MTc3MTQ0MzQ1NCwicm9sZXMiOiI2MGYwYXBNN011bXBZN1FocUJEeXM2RXUxSEZ3YVU5VDgwbXBtREQ5c2tjT2pnUU9aOWFDLUdnYms1aThlc2lEOUxFWTlvUGxHRzl5clBtTXFXNnBYclJjdXhkNXF6YlBLVXhwcHFaSDA2UGtTQmVDM0hYZWVuYlBoNF95WVNveER3a202ZyIsInN1YiI6Im9VWUgyLW1ubDlSeGo3LTZfVUc1VlUiLCJicmFuZCI6Im9CWUgyc1BkVElJRDBpSkIyM2hCOHMiLCJzY29wZXMiOlsiZGVzaWduOm1ldGE6cmVhZCIsImRlc2lnbjpjb250ZW50OnJlYWQiLCJkZXNpZ246Y29udGVudDp3cml0ZSJdLCJsb2NhbGUiOiJCV1o3S2hXX1psS0tMUTM4RlhuZGhLY0UyN1JYUDRhdVFtRnA3a3kwc0pKT1JQZ2w3UnRTd0xmVnJBN2VQYjN0MGNvaVZBIiwiYnVuZGxlcyI6WyJQUk9TIl0sInBrY2UiOiJIUWQxV3Y5QTNXTEM1c1Q0dmRxWHcwT3dWcWtiak5HeTFQN0Y1M0JsWWFjMFJmcEt4a0RFWWN3aTZTeUhkOEVVdXBjczJEcGVKTV9KQ0JoRkNyR3c1NHotOGpabXRYT0oySG51YXRuNERGUkJudVFyIiwicmVkaXJlY3RfdXJpIjoiaHR0cHM6Ly9uOG4ubWFjaGFuZ28ub3JnL3Jlc3Qvb2F1dGgyLWNhbGxiYWNrIn0.ICrPrKGcWNN2YxZSsE0NrHme_8ZD_wMD4ySyifJ_WnqlhkOvngCMlNW4QpQfHQHUEI7RZR_M5q_VUAXWOOthW67p0VZHVa77C0gTNAfzJ8Z-PJKsdZ6eRjHecJ_Bu8qYCMT6wBa4rlfy0UBb5wPP0POLYpoC7W-PeC4E8d6gaKNWyzQhT1-1BWkPkx4Y3Z9sYIWtf_eccaj-b2iX7z130KkxNeG8Kfvmdfwe9PTTuoPqPiD2cqQuJfs-gOjkpNDqiSIGjAFr01C1fm5qH4PTapPt2l1GLYenW7e6FuZRo_UYM-BEPZFjeIWij4ZEf7JrhZO1eCKvxPcQR_FOD5UGiQ",
#     "redirect_uri": "https://n8n.machango.org/rest/oauth2-callback",
# }
# 
# response = requests.post("https://api.canva.com/rest/v1/oauth/token",
#     headers=headers,
#     data=data
# )
# print(response.json())