# Render Deployment Prep Summary

## Files Created
1. `render.yaml` - Render service configuration (API + Web)
2. `api/requirements.txt` - Python dependencies for API

## Files Modified
1. `api/app/__init__.py` - Added Render CORS origin, updated FOF mount point
2. `api/app/routes/asset_review.py` - Fixed hardcoded paths to use relative paths

## Important Notes for Render Deployment

### 1. Runtime Models (UPDATED)
The `.gitignore` has been updated to include production models and database:
- `api/runtime/bus-v2-2.5m.zip` (10.7 MB) - Bus game model
- `api/runtime/lc-v2-low-lr-2m.zip` (3.3 MB) - Lost Cities game model
- `api/runtime/rbgg.db` (389 KB) - SQLite database

Test models in `api/runtime/<game>/` subfolders are still gitignored (4.2 GB total).

These files need to be committed to git for Render deployment.

### 2. Database
The SQLite database (`rbgg.db`) is gitignored. On Render, you'll need to:
- Either commit a seed database, OR
- Initialize the database on first run

### 3. Image Assets
The following directories need to be committed (not gitignored):
- `api/img/` - Game cover images and assets
- `documentation/` - Game documentation and images

### 4. Environment Variables
Set these in Render dashboard:
- `VITE_API_BASE` = `https://rbgg-api.onrender.com/api/v1` (for web service)
- `RBGG_ASSET_REVIEW_ROOT` = `/opt/render/project/src/documentation` (for API)
- `RBGG_CONFIG_ROOT` = `/opt/render/project/src/api/configs` (for API)

### 5. Build Commands
- API: `pip install -r requirements.txt`
- Web: `npm install && npm run build`

### 6. Start Commands
- API: `uvicorn wsgi:app --host 0.0.0.0 --port $PORT`
- Web: `node build`

### 7. Free Tier Limitations
- Render free tier services spin down after 15 minutes of inactivity
- First request after spin-down may take 30-60 seconds
- Consider upgrading to paid tier for production use

### 8. Image Serving
The API serves images from:
- `api/img/` (general mount at `/api/v1/img/`)
- `api/games/bus/` (mounted at `/api/v1/img/bus`)
- `documentation/twilight-struggle/images/` (mounted at `/api/v1/img/twilight-struggle`)
- `api/img/fof/` (mounted at `/api/v1/img/fof`)