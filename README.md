# Central Bank Interest Rates -> Email (runs on GitHub Actions, no local computer needed)

This repo emails you a daily summary of **both** the policy rate and the
average commercial bank deposit rate for six major economies,
automatically, using GitHub's free scheduled-workflow runners. Nothing
needs to run on your own machine.

**Why two rates:** a central bank's policy rate (e.g. SBV's 4.5%
refinancing rate) is what it charges *commercial banks* — it is not what
those banks pay you as a saver or charge you as a borrower. Commercial
deposit/lending rates are set independently by each bank based on market
conditions, and are usually higher (that's why you might see a bank
advertising 6-8% on a term deposit while the central bank's own rate sits
at 4.5% — both numbers are correct, they're just different things). The
email shows both side by side so that's clear at a glance.

## Rates tracked

| Central bank | Policy rate | Deposit rate | Source |
|---|---|---|---|
| US Federal Reserve | Fed Funds target rate | Avg. commercial deposit rate | FRED API (policy, needs a free key) + TradingEconomics (deposit) |
| European Central Bank | Main refinancing rate | Avg. commercial deposit rate | ECB Statistical Data Warehouse API (policy) + TradingEconomics (deposit) |
| Bank of England | Bank Rate | Avg. commercial deposit rate | BOE public statistics page (policy) + TradingEconomics (deposit) |
| Bank of Japan | Policy rate | Avg. commercial deposit rate | TradingEconomics (both, scraped) |
| People's Bank of China | Loan Prime Rate | Avg. commercial deposit rate | TradingEconomics (both, scraped) |
| State Bank of Vietnam | Refinancing rate | Avg. commercial deposit rate | TradingEconomics (both, scraped) |

The Fed, ECB, and BOE have clean official data feeds for their *policy*
rate and should stay reliable long-term. BOJ, PBOC, and SBV don't publish
a clean, scrapable English number on their own sites — BOJ's decisions are
PDFs with no rate in the surrounding page text, PBOC's English news index
mixes unrelated headlines in with rate releases, and SBV's site is a noisy
multi-widget portal. Those three (plus the *deposit* rate for all six
economies, since none of the official sources above publish that) are
instead read from [TradingEconomics](https://tradingeconomics.com), which
reports every country's rates in the same plain-English sentence format
regardless of country, which is far more reliably parsed than each site's
own differently-structured page. If one of them starts reporting
"unavailable", that sentence format probably changed; check
`fetch_te_rate()` / `fetch_te_deposit_rate()` in `interest_rate_emailer.py`.
TradingEconomics doesn't offer a free public API, hence the scrape — if
you'd rather use an authoritative source per bank, each one's official
site is still linked in the email footer.

Note that "average commercial deposit rate" is a broad national average
(often World-Bank-sourced and updated annually for smaller economies) —
it's a useful ballpark for "what banks generally pay," not a specific
promotional rate any one bank is currently advertising. A specific bank's
current term-deposit rate can run higher or lower than this average.

**Vietnam specifically**: TradingEconomics' deposit-rate figure for
Vietnam is stuck on a 2023 World Bank data point (4.78%) as of when this
was written — there's no more recent free, cleanly-scrapable figure for
it. If you've seen banks advertise 6-8% on VND term deposits, that's not
wrong; it's just a different, more current number than the stale national
average this repo can automate. The email flags any deposit rate that's a
bare annual figure more than a year old with an "annual figure, may be
outdated" badge, specifically so this one doesn't get mistaken for a
current number.

## Vietnam commercial banks (10 banks, every term)

Because the national-average deposit rate above isn't the number most
people actually want, the email also has a second section with each
bank's own advertised savings rates — **every term the bank lists, both
at-counter and online** — for:

Vietcombank, Techcombank, BIDV, VietinBank, MB Bank, ACB, VPBank,
Sacombank, HDBank, and TPBank.

**All ten are read from one source: [24hmoney.vn](https://24hmoney.vn)'s
per-bank rate page**, not each bank's own site. This wasn't the first
approach tried — Vietcombank's own rate page turned out to be populated by
client-side JavaScript (empty in the raw HTML), and Techcombank's
equivalent page is an interactive calculator with no static table at all,
both of which needed increasingly heavy workarounds (a headless browser,
then PDF-parsing) that were fragile and slow. 24hmoney.vn's page is plain
server-rendered HTML — the numbers are present in the raw HTTP response,
confirmed directly — with the *same* table format for every bank, so one
simple `requests.get()` (no browser, no PDF library) now covers all ten.

Each bank's page has two tables: "tại Quầy" (at the counter — the
standard, walk-in rate) and "Trực tuyến" (online, usually noticeably
higher — that gap is each bank's incentive to get you using the app
instead of a branch, and the online figure is what actually matches the
rate shown in a bank's own app). The email shows both, side by side, for
every term the bank publishes (typically 1/3/6/9/12 months, sometimes
more) — not just a single headline number. Each term row also gets its
own "changed" badge if that specific term/channel moved since the last
run. If a bank's page layout changes and no rows can be parsed, the error
includes a snippet of what the page actually contained, so a failure is
diagnosable from the email itself rather than requiring another round of
guessing — check `fetch_bank_all_rates()` in `interest_rate_emailer.py`
against whatever that snippet shows.

Each bank also offers new-customer promotions and balance-tiered rates
not captured here (e.g. a large-balance tier can run above the standard
listed rate for the same term) — the listed rates are a reasonable
comparison point, not necessarily the *best* rate any given bank
currently offers.

If any single bank fails to fetch, only that bank's block notes the
failure — the rest of the email still generates and sends normally.

## Special products (Certificates of Deposit)

Separate from both sections above, the email has a third card for
**Certificates of Deposit** — a fundamentally different product from a
regular savings account, currently tracking:

- **Vietcombank** — "Chứng chỉ tiền gửi trực tuyến"
- **Techcombank** — "Chứng chỉ tiền gửi Bảo Lộc" (Bao Loc CD)

What makes these different from regular savings:

- Bond-like: fixed term, cannot be withdrawn early
- But transferable — Vietcombank's can be sold on to Vietcombank
  Securities (VCBS) or used as loan collateral; Techcombank's can be
  transferred to another holder via the app
- Priced noticeably higher than each bank's regular savings rate (this
  is *why* they exist — a higher-yield alternative for customers who
  don't need instant liquidity)
- The two banks structure this differently: Vietcombank sells fixed
  6/9/12-month terms in periodic limited-scale issuances; Techcombank's
  is an always-open product priced by exact holding period (days to
  months) rather than fixed terms

This is why a bank can simultaneously show ~5.9% on regular savings and
~7.9% on this product — both are accurate, they're just different
things. If you've seen a rate above 7% "in the app" that didn't match
the regular savings table, this is almost certainly it.

**Sources**: rather than trying to track individual news articles about
each new issuance or rate change (which a script has no reliable way to
discover on its own), this reads each bank's own permanent product page,
which they keep updated with the current headline rate:

- Vietcombank: https://www.vietcombank.com.vn/vi-VN/KHCN/SPDV/Dau-tu/Chung-chi-tien-gui-truc-tuyen
  — confirmed server-rendered, rate present in the raw HTML as
  "Lãi suất hấp dẫn đến X%/năm"
- Techcombank: https://techcombank.com/en/personal/save/certificate-of-deposit
  — confirmed server-rendered, rate present in the raw HTML as
  "Attractive profit up to X%/year (\*) for 3M holding" — note this is
  specifically the 3-month-holding figure, Techcombank's own headline
  comparison point, not necessarily the maximum available at other
  holding periods

**Only these two are tracked here.** They're the ones that came up in
conversation; other banks may or may not run an equivalent product, and
each would need its own page checked the same way these two were before
adding it. If a bank has no issuance open (Vietcombank specifically —
Techcombank's is always-open) when the script runs, expect "unavailable"
rather than a stale old figure — the fetcher looks for a live headline
rate, not a cached one.

## One-time setup (~5 minutes)

1. **Create a GitHub account** if you don't have one: https://github.com/join

2. **Create a new repository**
   - Click "+" (top right) -> "New repository"
   - Name it anything, e.g. `interest-rate-emailer`
   - Set it to **Private** (recommended, keeps your workflow config private)
   - Click "Create repository"

3. **Upload these files** to the repo (drag-and-drop works fine via the
   GitHub web UI: "Add file" -> "Upload files"), keeping the folder structure:
   - `interest_rate_emailer.py`
   - `requirements.txt`
   - `.github/workflows/send-interest-rate.yml`

4. **Get a free FRED API key** (needed for the Fed rate):
   - https://fred.stlouisfed.org/docs/api/api_key.html

5. **Create a Gmail App Password** (your normal Gmail password won't work):
   - Turn on 2-Step Verification: https://myaccount.google.com/signinoptions/two-step-verification
   - Then create an app password: https://myaccount.google.com/apppasswords
   - Choose "Mail" as the app, copy the 16-character password it gives you.

6. **Add your secrets to the repo** (this keeps your email/password/key out of the code):
   - In your repo: Settings -> Secrets and variables -> Actions -> "New repository secret"
   - Add four secrets:
     - `GMAIL_ADDRESS` = your Gmail address
     - `GMAIL_APP_PASSWORD` = the 16-character app password from step 5
     - `INTEREST_RATE_RECIPIENT` = the email address that should receive the summary
     - `FRED_API_KEY` = the key from step 4

7. **Test it manually**
   - Go to the "Actions" tab in your repo
   - Click "Send Interest Rate Summary" on the left
   - Click "Run workflow" -> "Run workflow" (green button)
   - Wait ~15-20 seconds, refresh, click into the run to see logs / confirm success
   - Check the recipient inbox for the email

That's it — from now on it runs automatically on the schedule below, with
no computer of yours needing to be on.

## Schedule

```
- cron: "*/30 * * * *"
```

Runs every 30 minutes (cron is always in UTC), matching the cadence of the
other `*-emailer` repos. This line should not be changed.

## Only emailing on rate changes

By default the workflow sends an email on **every** scheduled run, whether
or not any rate has actually moved since last time. If you'd rather only
get emailed when a rate changes, open
`.github/workflows/send-interest-rate.yml`, find `SEND_ONLY_ON_CHANGE:
"false"` under the "Generate email" step, and change it to:

```
SEND_ONLY_ON_CHANGE: "true"
```

With that on, `generate` compares this run's rates against the last saved
snapshot — stored in `last_rates.json` on a dedicated
`interest-rate-state` branch the workflow creates/updates automatically —
and skips the email if nothing changed.

## Notes

- GitHub Actions free tier includes 2,000 minutes/month for private repos —
  this job takes a few seconds a run, so it's effectively free even at a
  daily cadence.
- You can also trigger it manually anytime via the "Run workflow" button.
- If a run fails, check the Actions tab -> the failed run -> logs. Common
  causes: a secret is missing/misspelled, the Gmail app password or FRED
  key was revoked, or a central bank site changed its page markup.

## Running locally instead

If you'd rather run this on your own machine instead of GitHub Actions:

```
pip install -r requirements.txt
export FRED_API_KEY="your_fred_key"
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export INTEREST_RATE_RECIPIENT="you@gmail.com"
python interest_rate_emailer.py generate
python interest_rate_emailer.py send
```

Schedule it yourself with cron (`crontab -e`):

```
0 8 * * * cd /path/to/interest-rate-emailer && /usr/bin/python3 interest_rate_emailer.py generate && /usr/bin/python3 interest_rate_emailer.py send >> interest_rate_emailer.log 2>&1
```
