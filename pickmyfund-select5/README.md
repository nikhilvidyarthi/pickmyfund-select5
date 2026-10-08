# PickMyFund Select 5 – dashboard

Internal dashboard for the PickMyFund Select 5 mutual fund model.

- `public/index.html` – the page Netlify serves.
- `build/` – generator (`gen_dash.py`), page template, quarterly holdings (`sched.json`) and current picks/sector table (`dash_static.json`).
- `.github/workflows/refresh.yml` – runs every Tuesday–Saturday at 07:30 IST: fetches the latest NAVs from api.mfapi.in, rebuilds `public/index.html` and commits it. Netlify redeploys automatically on each commit.

## One-time setup

1. Create a **private** GitHub repository and upload the contents of this folder (keep the `.github` folder).
2. In the repository: **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**.
3. In Netlify: **Add new site → Import an existing project → GitHub →** pick this repository. Leave the build command empty; publish directory is `public` (read from `netlify.toml`). Deploy.
4. For internal-only access: **Site configuration → Access control → Password protection** (or Netlify's team-only visitor access).
5. Test: in GitHub, **Actions → Refresh Select 5 dashboard → Run workflow**. A new commit appears and Netlify redeploys within a minute.

## Quarterly review (Jan / Apr / Jul / Oct)

Replace `build/sched.json` (append the new review's holdings) and `build/dash_static.json` (new-client picks and NGEN sector table), then commit. The next daily run picks them up.

If a NAV fetch fails, the workflow stops without committing, so the live page keeps the last good version.
