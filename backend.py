# backend.py
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import os, requests

app = FastAPI()

# Tüm origin'lere izin (Space/website'tan çağrı için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Tarayıcıdan kopyaladığın sessionid'i Render Environment'a IG_SESSIONID olarak kaydettik
def _get_sessionid() -> str:
    return os.getenv("IG_SESSIONID", "").strip()

def _get_ua() -> str:
    ua = os.getenv("IG_USER_AGENT", "").strip()
    if not ua:
        ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
    return ua


def _ig_headers():
    """Instagram web endpoint'i için header + cookie (şifresiz)."""
    if not IG_SESSIONID:
        raise RuntimeError("IG_SESSIONID yok. Render Environment'a ekleyin.")
    return {
        "User-Agent": UA,
        "Referer": "https://www.instagram.com/",
        "Cookie": f"sessionid={IG_SESSIONID};"
    }

@app.get("/")
def root():
    # Sağlık kontrolü için basit yanıt
    return {"status": "ok", "has_session": bool(IG_SESSIONID)}

@app.get("/analyze")
def analyze(username: str = Query(...), limit: int = 60):
    """
    Instagram web_profile_info ile profil + son gönderiler.
    Dönen şema: { profile: {...}, posts: [...] }  (Streamlit'in beklediği yapı)
    """
    try:
        # 1) Profil bilgisi + zaman çizgisi verisi
        url = f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}"
        r = requests.get(url, headers=_ig_headers(), timeout=30)
        if r.status_code != 200:
            return {"error": f"web_profile_info {r.status_code}: {r.text[:200]}"}

        j = r.json()
        user = (j or {}).get("data", {}).get("user")
        if not user:
            return {"error": "Kullanıcı bulunamadı veya erişim kısıtlı."}

        # 2) Profile map
        profile = {
            "username": user.get("username"),
            "full_name": user.get("full_name"),
            "followers": (user.get("edge_followed_by") or {}).get("count"),
            "followees": (user.get("edge_follow") or {}).get("count"),
            "mediacount": (user.get("edge_owner_to_timeline_media") or {}).get("count"),
            "is_private": user.get("is_private"),
            "is_verified": user.get("is_verified"),
            "is_business_account": user.get("is_business_account", False),
            "biography": user.get("biography"),
            "external_url": user.get("external_url"),
            "category_name": user.get("category_name"),
        }

        # 3) Posts map
        edges = (user.get("edge_owner_to_timeline_media") or {}).get("edges", [])
        posts = []
        lim = max(1, min(limit, 60))
        for e in edges[:lim]:
            n = e.get("node", {})
            # caption
            cap_edges = (n.get("edge_media_to_caption") or {}).get("edges", [])
            caption = cap_edges[0]["node"]["text"] if cap_edges else None
            # mediacount
            sidecar = (n.get("edge_sidecar_to_children") or {}).get("edges", [])
            mediacount = len(sidecar) if sidecar else 1
            # taken_at
            ts = n.get("taken_at_timestamp")
            dt = datetime.utcfromtimestamp(ts).isoformat() if ts else None

            posts.append({
                "shortcode": n.get("shortcode"),
                "date_utc": dt,
                "is_video": n.get("is_video"),
                "typename": n.get("__typename", ""),
                "mediacount": mediacount,
                "caption": caption,
                "likes": (n.get("edge_liked_by") or {}).get("count"),
                "comments": (n.get("edge_media_to_comment") or {}).get("count"),
            })

        return {"profile": profile, "posts": posts}

    except Exception as e:
        # Hata mesajını sade döndürüyoruz (Space tarafında gösteriliyor)
        return {"error": str(e)}
