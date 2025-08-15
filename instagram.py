import instaloader
import datetime

# Запоминаем, какие посты уже видели
seen_posts = set()

def get_new_posts(accounts):
    """Возвращает список новых постов (фото/видео + описание)"""
    L = instaloader.Instaloader(download_pictures=False,
                                download_videos=False,
                                save_metadata=False,
                                quiet=True)

    new_posts = []
    for username in accounts:
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            for post in profile.get_posts():
                post_id = f"{username}_{post.shortcode}"
                if post_id not in seen_posts:
                    seen_posts.add(post_id)
                    new_posts.append({
                        "id": post_id,
                        "username": username,
                        "media_url": post.url,
                        "caption": post.caption or "",
                        "is_video": post.is_video
                    })
        except Exception as e:
            print(f"Ошибка при получении {username}: {e}")
    return new_posts
