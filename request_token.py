import urllib.request
import urllib.parse
import json
import sys

def get_token(code):
    client_id = "b40dc552427bc1d7d10e67a35e4f18ec"
    client_secret = "ifTHt5vSsyYS9uKM50mWY8miYLPp5dbs"
    redirect_uri = "http://localhost"

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code.strip(),
        "client_secret": client_secret
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://kauth.kakao.com/oauth/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"}
    )

    try:
        with urllib.request.urlopen(req) as res:
            res_body = res.read().decode("utf-8")
            token_json = json.loads(res_body)
            refresh_token = token_json.get("refresh_token")
            
            with open(".env", "r", encoding="utf-8") as f:
                content = f.read()
            
            lines = content.splitlines()
            found = False
            new_lines = []
            for line in lines:
                if line.startswith("KAKAO_REFRESH_TOKEN="):
                    new_lines.append(f"KAKAO_REFRESH_TOKEN={refresh_token}")
                    found = True
                else:
                    new_lines.append(line)
            if not found:
                new_lines.append(f"KAKAO_REFRESH_TOKEN={refresh_token}")
            
            with open(".env", "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            
            print(f"SUCCESS: KAKAO_REFRESH_TOKEN has been saved to .env")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"FAILED: {e.code} - {err_body}")
        return False
    except Exception as ex:
        print(f"ERROR: {ex}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        get_token(sys.argv[1])
    else:
        print("Usage: python request_token.py <AUTH_CODE>")
