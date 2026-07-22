# Monica (people layer) — setup

The PA reads your self-hosted Monica personal CRM to add the **person** dimension (birthdays,
relationships, and — later — person-as-a-thread). Read-only. AGPL-v3, self-hosted (your data
stays yours). See ADR-004.

## 1. Run Monica (Docker, quickest)

```bash
# minimal — see https://github.com/monicahq/monica for the full compose file
docker run -d --name monica -p 8081:80 \
  -e APP_KEY=base64:$(openssl rand -base64 32) \
  -e DB_CONNECTION=sqlite monicahq/monica
# open http://localhost:8081, register, and add a few contacts (or import a CSV)
```

(For anything beyond a trial, use the official docker-compose with MySQL + a persistent
volume so your data survives restarts.)

## 2. Create an API token

Monica → **Settings → API → Create new token** → copy it.

## 3. Point the PA at it

```bash
cp monica.env.example monica.env        # monica.env is git-ignored
# edit monica.env:
#   MONICA_URL=http://localhost:8081
#   MONICA_TOKEN=<the token>
python3 lib/monica.py                    # should list upcoming birthdays
python3 build_pa_dashboard.py            # the People card fills in
```

Tell me once it's up and I'll verify the field mapping against your live API (Monica's exact
JSON shape varies by version) and add the richer bits — "stay in touch" nudges and linking a
person to their mail + meetings + tasks (person-as-a-ZigZag-thread).

## Alternative
If you'd rather not run a server, say so and I'll switch to a light local `data/people.json`
people layer instead (ADR-004 option A1) — same People card, no Monica.
