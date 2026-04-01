import os
import smtplib
import requests
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

JST = timezone(timedelta(hours=9))
today = datetime.now(JST).strftime("%Y年%m月%d日")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def scrape(url, max_chars=2000):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        return f"[取得失敗: {e}]"

def collect_news():
    print("業界ニュースを収集中...")
    sources = {
        "ぱちんこキュレーション": "https://www.pachinko-curation.com/4820/",
        "P-WORLD 新台カレンダー": "https://www.p-world.co.jp/database/machine/introduce_calendar.cgi",
        "ちょんぼりすた": "https://chonborista.com/shindai/4197/",
        "グリーンべると": "https://web-greenbelt.jp/",
        "パチ7": "https://pachiseven.jp/articles/detail/10631",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")
    return "\n".join(results)

def generate_report(raw_news):
    print("Geminiでレポートを生成中...")
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"""
あなたは日本のパチンコ・パチスロ業界に精通したシニア・アナリストです。
以下の本日収集した業界情報をもとに、{today}付けの業界日報を作成してください。

# 本日収集した業界情報
{raw_news}

# 注意事項
- 公式発表と個人の推測・噂は必ず区別すること（噂には「※噂レベル」と明記）
- 業界全体に影響しそうなトピックを優先すること
- 情報が少ない日は「本日は大きな動きなし」と正直に記載すること
- 全体で1500〜2000字程度

# 出力フォーマット

パチンコ業界日報　{today}

■ 今朝のヘッドライン（3行まとめ）
・
・
・

■ 【1】主要ニュース（Webメディア情報）
新台・メーカー動向、行政・規制の動き、ホール経営ニュースを記載。

■ 【2】SNS・掲示板のトレンド・反応
・注目の話題：
・ユーザー・業界人の声：
・未確認情報・噂（※噂レベル）：

■ 【3】アナリストの視点（考察）
本日の総括と業界全体への影響分析。
"""
    response = model.generate_content(prompt)
    return response.text

def send_email(report_text):
    sender    = os.environ["EMAIL_ADDRESS"]
    password  = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_TO"]
    subject   = f"【パチンコ業界日報】{today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient

    msg.attach(MIMEText(report_text, "plain", "utf-8"))

    html_lines = []
    for line in report_text.splitlines():
        if line.startswith("■"):
            html_lines.append(
                f'<h2 style="color:#c0392b; border-left:4px solid #c0392b; padding-left:10px;">{line}</h2>'
            )
        elif line.startswith("・"):
            html_lines.append(f'<li style="margin:4px 0;">{line[1:]}</li>')
        elif "---" in line:
            html_lines.append('<hr style="border:1px solid #eee;">')
        elif line.strip():
            html_lines.append(f'<p style="margin:4px 0;">{line}</p>')

    html_content = f"""
<html>
<body style="font-family:'Hiragino Sans',sans-serif; max-width:750px;
             margin:auto; padding:24px; color:#333; line-height:1.8;">
  <div style="background:#c0392b; color:white; padding:16px;
              border-radius:6px; margin-bottom:20px;">
    <h1 style="margin:0; font-size:20px;">🎰 パチンコ業界日報</h1>
    <p style="margin:4px 0 0; font-size:14px; opacity:0.9;">{today}</p>
  </div>
  {''.join(html_lines)}
  <hr style="border:1px solid #eee; margin-top:32px;">
  <p style="color:#aaa; font-size:11px; text-align:center;">
    GitHub Actions + Gemini により自動生成（完全無料）
  </p>
</body>
</html>
"""
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    print("メールを送信中...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
    print(f"✅ 送信完了 → {recipient}")

if __name__ == "__main__":
    print(f"=== パチンコ業界日報 開始 {today} ===")
    raw_news = collect_news()
    report   = generate_report(raw_news)
    print(report)
    send_email(report)
    print("=== 完了 ===")
