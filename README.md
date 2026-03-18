# wcc-scripts

A service that syncs paid WCC membership data from CCN (ccnbikes.com) into Discourse user groups. Triggered via HTTP, it downloads the current member list and adds matching Discourse users to the appropriate groups.

---

## Environment Variables

| Variable | Description |
|---|---|
| `CCN_USER` | CCN account username |
| `CCN_PASS` | CCN account password |
| `CCN_REPORT_ID` | The CCN event ID the membership report is scoped to |
| `DISCOURSE_USER` | Discourse admin username for API calls |
| `DISCOURSE_KEY` | Discourse API key (admin-level) |
| `DISCOURSE_HOST` | Full base URL of your Discourse instance, e.g. `https://forum.example.com` |

### Finding `CCN_REPORT_ID`

Log in to CCN, navigate to the event's report dashboard, and grab the `object_id` value from the URL. It's the numeric ID used in the reports API query string.

### Generating a Discourse API Key

In your Discourse admin panel go to **Admin → API → New API Key**. Set the user to your admin account and scope to **Global**.

---

## Setup

### 1. Clone and configure

Copy the env setup script below, fill in your values, and run it:

```bash
#!/usr/bin/env bash
# setup-env.sh — fill in values before running

export CCN_USER="your_ccn_username"
export CCN_PASS="your_ccn_password"
export CCN_REPORT_ID="12345"

export DISCOURSE_USER="your_discourse_admin_username"
export DISCOURSE_KEY="your_discourse_api_key"
export DISCOURSE_HOST="https://forum.yourclub.com"
```

```bash
chmod +x setup-env.sh
source setup-env.sh
```

> For production, set these as secrets in your cloud environment rather than sourcing a local file.

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run locally

```bash
python run.py
# Server starts on http://0.0.0.0:8080

# Trigger a sync:
curl http://localhost:8080/syncmembers
```

---

## Docker

### Build and run

```bash
docker build -t wcc-scripts .

docker run -p 8080:8080 \
  -e CCN_USER="..." \
  -e CCN_PASS="..." \
  -e CCN_REPORT_ID="..." \
  -e DISCOURSE_USER="..." \
  -e DISCOURSE_KEY="..." \
  -e DISCOURSE_HOST="..." \
  wcc-scripts
```

---
 
## Deploying to GCP Cloud Run
 

### Prerequisites
 
```bash
# Install the gcloud CLI if you haven't already:
# https://cloud.google.com/sdk/docs/install
 
# Authenticate
gcloud auth login
 
# Set your project (replace with your actual project ID)
gcloud config set project YOUR_PROJECT_ID
 
# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com
```
 
### 1. Create an Artifact Registry repository
 
```bash
gcloud artifacts repositories create wcc-scripts \
  --repository-format=docker \
  --location=us-central1 \
  --description="WCC sync service"
```
 
### 2. Store secrets in Secret Manager
 
Never pass credentials as plain env vars in production. Store each secret once — the deploy command will reference them by name.
 
```bash
echo -n "your_ccn_username"             | gcloud secrets create CCN_USER         --data-file=-
echo -n "your_ccn_password"             | gcloud secrets create CCN_PASS         --data-file=-
echo -n "12345"                         | gcloud secrets create CCN_REPORT_ID    --data-file=-
echo -n "your_discourse_admin_username" | gcloud secrets create DISCOURSE_USER   --data-file=-
echo -n "your_discourse_api_key"        | gcloud secrets create DISCOURSE_KEY    --data-file=-
echo -n "https://forum.yourclub.com"    | gcloud secrets create DISCOURSE_HOST   --data-file=-
```

### 3. Create a service account for Cloud Run
 
```bash
gcloud iam service-accounts create wcc-scripts-sa \
  --display-name="WCC Scripts Service Account"
 
# Grant it access to read all six secrets
for SECRET in CCN_USER CCN_PASS CCN_REPORT_ID DISCOURSE_USER DISCOURSE_KEY DISCOURSE_HOST; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:wcc-scripts-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```
 
### 4. Build and push the image
 
```bash
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/wcc-scripts/wcc-scripts:latest
```
 
### 5. Deploy to Cloud Run
 
```bash
gcloud run deploy wcc-scripts \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/wcc-scripts/wcc-scripts:latest \
  --platform managed \
  --region us-central1 \
  --service-account wcc-scripts-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --timeout=1200 \
  --memory=512Mi \
  --set-secrets CCN_USER=CCN_USER:latest,CCN_PASS=CCN_PASS:latest,CCN_REPORT_ID=CCN_REPORT_ID:latest,DISCOURSE_USER=DISCOURSE_USER:latest,DISCOURSE_KEY=DISCOURSE_KEY:latest,DISCOURSE_HOST=DISCOURSE_HOST:latest
```
 
> `--timeout=1200` sets a 20-minute request timeout. This is necessary because the CCN report generation step can take up to 15 minutes. Cloud Run's default is 5 minutes and the sync will fail without this.
 
After deploying, grab your service URL:
 
```bash
gcloud run services describe wcc-scripts \
  --region=us-central1 \
  --format="value(status.url)"
```
 
### 6. Set up a Cloud Scheduler trigger
 
This runs the sync automatically every day at 3 AM Eastern. The scheduler authenticates to Cloud Run using OIDC, which works because the service has `--no-allow-unauthenticated`.
 
```bash
# Create a service account for the scheduler to invoke Cloud Run
gcloud iam service-accounts create wcc-scheduler-sa \
  --display-name="WCC Scheduler Invoker"
 
# Grant it permission to invoke the Cloud Run service
gcloud run services add-iam-policy-binding wcc-scripts \
  --region=us-central1 \
  --member="serviceAccount:wcc-scheduler-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
 
# Create the scheduled job (replace the URL with your Cloud Run service URL from step 5)
gcloud scheduler jobs create http wcc-daily-sync \
  --location=us-central1 \
  --schedule="0 3 * * *" \
  --time-zone="America/Toronto" \
  --uri="https://YOUR_CLOUD_RUN_URL/syncmembers" \
  --http-method=GET \
  --oidc-service-account-email=wcc-scheduler-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --oidc-token-audience="https://YOUR_CLOUD_RUN_URL" \
  --attempt-deadline=1200s
```
 
To trigger a sync manually at any time:
 
```bash
gcloud scheduler jobs run wcc-daily-sync --location=us-central1
```
 
### Redeploying after code changes
 
```bash
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/wcc-scripts/wcc-scripts:latest
 
gcloud run deploy wcc-scripts \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/wcc-scripts/wcc-scripts:latest \
  --region us-central1
```
 
---
 

## Notes

- The sync is **additive only** — users are never removed from groups by this script. Membership cleanup must be done manually or extended in code.
- The report generation step can take up to 15 minutes (`report-timeout: 900`). Cloud Run's default request timeout is 5 minutes — increase it to at least 20 minutes when deploying: `--timeout=1200`.