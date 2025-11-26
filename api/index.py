# api/index.py
from flask import Flask, request, render_template_string, send_file, redirect, url_for, flash
import requests, io, re
from urllib.parse import urlparse
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change-me")

HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>IG Reel Downloader</title></head>
<body>
  <h2>Instagram Reel Downloader (light)</h2>
  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <ul>
      {% for category, msg in messages %}
        <li style="color:{{ 'crimson' if category=='error' else 'green' }}">{{ msg }}</li>
      {% endfor %}
      </ul>
    {% endif %}
  {% endwith %}
  <form method="post" action="/download">
    <input name="url" placeholder="https://www.instagram.com/reel/CRxxxxx/" style="width:80%" required />
    <button type="submit">Download</button>
  </form>
  <p>Only public posts. No login. Simple extractor: looks for og:video / og:image meta tags.</p>
</body></html>"""

def extract_shortcode(url: str) -> str:
    if not url: return None
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split('/') if p]
    if not parts: return None
    for i,p in enumerate(parts):
        if p.lower() in ('reel','p','tv') and i+1 < len(parts):
            return parts[i+1]
    if len(parts) >= 2: return parts[1]
    return parts[0]

def find_media_url_from_html(html: str):
    # try og:video first, then og:image
    m = re.search(r'<meta[^>]+property=[\'"]og:video[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html, re.I)
    if m: return m.group(1)
    m2 = re.search(r'<meta[^>]+property=[\'"]og:image[\'"][^>]+content=[\'"]([^\'"]+)[\'"]', html, re.I)
    if m2: return m2.group(1)
    # fallback: look for "video_url" in JSON inside page
    m3 = re.search(r'"video_url":"([^"]+)"', html)
    if m3:
        return m3.group(1).replace('\\u0026','&').replace('\\/','/')
    return None

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url','').strip()
    if not url:
        flash('Please provide a URL', 'error'); return redirect(url_for('index'))
    shortcode = extract_shortcode(url)
    if not shortcode:
        flash('Cannot extract shortcode', 'error'); return redirect(url_for('index'))

    # fetch the post page (add headers to mimic browser)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except Exception as e:
        flash(f'Failed to fetch post page: {e}', 'error'); return redirect(url_for('index'))

    media_url = find_media_url_from_html(r.text)
    if not media_url:
        flash('Could not find media URL (Instagram may block unauthenticated access)', 'error'); return redirect(url_for('index'))

    # stream media
    try:
        rr = requests.get(media_url, stream=True, timeout=30, headers=headers)
        rr.raise_for_status()
        ext = '.mp4' if 'video' in rr.headers.get('content-type','') else '.jpg'
        buf = io.BytesIO()
        for chunk in rr.iter_content(8192):
            if chunk: buf.write(chunk)
        buf.seek(0)
        filename = f"{shortcode}{ext}"
        return send_file(buf, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error streaming media: {e}', 'error'); return redirect(url_for('index'))

# no app.run() — Vercel expects exported `app`
