# api/index.py
from flask import Flask, request, render_template_string, send_file, redirect, url_for, flash
import instaloader
from urllib.parse import urlparse
import requests
import io
import os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "change-me")

# Instaloader context (no login)
L = instaloader.Instaloader(download_videos=False)

HTML = """<!doctype html>
<html>
  <head><meta charset="utf-8"><title>IG Reel Downloader</title></head>
  <body>
    <h2>Instagram Reel Downloader</h2>
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
    <p>Works only with public posts (no login/token).</p>
  </body>
</html>"""

def extract_shortcode(url: str) -> str:
    if not url:
        return None
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    if not path_parts:
        return None
    for i, part in enumerate(path_parts):
        if part.lower() in ('reel', 'p', 'tv') and i + 1 < len(path_parts):
            return path_parts[i + 1]
    if len(path_parts) >= 2:
        return path_parts[1]
    return path_parts[0]

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/download', methods=['POST'])
def download():
    url = request.form.get('url', '').strip()
    if not url:
        flash('Please provide a URL', 'error')
        return redirect(url_for('index'))

    shortcode = extract_shortcode(url)
    if not shortcode:
        flash('Could not extract shortcode from URL', 'error')
        return redirect(url_for('index'))

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except Exception as e:
        flash(f'Failed to load post: {e}', 'error')
        return redirect(url_for('index'))

    # choose media url
    media_url = None
    filename = shortcode
    if getattr(post, 'is_video', False):
        media_url = getattr(post, 'video_url', None)
        filename += '.mp4'
    else:
        media_url = getattr(post, 'url', None)
        filename += '.jpg'

    if not media_url:
        flash('No direct media URL available for this post', 'error')
        return redirect(url_for('index'))

    # stream media to memory and return
    try:
        resp = requests.get(media_url, stream=True, timeout=20)
        resp.raise_for_status()
        buf = io.BytesIO()
        for chunk in resp.iter_content(8192):
            if chunk:
                buf.write(chunk)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error downloading media: {e}', 'error')
        return redirect(url_for('index'))

# NOTE: Do NOT run app.run() — Vercel will call the exported `app` object.
