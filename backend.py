from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import instaloader

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "message": "Instagram backend çalışıyor"}

@app.get("/analyze")
def analyze(username: str, limit: int = 60):
    try:
        L = instaloader.Instaloader(
            download_pictures=False, download_videos=False,
            download_video_thumbnails=False, download_geotags=False,
            compress_json=False, save_metadata=False, quiet=True
        )
        profile = instaloader.Profile.from_username(L.context, username)
        posts = []
        for i, p in enumerate(profile.get_posts()):
            if i >= limit: break
            posts.append({
                "shortcode": p.shortcode,
                "date_utc": p.date_utc.isoformat(),
                "is_video": bool(p.is_video),
                "typename": getattr(p, "typename", ""),
                "mediacount": getattr(p, "mediacount", 1),
                "caption": p.caption,
                "likes": getattr(p, "likes", None),
                "comments": getattr(p, "comments", None),
            })
        payload = {
            "profile": {
                "username": profile.username,
                "full_name": profile.full_name,
                "followers": profile.followers,
                "followees": profile.followees,
                "mediacount": profile.mediacount,
                "is_verified": profile.is_verified,
                "is_private": profile.is_private,
                "is_business_account": profile.is_business_account,
                "biography": profile.biography,
                "external_url": profile.external_url,
                "category_name": getattr(profile, "category_name", None),
            },
            "posts": posts
        }
        return payload
    except instaloader.exceptions.ProfileNotExistsException:
        return {"error": "Profil bulunamadı"}
    except instaloader.exceptions.PrivateProfileNotFollowedException:
        return {"error": "Hesap özel (şifresiz çekilemez)"}
    except Exception as e:
        return {"error": str(e)}
