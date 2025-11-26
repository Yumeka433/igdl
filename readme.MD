# Instagram Reels Downloader (Monorepo)

Monorepo containing:
- `api/` — FastAPI serverless function (Python) using yt-dlp to extract direct media URL and stream.
- `frontend/` — Next.js + Tailwind frontend UI.

## Deploy ke Vercel
1. Push ke GitHub.
2. Import project di Vercel. Vercel akan menggunakan `vercel.json` untuk build monorepo.
3. Atur environment variables jika perlu:
   - `CORS_ORIGINS` (default `*`)
   - `RATE_LIMIT` (default `10/minute`)
   - `LOG_LEVEL` (optional)

## Testing lokal
- Backend: (opsional) jalankan `uvicorn api.index:app --port 8000 --reload` (pastikan dependencies terinstall).
- Frontend:
  - `cd frontend && npm install`
  - `npm run dev`

Pastikan `frontend/.env.local` set `NEXT_PUBLIC_API_BASE` ke backend lokal jika diperlukan: