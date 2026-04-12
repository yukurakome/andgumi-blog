import os
import requests
import random
from datetime import datetime
import google.generativeai as genai
from requests.auth import HTTPBasicAuth

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_USER = os.environ.get("WP_USER")
WP_PASSWORD = os.environ.get("WP_PASSWORD")
WP_URL = os.environ.get("WP_URL")
UNSPLASH_KEY = os.environ.get("UNSPLASH_KEY")

genai.configure(api_key=GEMINI_API_KEY)

def generate_content():
    model = genai.GenerativeModel("gemini-2.5-flash")
    weekday = datetime.now().weekday()  # 1=火, 3=木, 6=日

    # 火曜：生活習慣系
    if weekday == 1:
        theme = "腸をパッと目覚めさせる『朝のルーティンと習慣』"
        image_kw = "morning routine healthy"

    # 木曜：食事系（発酵食品とレシピを週替わり）
    elif weekday == 3:
        week_num = datetime.now().isocalendar()[1]
        if week_num % 2 == 0:
            theme = "腸内環境を整える『最強の発酵食品・食材』の栄養と効果"
            image_kw = "fermented food japanese"
        else:
            theme = "手軽に続けられる『美味しい腸活レシピと献立』"
            image_kw = "healthy gut recipe"

    # 日曜：運動系
    else:
        theme = "ぽっこりお腹を解消する『簡単な腸活運動・ストレッチ』"
        image_kw = "yoga stretching wellness"

    prompt = f"""あなたは腸活アドバイザーの安堵來未(あんどくみ)です。
今日は「{theme}」というテーマで、30〜40代の健康・美容に関心のある女性向けに、
親しみやすく丁寧な日本語でブログ記事を作成してください。

出力形式：
【TITLE】タイトル
【KEYWORD】{image_kw}
【BODY】本文(Markdown)"""

    response = model.generate_content(prompt)
    raw_text = response.text
    try:
        title = raw_text.split("【TITLE】")[1].split("【KEYWORD】")[0].strip()
        image_keyword = raw_text.split("【KEYWORD】")[1].split("【BODY】")[0].strip()
        content = raw_text.split("【BODY】")[1].strip()
    except:
        title = f"今日から始める腸活習慣 {datetime.now().strftime('%Y-%m-%d')}"
        image_keyword = image_kw
        content = raw_text
    return title, image_keyword, content

if __name__ == "__main__":
    if not WP_URL:
        print("エラー: WP_URLが未設定です")
    else:
        ai_title, ai_keyword, ai_body = generate_content()
        img_res = requests.get(
            f"https://api.unsplash.com/search/photos?query={ai_keyword}&client_id={UNSPLASH_KEY}&per_page=30"
        )
        try:
            img_url = random.choice(img_res.json()["results"])["urls"]["regular"]
        except:
            img_url = "https://images.unsplash.com/photo-1490645935967-10de6ba17061"

        full_body = f'<img src="{img_url}" style="width:100%; border-radius:10px;"><br><br>{ai_body}'
        response = requests.post(
            f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(WP_USER, WP_PASSWORD),
            json={"title": ai_title, "content": full_body, "status": "publish"}
        )
        print(f"結果: {response.status_code}")
