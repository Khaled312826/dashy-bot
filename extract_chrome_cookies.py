import os, json, shutil, sqlite3, base64
from Cryptodome.Cipher import AES
import win32crypt

# Build a list of candidate paths for the cookie DB
user = os.environ["USERPROFILE"]
profile_base = os.path.join(user, "AppData", "Local", "Google", "Chrome", "User Data", "Default")
candidates = [
    os.path.join(profile_base, "Cookies"),
    os.path.join(profile_base, "Network", "Cookies")
]

# Pick the first one that actually exists
for path in candidates:
    if os.path.exists(path):
        COOKIE_DB = path
        break
else:
    raise FileNotFoundError(f"Couldn't find Chrome cookies DB. Tried:\n  " + "\n  ".join(candidates))

LOCAL_STATE = os.path.join(user, "AppData", "Local", "Google", "Chrome", "User Data", "Local State")

def get_master_key():
    with open(LOCAL_STATE, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)[5:]
    return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]

def decrypt_value(enc_value, key):
    iv = enc_value[3:15]
    ciphertext = enc_value[15:]
    cipher = AES.new(key, AES.MODE_GCM, iv)
    plaintext = cipher.decrypt(ciphertext)[:-16]
    return plaintext.decode("utf-8", errors="ignore")

def extract(domain):
    # Copy the DB so Chrome lock isn’t a problem
    tmp = COOKIE_DB + ".tmp"
    shutil.copy2(COOKIE_DB, tmp)

    conn = sqlite3.connect(tmp)
    cursor = conn.cursor()
    cursor.execute("""
      SELECT name, encrypted_value, host_key, path, expires_utc, is_secure, is_httponly
      FROM cookies
      WHERE host_key LIKE ?
    """, (f"%{domain}%",))
    master_key = get_master_key()

    out = []
    for name, enc_val, host, path, expires, secure, httponly in cursor.fetchall():
        val = decrypt_value(enc_val, master_key)
        out.append({
            "name": name,
            "value": val,
            "domain": host,
            "path": path,
            "expires": None if expires == 0 else expires/1e6 - 11644473600,
            "httpOnly": bool(httponly),
            "secure": bool(secure),
            "sameSite": "Lax",
        })
    conn.close()
    os.remove(tmp)
    return out

if __name__ == "__main__":
    domain = "doordash.com"
    print(f"Using cookie DB at: {COOKIE_DB}")
    cookies = extract(domain)
    with open("state.json", "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies, "origins": []}, f, indent=2)
    print(f"✅  Exported {len(cookies)} cookies for {domain} → state.json")
