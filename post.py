import os
import requests
import random
from datetime import datetime
import google.generativeai as genai
from requests.auth import HTTPBasicAuth

# --- 環境変数（GitHub Actionsから取得） ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
WP_USER = os.environ.get("WP_USER")
WP_PASSWORD = os.environ.get("WP_PASSWORD")
WP_URL = os.environ.get("WP_URL")
UNSPLASH_KEY = os.environ.get("UNSPLASH_KEY")

genai.configure(api_key=GEMINI_API_KEY)

def generate_content():
    model = genai.GenerativeModel("gemini-2.5-flash")
    weekday = datetime.now().weekday()
   
    # 腸活テーマ
    themes = [
        "腸内環境を整える『最強の発酵食品・食材』の栄養と効果", # 月
        "腸をパッと目覚めさせる『朝のルーティンと習慣』",       # 火
        "手軽に続けられる『美味しい腸活レシピと献立』",        # 水
        "ぽっこりお腹を解消する『簡単な腸活運動・ストレッチ』", # 木
        "自律神経を整えて腸を元気にする『心のケアと睡眠』",     # 金
        "忙しい人のための『コンビニや外食でできる腸活選び』",   # 土
        "腸内環境を整えて健康と美肌を手に入れる『究極のヒント』" # 日
    ]
   
    selected_theme = themes[weekday]
    prompt = f"あなたは腸活アドバイザーです。今日は「{selected_theme}」というテーマで、読者の健康と美容に役立つブログ記事を、親しみやすく丁寧な日本語で作成してください。\n\n出力形式：\n【TITLE】タイトル\n【KEYWORD】画像検索用英語(1語)\n【BODY】本文(Markdown)"
   
    response = model.generate_content(prompt)
    raw_text = response.text
    try:
        title = raw_text.split("【TITLE】")[1].split("【KEYWORD】")[0].strip()
        image_keyword = raw_text.split("【KEYWORD】")[1].split("【BODY】")[0].strip()
        content = raw_text.split("【BODY】")[1].strip()
    except:
        title = f"今日から始める腸活習慣 {datetime.now().strftime('%Y-%m-%d')}"
        image_keyword = "healthy food"
        content = raw_text
    return title, image_keyword, content

if __name__ == "__main__":
    if not WP_URL:
        print("エラー: WP_URLが未設定です")
    else:
        ai_title, ai_keyword, ai_body = generate_content()
        img_res = requests.get(f"https://api.unsplash.com/search/photos?query={ai_keyword}&client_id={UNSPLASH_KEY}&per_page=30")
        try:
            img_url = random.choice(img_res.json()["results"])["urls"]["regular"]
        except:
            img_url = "https://images.unsplash.com/photo-1490645935967-10de6ba17061"

        full_body = f'<img src="{img_url}" style="width:100%; border-radius:10px;"><br><br>{ai_body}'
        response = requests.post(f"{WP_URL.rstrip('/')}/wp-json/wp/v2/posts",
            auth=HTTPBasicAuth(WP_USER, WP_PASSWORD),
            json={"title": ai_title, "content": full_body, "status": "publish"})
        print(f"結果: {response.status_code}")
