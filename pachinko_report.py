import os
import smtplib
import requests
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import time

JST = timezone(timedelta(hours=9))
today = datetime.now(JST).strftime("%Y年%m月%d日")
weekday = ["月","火","水","木","金","土","日"][datetime.now(JST).weekday()]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def scrape(url, max_chars=3000):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script","style","nav","footer","header"]):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        return "\n".join(lines)[:max_chars]
    except Exception as e:
        return f"[取得失敗: {e}]"

def collect_papimo_data():
    """パピモレポートからリアルタイムデータを取得"""
    print("パピモレポートからデータ収集中...")
    sources = {
        "パチスロ新台・稼動リアルタイム": "https://report.papimo.jp/ps/",
        "パチスロ稼動ランキング": "https://report.papimo.jp/ps/kado.php?term=0",
        "パチスロ勝率ランキング": "https://report.papimo.jp/ps/win_rate.php?term=0",
        "パチスロ最大差ランキング": "https://report.papimo.jp/ps/max_out.php?term=0",
        "パチンコ新台・稼動リアルタイム": "https://report.papimo.jp/pc/",
        "パチンコ稼動ランキング": "https://report.papimo.jp/pc/kado.php?term=0",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")
    return "\n".join(results)

def collect_news():
    """業界ニュースを収集"""
    print("業界ニュースを収集中...")
    sources = {
        "ぱちんこキュレーション（噂・未確定情報）": "https://www.pachinko-curation.com/4820/",
        "グリーンべると 業界ニュース": "https://web-greenbelt.jp/",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")
    return "\n".join(results)

def generate_report(papimo_data, news_data):
    print("Geminiでレポートを生成中...")
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
あなたは日本のパチンコ・パチスロ業界に精通したシニア・アナリストです。
以下の本日収集したリアルタイムデータと業界情報をもとに、{today}（{weekday}曜日）付けの業界日報を作成してください。

# パピモレポート（リアルタイム実績データ）
{papimo_data}

# 業界ニュース・噂情報
{news_data}

# 注意事項
- パピモレポートの具体的な数値（稼動枚数・勝率・最大差）を必ずレポートに反映すること
- 公式発表と個人の推測・噂は必ず区別すること（噂には「※噂レベル」と明記）
- 業界全体に影響しそうなトピックを優先すること
- 全体で1500〜2000字程度

# 出力フォーマット

パチンコ・パチスロ業界日報　{today}（{weekday}曜日）

■ 今日のヘッドライン（3行）
・
・
・

■ 【1】新台リアルタイム速報（パピモレポートデータ）
導入直後の新台について稼動・勝率・最大差などの実績数値を記載。

■ 【2】稼動ランキングTOP5（本日）
1位〜5位を枚数付きで記載・各機種の特徴コメントも添える。

■ 【3】勝率・最大差ランキング
注目機種を数値付きで記載。

■ 【4】導入予定・業界ニュース
今後の新台スケジュール、メーカー動向、規制情報など。

■ 【5】噂・未確定情報（※噂レベル）
信憑性が高そうな噂を記載。

■ 【6】アナリストの視点（考察）
数値データをもとにした本日の総括と業界トレンド分析。
"""

    # リトライ機能（最大3回）
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if attempt < 2:
                print(f"エラー・60秒待機して再試行（{attempt+1}/3）: {e}")
                time.sleep(60)
            else:
                raise e

def send_email(report_text):
    sender    = os.environ["EMAIL_ADDRESS"]
    password  = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_TO"]
    subject   = f"【パチンコ業界日報】{today}（{weekday}曜日）"

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
        elif line.strip():
            html_lines.append(f'<p style="margin:4px 0;">{line}</p>')

    html_content = f"""
<html>
<body style="font-family:'Hiragino Sans',sans-serif; max-width:750px;
             margin:auto; padding:24px; color:#333; line-height:1.8;">
  <div style="background:#c0392b; color:white; padding:16px;
              border-radius:6px; margin-bottom:20px;">
    <h1 style="margin:0; font-size:20px;">🎰 パチンコ・パチスロ業界日報</h1>
    <p style="margin:4px 0 0; font-size:14px; opacity:0.9;">{today}（{weekday}曜日）</p>
  </div>
  {''.join(html_lines)}
  <hr style="border:1px solid #eee; margin-top:32px;">
  <p style="color:#aaa; font-size:11px; text-align:center;">
    データ出典：パピモレポート｜GitHub Actions + Gemini により自動生成（完全無料）
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
    papimo_data = collect_papimo_data()
    news_data   = collect_news()
    report      = generate_report(papimo_data, news_data)
    print(report)
    send_email(report)
    print("=== 完了 ===")
