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
weekday = ["月","火","水","木","金","土","日"][datetime.now(JST).weekday()]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def scrape(url, max_chars=2000):
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

def collect_finance_news():
    print("金融情報を収集中...")
    sources = {
        "日経平均・株価": "https://finance.yahoo.co.jp/markets/japan/",
        "株式ニュース": "https://finance.yahoo.co.jp/news/",
        "為替レート": "https://finance.yahoo.co.jp/markets/forex/",
        "金相場（田中貴金属）": "https://gold.tanaka.co.jp/commodity/kaitori/",
        "金相場ニュース": "https://gold.tanaka.co.jp/news/",
        "米穀機構": "https://www.komenet.jp/",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")
    return "\n".join(results)

def generate_report(raw_data):
    print("Geminiでレポートを生成中...")
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")
    prompt = f"""
あなたは日本の金融市場に精通したシニアアナリストです。
以下の本日収集した金融情報をもとに、{today}（{weekday}曜日）付けの金融日報を作成してください。

# 本日収集した金融情報
{raw_data}

# 注意事項
- 前日終値・直近値をできるだけ具体的な数字で記載すること
- 数字が取得できない場合は「取得できず」と正直に記載すること
- 市場が休場の場合（土日祝）はその旨を記載すること
- 予想はあくまで参考情報であり、投資判断は自己責任である旨を必ず記載すること
- 全体で2000字程度

# 出力フォーマット（必ずこの形式で）

金融マーケット日報　{today}（{weekday}曜日）

■ 本日のサマリー（3行）
・
・
・

■ 【1】日本株・日経平均
前日終値、騰落率、注目セクターや個別銘柄の動向を記載。

■ 【2】為替（ドル円・ユーロ円）
現在レート、前日比、トレンドの方向感を記載。

■ 【3】金相場
国内金価格（円/g）、NY金先物（ドル/オンス）、前日比を記載。

■ 【4】米相場
国内米価格の動向、需給状況、直近のニュースを記載。

■ 【5】本日のマーケット予想
・日経平均：上昇／横ばい／下落予想と根拠
・ドル円：円高／円安方向と注目材料
・金相場：上昇／下落予想と根拠
・米相場：需給見通し
・本日の総合リスク度：低／中／高（理由も添えること）
※予想はあくまで参考情報です。投資判断は必ずご自身の責任で行ってください。

■ 【6】アナリストの視点（考察）
前日の相場を振り返り、本日注目すべきポイントと中長期的な視点からの考察を記載。
"""
    response = model.generate_content(prompt)
    return response.text

def send_email(report_text):
    sender    = os.environ["EMAIL_ADDRESS"]
    password  = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_TO"]
    subject   = f"【金融マーケット日報】{today}（{weekday}曜日）"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient

    msg.attach(MIMEText(report_text, "plain", "utf-8"))

    html_lines = []
    for line in report_text.splitlines():
        if line.startswith("■"):
            html_lines.append(
                f'<h2 style="color:#1a6496; border-left:4px solid #1a6496; padding-left:10px;">{line}</h2>'
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
  <div style="background:linear-gradient(135deg,#1a6496,#2ecc71); color:white;
              padding:16px; border-radius:6px; margin-bottom:20px;">
    <h1 style="margin:0; font-size:20px;">📈 金融マーケット日報</h1>
    <p style="margin:4px 0 0; font-size:14px; opacity:0.9;">{today}（{weekday}曜日）</p>
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
    print(f"=== 金融マーケット日報 開始 {today} ===")
    raw_data = collect_finance_news()
    report   = generate_report(raw_data)
    print(report)
    send_email(report)
    print("=== 完了 ===")
