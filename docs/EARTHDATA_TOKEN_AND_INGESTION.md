# Earthdata Token and Live Ingestion

## Your token (profile bearer token)

The **Bearer Token** you generate from your Earthdata Login profile is the right kind of token for AERIS:

- **Where:** [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov) → **My Profile** → **Generate Token**
- **Use in .env:** `BEARER_TOKEN=<paste token here>`
- **Expiry:** Tokens can expire (e.g. “Expires at: 04-15-2026”); regenerate from the same page if you start getting 403.

Your profile (username, Science Team, etc.) does not need to change. The token alone is used for Harmony requests.

## What we verified

1. **Token is accepted**  
   With your current `BEARER_TOKEN` in `.env`, requests to **production** Harmony (`harmony.earthdata.nasa.gov`) no longer return **403 Forbidden**. So the token from your profile is valid for production.

2. **400 “No matching granules”**  
   For the time/bbox we tried (last completed hour UTC, small California bbox), Harmony responded with:
   ```json
   {"code":"harmony.RequestValidationError","description":"Error: No matching granules found."}
   ```
   That means:
   - The request format (URL, subset, time, bbox) is valid.
   - There are simply no TEMPO granules in the catalog for that exact time/region. TEMPO coverage and ingestion delay can vary.

3. **403 vs 400**  
   - **403:** Authentication/authorization problem (wrong token, expired token, or wrong environment).  
   - **400 + “No matching granules”:** Auth is fine; no data for that request (try another time or bbox).

## EULAs and applications

From the profile text: *“The token will only authorize for applications that are EDL compliant and do not have unapproved EULAs.”*

If you ever see **403** again after refreshing the token:

- In **My Profile**, open **Applications** and **EULAs**.
- Approve any EULA or application that is required for the TEMPO/LARC data you are requesting.

For the request we ran, 403 did not occur with your current token.

## Getting a successful live fetch

To actually download a GeoTIFF and see data end-to-end:

1. **Keep using production**  
   Do **not** set `HARMONY_USE_UAT=1` when using a token from [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov).

2. **Choose a time with TEMPO data**  
   - TEMPO data is available from Aug 2023 onward.  
   - Use [Earthdata Search](https://search.earthdata.nasa.gov) or CMR to find dates/times that have TEMPO granules for your region, then use that time range in the scheduler or in `run_ingestion_validation.py`.

3. **Run live validation**  
   ```bash
   INGESTION_LIVE=1 python -m tests.run_ingestion_validation
   ```  
   The script tries the last completed hour, then the same hour 7 days ago. If granules exist for one of those, you’ll get “OK: GeoTIFF fetched and readable” and “OK: Processed N grid rows”.

4. **Celery scheduler**  
   When `fetch_tempo_hourly` runs (e.g. via Celery Beat), it uses the same token and the same Harmony URL pattern. Once a requested hour has granules available, the scheduler will fetch and process them.

## Summary

- **Profile token:** Use the “Generate Token” value from [urs.earthdata.nasa.gov](https://urs.earthdata.nasa.gov) in `.env` as `BEARER_TOKEN`.
- **Auth:** Confirmed working for production Harmony (no 403 with your current token).
- **“No matching granules”:** Expected when that time/bbox has no TEMPO data; adjust time/bbox or wait for ingestion.
- **EULAs:** If you see 403 later, check Applications/EULAs in My Profile and approve anything required for the data you need.
