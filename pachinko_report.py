import os
import smtplib
import requests
import google.generativeai as genai
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
import time

# ============================================================
# 定数・設定
# ============================================================
JST = timezone(timedelta(hours=9))
NOW = datetime.now(JST)
today = NOW.strftime("%Y年%m月%d日")
weekday = ["月","火","水","木","金","土","日"][NOW.weekday()]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}

# 複数宛先対応（カンマ区切りで環境変数に設定可能）
# 例: EMAIL_TO="a@gmail.com,b@gmail.com"
def get_recipients():
    raw = os.environ.get("EMAIL_TO", "")
    return [r.strip() for r in raw.split(",") if r.strip()]

# ============================================================
# スクレイピング共通関数
# ============================================================
def scrape(url, max_chars=3000, wait=1.5):
    """指定URLのテキストを取得。wait秒のスリープつき"""
    time.sleep(wait)
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
        text = "\n".join(lines)[:max_chars]
        return text if text else "[コンテンツなし]"
    except Exception as e:
        print(f"    [警告] スクレイプ失敗 {url}: {e}")
        return f"[取得失敗: {e}]"

def scrape_greenbelt_articles(max_articles=5):
    """グリーンべるとのトップページから記事URLを取得し、各記事を取得"""
    print("  → グリーンべると 記事一覧を取得中...")
    top_url = "https://web-greenbelt.jp/"
    try:
        time.sleep(1.5)
        res = requests.get(top_url, headers=HEADERS, timeout=15)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "web-greenbelt.jp" in href and "/news/" in href:
                links.append(href)
            elif href.startswith("/news/"):
                links.append("https://web-greenbelt.jp" + href)
        # 重複除去
        seen = set()
        unique_links = []
        for l in links:
            if l not in seen:
                seen.add(l)
                unique_links.append(l)

        results = []
        for url in unique_links[:max_articles]:
            print(f"    → {url}")
            content = scrape(url, max_chars=1500)
            results.append(f"[記事] {url}\n{content}")
        return "\n\n".join(results) if results else "[記事取得失敗]"
    except Exception as e:
        print(f"    [警告] グリーンべると一覧取得失敗: {e}")
        return f"[取得失敗: {e}]"

# ============================================================
# データ収集
# ============================================================
def collect_papimo_data():
    """パピモレポートからリアルタイムデータを取得"""
    print("【1】パピモレポートからデータ収集中...")
    sources = {
        "パチスロ新台・稼動リアルタイム": "https://report.papimo.jp/ps/",
        "パチスロ稼動ランキング(デイリー)": "https://report.papimo.jp/ps/kado.php?term=0",
        "パチスロ稼動ランキング(週間)": "https://report.papimo.jp/ps/kado.php?term=1",
        "パチスロ勝率ランキング(デイリー)": "https://report.papimo.jp/ps/win_rate.php?term=0",
        "パチスロ最大差ランキング(デイリー)": "https://report.papimo.jp/ps/max_out.php?term=0",
        "パチンコ新台・稼動リアルタイム": "https://report.papimo.jp/pc/",
        "パチンコ稼動ランキング(デイリー)": "https://report.papimo.jp/pc/kado.php?term=0",
        "パチンコ稼動ランキング(週間)": "https://report.papimo.jp/pc/kado.php?term=1",
        "パチンコ勝率ランキング(デイリー)": "https://report.papimo.jp/pc/win_rate.php?term=0",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")
    return "\n".join(results)

def collect_news():
    """業界ニュースを収集"""
    print("【2】業界ニュースを収集中...")
    # 単発URL収集
    sources = {
        "ぱちんこキュレーション（噂・未確定情報）": "https://www.pachinko-curation.com/4820/",
        "グリーンべると トップ": "https://web-greenbelt.jp/",
    }
    results = []
    for name, url in sources.items():
        print(f"  → {name}")
        results.append(f"【{name}】\n{scrape(url)}\n")

    # グリーンべると 個別記事
    print("  → グリーンべると 個別記事スクレイプ...")
    results.append(f"【グリーンべると 最新記事】\n{scrape_greenbelt_articles()}\n")

    return "\n".join(results)

# ============================================================
# レポート生成
# ============================================================
def generate_report(papimo_data, news_data):
    print("【3】Geminiでレポートを生成中...")
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""
あなたは日本のパチンコ・パチスロ業界に精通したシニア・アナリストであり、
パチンコ機械メーカーで21年間BtoB営業を担当してきたベテランでもあります。

以下の本日収集したリアルタイムデータと業界情報をもとに、
{today}（{weekday}曜日）付けの「業界日報」を作成してください。

読者は主に以下の2種類を想定してください：
1. ホール経営者・副店長：経営判断・機種選定の参考にしたい
2. メーカー・代理店の営業担当：今週どこにどうアプローチすべきか知りたい

━━━━━━━━━━━━━━━━━━━━━━━
# パピモレポート（リアルタイム実績データ）
{papimo_data}
━━━━━━━━━━━━━━━━━━━━━━━
# 業界ニュース・噂情報
{news_data}
━━━━━━━━━━━━━━━━━━━━━━━

# 作成ルール
- パピモレポートの具体的な数値（稼動枚数・勝率・最大差）を必ずレポートに反映すること
- 公式発表と個人の推測・噂は必ず区別すること（噂には「※噂レベル」と明記）
- 業界全体に影響しそうなトピックを優先すること
- 「営業アクション提案」は必ず具体的に書くこと
  （例：「今週○○が稼動落ちしているため、代替提案として△△を持参するタイミング」）
- 全体で1800〜2200字程度

# 出力フォーマット（必ずこの形式で）

パチンコ・パチスロ業界日報　{today}（{weekday}曜日）

■ 今日のヘッドライン（3行）
・
・
・

■ 【1】新台リアルタイム速報（パピモレポートデータ）
導入直後の新台について稼動・勝率・最大差などの実績数値を記載。

■ 【2】稼動ランキングTOP5（本日）
1位〜5位を枚数付きで記載・各機種の特徴コメントも添える。
※パチスロ・パチンコ両方記載。

■ 【3】勝率・最大差ランキング
注目機種を数値付きで記載。プレイヤー目線のコメントも添える。

■ 【4】導入予定・業界ニュース
今後の新台スケジュール、メーカー動向、規制情報など。

■ 【5】噂・未確定情報（※噂レベル）
信憑性が高そうな噂を記載。ソースの性質も明記。

■ 【6】アナリストの視点（考察）
数値データをもとにした本日の総括と業界トレンド分析。
21年の現場経験をベースに、数字の背景にある「なぜ」を解説する。

■ 【7】営業アクション提案（今週動くべきポイント）
上記データをもとに、ホール営業担当者が今週取るべき具体的アクションを3点記載。
例：稼動が落ちている機種を設置しているホールへのフォロー提案など。
"""

    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            if attempt < 2:
                wait = 60 * (attempt + 1)
                print(f"  [エラー] Gemini失敗・{wait}秒待機して再試行（{attempt+1}/3）: {e}")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Gemini生成に3回失敗しました: {e}")

# ============================================================
# メール送信
# ============================================================
def build_html(report_text):
    """テキストレポートをHTMLメールに変換"""
    html_lines = []
    in_list = False

    for line in report_text.splitlines():
        if line.startswith("■"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(
                f'<h2 style="color:#c0392b; border-left:4px solid #c0392b; '
                f'padding-left:10px; margin-top:24px;">{line}</h2>'
            )
        elif line.startswith("・") or line.startswith("•"):
            if not in_list:
                html_lines.append('<ul style="padding-left:20px;">')
                in_list = True
            html_lines.append(
                f'<li style="margin:4px 0;">{line[1:].strip()}</li>'
            )
        elif line.strip():
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            # 数字ランキング行は太字
            if line[:2] in ["1位","2位","3位","4位","5位"]:
                html_lines.append(
                    f'<p style="margin:4px 0; font-weight:bold;">{line}</p>'
                )
            else:
                html_lines.append(f'<p style="margin:4px 0;">{line}</p>')

    if in_list:
        html_lines.append("</ul>")

    return f"""
<html>
<body style="font-family:'Hiragino Sans','Meiryo',sans-serif; max-width:750px;
             margin:auto; padding:24px; color:#333; line-height:1.9;">
  <div style="background:linear-gradient(135deg,#c0392b,#8e1a10); color:white;
              padding:20px; border-radius:8px; margin-bottom:24px;">
    <h1 style="margin:0; font-size:22px;">🎰 パチンコ・パチスロ業界日報</h1>
    <p style="margin:6px 0 0; font-size:14px; opacity:0.9;">{today}（{weekday}曜日）</p>
  </div>
  {''.join(html_lines)}
  <hr style="border:1px solid #eee; margin-top:40px;">
  <p style="color:#aaa; font-size:11px; text-align:center; line-height:1.6;">
    データ出典：パピモレポート / グリーンべると / ぱちんこキュレーション<br>
    GitHub Actions + Gemini 2.5 Flash により自動生成
  </p>
</body>
</html>
"""

def send_email(report_text):
    sender    = os.environ["EMAIL_ADDRESS"]
    password  = os.environ["EMAIL_PASSWORD"]
    recipients = get_recipients()

    if not recipients:
        raise ValueError("EMAIL_TO が設定されていません")

    subject = f"【パチンコ業界日報】{today}（{weekday}曜日）"

    print(f"メールを送信中... 宛先: {recipients}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        for recipient in recipients:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = sender
            msg["To"]      = recipient
            msg.attach(MIMEText(report_text, "plain", "utf-8"))
            msg.attach(MIMEText(build_html(report_text), "html", "utf-8"))
            server.sendmail(sender, recipient, msg.as_string())
            print(f"  ✅ 送信完了 → {recipient}")

# ============================================================
# メイン
# ============================================================
if __name__ == "__main__":
    start = time.time()
    print(f"\n{'='*50}")
    print(f" パチンコ業界日報 開始  {today}（{weekday}）")
    print(f"{'='*50}\n")

    try:
        papimo_data = collect_papimo_data()
        news_data   = collect_news()
        report      = generate_report(papimo_data, news_data)

        print("\n" + "="*50)
        print(report)
        print("="*50 + "\n")

        send_email(report)

        elapsed = round(time.time() - start, 1)
        print(f"\n✅ 完了（所要時間: {elapsed}秒）")

    except Exception as e:
        # エラーをメールで通知
        print(f"\n❌ 致命的エラー: {e}")
        try:
            sender   = os.environ["EMAIL_ADDRESS"]
            password = os.environ["EMAIL_PASSWORD"]
            recipients = get_recipients()
            error_subject = f"【エラー】業界日報 生成失敗 {today}"
            error_body = f"業界日報の自動生成中にエラーが発生しました。\n\n{e}"
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender, password)
                for recipient in recipients:
                    msg = MIMEText(error_body, "plain", "utf-8")
                    msg["Subject"] = error_subject
                    msg["From"]    = sender
                    msg["To"]      = recipient
                    server.sendmail(sender, recipient, msg.as_string())
            print("エラー通知メールを送信しました")
        except Exception as mail_err:
            print(f"エラー通知メールも失敗: {mail_err}")
        raise