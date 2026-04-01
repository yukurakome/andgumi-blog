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

def get_market_data():
    """Yahoo Finance非公式APIで数値データを取得"""
    print("市場データを取得中...")
    symbols = {
        "日経平均": "^N225",
        "ドル円": "USDJPY=X",
        "ユーロ円": "EURJPY=X",
        "NY金先物": "GC=F",
        "NYダウ": "^DJI",
        "ナスダック": "^IXIC",
    }
    results = {}
    for name, symbol in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            res = requests.get(url, headers=HEADERS, timeout=10)
            data = res.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", "取得できず")
            prev  = meta.get("chartPreviousClose", "取得できず")
            if isinstance(price, float) and isinstance(prev, float):
                change = price - prev
                pct    = (change / prev) * 100
                results[name] = f"{price:,.2f}（前日比 {change:+,.2f} / {pct:+.2f}%）"
            else:
                results[name] = "取得できず"
        except Exception as e:
            results[name] = f"取得できず（{e}）"
    return results

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

def collect_news():
    print("ニュースを収集中...")
    sources = {
        "株式・経済ニュース": "https://finance.yahoo.co.jp/news/",
        "金相場（田中貴金属）": "https://gold.tanaka.co.jp/commodity/kaitori/",
        "米穀機構": "https://www.komenet.jp/",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")
    return "\n".join(results)

def generate_report(market_data, news_data):
    print("Geminiでレポートを生成中...")
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.0-flash")

    market_str = "\n".join([f"・{k}：{v}" for k, v in market_data.items()])

    prompt = f"""
あなたは日本の金融市場に精通したシニアアナリストです。
個人投資家が投資判断の参考にできる、具体的で実践的な金融日報を作成してください。

# 本日の市場データ（リアルタイム取得）
{market_str}

# 本日収集したニュース
{news_data}

# 重要な指示
- 上記の具体的な数値を必ずレポートに反映すること
- 「取得できず」の項目は正直にそのまま記載すること
- 投資判断の参考になる具体的な価格帯・水準を記載すること
- 土日祝で市場休場の場合はその旨を明記すること
- 全体で2000字程度

# 出力フォーマット

金融マーケット日報　{today}（{weekday}曜日）

■ 本日のサマリー（3行）
・
・
・

■ 【1】日本株・日経平均
終値・前日比・騰落率を明記。注目セクターや売買のポイントを記載。

■ 【2】為替（ドル円・ユーロ円）
現在レート・前日比を明記。円高／円安トレンドと輸出入企業への影響。

■ 【3】金相場
NY金先物・前日比を明記。上昇／下落の根拠と今後の見通し。

■ 【4】米相場
国内米価格の動向・需給状況・直近ニュース。

■ 【5】本日のマーケット予想
・日経平均：上昇／横ばい／下落予想と根拠・注目価格帯
・ドル円：円高／円安方向と注目材料・想定レンジ
・金相場：上昇／下落予想と根拠
・米相場：需給見通し
・本日の総合リスク度：低／中／高（理由も添えること）
・今日の注目経済指標・イベント
※投資判断は必ずご自身の責任で行ってください。

■ 【6】個人投資家へのアドバイス
・短期（今週）の戦略
・中期（1ヶ月）の見通し
・今日やるべきこと・避けるべきこと
・注意すべきリスク要因

■ 【7】アナリストの視点（総括）
相場全体の流れ・米国市場との連動・地政学リスク・
日銀FRB政策との関係を踏まえた本日の総括。
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
    ※本レポートは参考情報です。投資判断はご自身の責任で行ってください。<br>
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
    market_data = get_market_data()
    news_data   = collect_news()
    report      = generate_report(market_data, news_data)
    print(report)
    send_email(report)
    print("=== 完了 ===")
