# 2026 NCAA Tournament Research Prompt

Use the prompt below to brief a web researcher collecting source data for a 2026 NCAA men's tournament model.

```text
I’m rebuilding an NCAA men’s tournament prediction model for the 2026 tournament and need clean, current input data in a structured format.

Please research and compile the following for the 2025-26 NCAA men’s basketball season, with sources and exact retrieval dates:

1. Team strength inputs
- Current Elo-style ratings for all Division I teams, or the closest high-quality public equivalent
- Current KenPom ratings for all teams, including adjusted efficiency metrics if available
- Latest AP Top 25 poll before Selection Sunday / tournament start
- Preseason AP Top 25 poll for the 2025-26 season
- Any other strong public team rating systems that are widely respected and available in tabular form

2. Tournament field and bracket data
- Official 2026 NCAA men’s tournament bracket
- Full field of 68 teams
- Regions, seeds, First Four matchups, and full game path structure
- Selection Sunday date and bracket release source

3. Historical validation data, if easy to gather
- Final tournament bracket/results for recent seasons
- Historical KenPom/Elo/AP snapshots from just before each tournament
- Anything usable for backtesting model weights

For each source, please provide:
- Source name
- Direct link
- What the data contains
- Whether it is free, paywalled, scraped, or official
- Whether it updates daily, weekly, or only once
- Best export format available: CSV, HTML table, JSON, etc.
- Any team-name formatting quirks I should expect

Output format:
A concise research memo with sections for:
- Recommended primary sources
- Fallback sources
- Data quality / reliability notes
- Suggested canonical team-name standard
- A final "build-ready dataset checklist"

Important constraints:
- Prioritize reliable, current, citation-ready sources
- Prefer sources that can be copied into CSVs or scraped consistently
- Call out any source that is paywalled
- Use exact dates, not relative phrases like "today" or "yesterday"
- Focus on the 2026 NCAA men’s tournament, not women’s
```

# 2025–26 NCAA Men’s Basketball Data Sources for Team Strength and the 2026 Tournament

## Retrieval date and scope

All sources below were retrieved on **March 18, 2026 (America/Los_Angeles)** unless explicitly noted otherwise. The scope is **Division I men’s basketball** with special focus on the **2026 Division I men’s national tournament** (field, seeds, regions, First Four, and bracket structure). citeturn6view0turn8view0

## Recommended primary sources

### Official bracket and field

**Source name:** Official printable bracket PDF (one-page bracket image/PDF)  
**Direct link:** `https://www.ncaa.com/brackets/print/basketball-men/d1/2026?%24web_only=true&_branch_match_id=...` (printable bracket endpoint) citeturn8view0  
**What the data contains:** The complete **68-team bracket**, with **regions**, **seeds**, **First Four** entries, and the full path through **Final Four** and championship; includes the published game-round date ranges and host cities. citeturn8view0  
**Official / free / paywalled / scraped:** **Official** and **free** (NCAA). citeturn8view0  
**Update frequency:** “One-shot” bracket artifact, but the same PDF can reflect early results (the retrieved copy shows completed First Four results for two play-in games). citeturn8view0  
**Best export format:** **PDF** (best treated as: (a) manual copy, (b) PDF text extraction, or (c) image-to-structure parsing). citeturn8view0  
**Team-name quirks:** Includes abbreviations, parenthetical disambiguators, and occasional abbreviated institutional names; also note that **team records may reflect play-in outcomes** (winners’ records can differ from the pre–First Four record printed in the First Four box). citeturn8view0  

**Source name:** Bracket announcement / release context (tournament bracket release article)  
**Direct link:** `https://www.ncaa.com/news/basketball-men/mml-official-bracket/2026-03-17/2026-ncaa-tournament-printable-bracket-schedule-march-madness` citeturn6view0  
**What the data contains:** Confirms **Selection Sunday timing** and broadcast, and points to both the printable and interactive bracket artifacts. The article states the bracket was announced on **Sunday, March 15, 2026 at 6 p.m. ET on CBS**. citeturn6view0  
**Official / free / paywalled / scraped:** **Official** and **free** (NCAA). citeturn6view0  
**Update frequency:** Updates around bracket release and tournament progression. citeturn6view0  
**Best export format:** HTML page (stable enough for scraping links/metadata), but the bracket data itself is best taken from the PDF. citeturn6view0turn8view0  
**Team-name quirks:** Same as the bracket artifact (because the page’s job is largely linking to the artifacts). citeturn6view0  

### High-signal team strength ratings

**Source name:** Ken Pomeroy efficiency ratings table (season ratings page)  
**Direct link:** `https://kenpom.com/index.php` citeturn31view0  
**What the data contains:** A full-season ratings table including (as labeled on-page) **NetRtg** (adjusted efficiency margin), **ORtg**, **DRtg**, **AdjT** (tempo), **Luck**, and multiple SOS-related columns (Strength of Schedule / non-conference SOS columns appear as grouped headings). The page itself states the specific data cutoff (“Data includes … games played on Tuesday, March 17”). citeturn31view0  
**Official / free / paywalled / scraped:** The ratings table is publicly viewable; several deeper stat pages route to subscription. citeturn31view0turn32view1  
**Update frequency:** Effectively **daily in-season / when games are played**, with an explicit “Data includes … games played on [date]” stamp. citeturn31view0  
**Best export format:** **HTML table** (copy/paste or scrape). There is not an official CSV export link on this page in the retrieved view; treat as scrape/copy. citeturn31view0  
**Team-name quirks:** Uses short forms and punctuation (periods, apostrophes), and sometimes abbreviated directional/state markers; for joins you should expect formatting differences versus polls/bracket sources. citeturn31view0  

**Source name:** Ken Pomeroy methodology notes (for column meaning and historical stability)  
**Direct link:** `https://kenpom.com/blog/ratings-methodology-update/` citeturn32view0  
**What the data contains:** Definitions and interpretation of **AdjEM** and related concepts, plus how the system was changed to make rating scales more interpretable and linear. Useful for documenting feature semantics in a model/data dictionary. citeturn32view0  
**Official / free / paywalled / scraped:** Official and free blog post. citeturn32view0  
**Update frequency:** Static explanatory page. citeturn32view0  
**Best export format:** HTML (documentation). citeturn32view0  
**Team-name quirks:** Not applicable (methodology). citeturn32view0  

**Source name:** Elo-style team ratings (Division I)  
**Direct link:** `https://www.warrennolan.com/basketball/2026/elo` citeturn30view0  
**What the data contains:** A full Division I table with **team record**, **ELO value**, **ELO rank**, and **ELO Delta** with a clearly stated baseline date (“ELO Delta is the change … since SUN, MAR 15th”). The table runs through rank **365**, which is a practical sanity check when validating row counts in your ingestion. citeturn30view0  
**Official / free / paywalled / scraped:** Public, best described as **third‑party** (not NCAA-official) but widely used; scrape/copy. citeturn30view0  
**Update frequency:** Not stated as “daily” in one sentence, but the existence of a dated delta baseline strongly implies rolling updates as games complete. citeturn30view0  
**Best export format:** HTML table (scrape/copy). citeturn30view0  
**Team-name quirks:** Names are generally “clean” but can differ from other sources (spacing, punctuation, parentheticals). Expect join work. citeturn30view0  

**Source name:** Bart Torvik team results / ratings bulk file (programmatic)  
**Direct link:** `https://barttorvik.com/2026_team_results.json` citeturn19view0  
**What the data contains:** A large **array-of-arrays** data dump with one row per team and many numeric columns (ratings and team stats). The structure is highly ingestible but requires column definitions (you should version-control your own header map once validated). citeturn19view0turn11view0  
**Official / free / paywalled / scraped:** Third‑party and **free**; explicitly positioned as a way to work “in bulk … without the need to scrape,” and the files “update constantly during the season.” citeturn11view0turn19view0  
**Update frequency:** “Update constantly during the season” (practically: after results/refresh cycles). citeturn11view0  
**Best export format:** **JSON** (best), with CSV also referenced elsewhere but the JSON endpoint is the most automation-friendly in the retrieved environment. citeturn11view0turn19view0  
**Team-name quirks:** Mostly short school names; expect punctuation/abbrev differences versus polls and bracket naming, plus some short forms (e.g., abbreviations, periods). citeturn19view0  

### AP Top 25 polls

You asked for two specific snapshots: (a) the **latest poll before Selection Sunday**, and (b) the **preseason poll** for the 2025–26 season. The most scrape-stable path I found is a third‑party tabular republisher (Warren Nolan) plus a historical archive (College Poll Archive). I treat these as “data convenience layers” that should be periodically cross-checked against the original AP story pages when high-stakes accuracy matters.

**Source name:** Latest AP Top 25 before Selection Sunday (Week 19 window)  
**Direct link:** `https://www.warrennolan.com/basketball/2026/polls/week/19` citeturn49view0  
**What the data contains:** **AP Poll rankings** with points and first-place votes, labeled **Week 19 (Mar 9 – 15)**, i.e., the poll window immediately preceding Selection Sunday on March 15, 2026. citeturn49view0turn6view0  
**Official / free / paywalled / scraped:** Third‑party and free; scrape/copy. citeturn49view0  
**Update frequency:** Weekly (AP poll cadence), with explicit week/date labeling. citeturn49view0  
**Best export format:** HTML table. citeturn49view0  
**Team-name quirks:** Abbreviations and punctuation; also “others receiving votes” appears as additional ranked rows beyond 25, which can trip simplistic parsers that assume exactly 25 rows. citeturn49view0  

**Source name:** Preseason AP Top 25 poll for the 2025–26 season  
**Direct link:** `https://www.collegepollarchive.com/basketball/men/ap/seasons.cfm?appollid=1302` citeturn47view0  
**What the data contains:** A full preseason Top 25 table including **first-place votes** and **points**, plus “others receiving votes.” citeturn47view0  
**Official / free / paywalled / scraped:** Third‑party historical archive; free; scrape/copy. The site explicitly notes it is not affiliated with selection committees or related entities. citeturn46view1  
**Update frequency:** Static once published (preseason poll). citeturn47view0  
**Best export format:** HTML table. citeturn47view0  
**Team-name quirks:** Generally clean but not guaranteed to match the exact typography used in efficiency models or bracket PDFs; treat as a separate “poll namespace.” citeturn47view0  

**Source name:** Final AP poll before games begin (post–Selection Sunday, pre–First Round)  
**Direct link:** `https://www.warrennolan.com/basketball/2026/polls` (Week 20) citeturn48view0  
**What the data contains:** **Week 20 (Mar 16 – Apr 6)** including the AP poll ranks, points, and first-place vote counts. This is “latest before tournament games” in the practical sense that it posts after Selection Sunday but before the Round of 64 begins. citeturn48view0turn6view0  
**Official / free / paywalled / scraped:** Third‑party; free; scrape/copy. citeturn48view0  
**Update frequency:** Weekly. citeturn48view0  
**Best export format:** HTML table. citeturn48view0  
**Team-name quirks:** Same as above; watch duplicates / tie ranks and “others receiving votes.” citeturn48view0  

## Fallback sources

### NET and committee-facing ranking proxies

**Source name:** NET rankings table (scrape-friendly mirror)  
**Direct link:** `https://www.cbssports.com/college-basketball/rankings/net/` citeturn25view0  
**What the data contains:** NCAA NET rank ordering in a large HTML table with an explicit “NET Updated Mar 15, 2026” stamp. Useful when the official NCAA NET page is JS/anti-bot gated. citeturn25view0turn24view0  
**Official / free / paywalled / scraped:** Third‑party republisher; free; scrape/copy. citeturn25view0turn24view0  
**Update frequency:** As NET updates (the page reports an update date). citeturn25view0  
**Best export format:** HTML table. citeturn25view0  
**Team-name quirks:** Uses media-style short names and abbreviations; expect differences from both efficiency models and bracket PDFs. citeturn25view0  

### Additional public power ratings worth backtesting

**Source name:** Predictive power ratings table  
**Direct link:** `https://www.teamrankings.com/ncaa-basketball/ranking/predictive-by-other/` citeturn44view3  
**What the data contains:** A full rankings table with a numeric **Rating** plus record splits (e.g., vs top 1–25 / 26–50 / 51–100), plus an “About Our Power Ratings” section stating the ratings are designed for predictive purposes and incorporate a preseason prior (with diminishing weight over time). citeturn44view3  
**Official / free / paywalled / scraped:** Third‑party; free to view; scrape/copy. citeturn44view3  
**Update frequency:** The page includes “Gainers (Since Yesterday)” and “Losers (Since Yesterday),” indicating day-to-day refresh. citeturn44view3  
**Best export format:** HTML table. citeturn44view3  
**Team-name quirks:** Abbreviations and spacing differ from other ecosystems (you should not assume join-by-name works without an alias table). citeturn44view3  

**Source name:** Haslametrics (predictive analysis + team capsules)  
**Direct link:** `https://haslametrics.com/about.php` and `https://haslametrics.com/ratings.php` citeturn36search8turn36search0  
**What the data contains:** A public analytics system with explanations of intent (predictive analysis / insight). The ratings landing page is date-driven (select-a-date UI) and includes methodological notes (e.g., “garbage time” not factored) and projections described as based on present-day ratings. citeturn36search0turn36search8  
**Official / free / paywalled / scraped:** Third‑party; described as “free of charge.” citeturn36search8  
**Update frequency:** Implied continuous updates through date-driven pages; not clearly stated as a schedule in one line. citeturn36search0  
**Best export format:** Mostly HTML; not surfaced as a clean bulk JSON/CSV in the retrieved pages. citeturn36search0turn36search8  
**Team-name quirks:** Team capsules and table views can vary in formatting; expect more join friction than the bulk JSON sources. citeturn36search0turn36search8  

### Historical tournament results for backtesting

**Source name:** ESPN bracket pages by season (results embedded)  
**Direct link:** `https://www.espn.com/mens-college-basketball/bracket/_/season/2025/2025-ncaa-tournament` (and analogous season URLs) citeturn39search5  
**What the data contains:** Historical bracket structures and results for men’s tournaments across many seasons. Useful when official NCAA year pages are JS/verification gated. citeturn39search5turn37search4turn38view3  
**Official / free / paywalled / scraped:** Third‑party; typically free-to-view; scrape viability depends on ESPN’s page structure. citeturn39search5turn37search4  
**Update frequency:** Static for past seasons once tournament is complete. citeturn37search4  
**Best export format:** HTML. citeturn37search4  
**Team-name quirks:** Media abbreviations; sometimes differs from committee/bracket naming. citeturn39search5  

### Scores and schedules for deeper validation

**Source name:** Massey schedule/score data formats (for building your own rollups)  
**Direct link:** `https://masseyratings.com/data` and format page `https://masseyratings.com/scorehelp.htm` citeturn41view0turn42view0  
**What the data contains:** A centralized scores/schedules repository with multiple output formats documented (fixed-width lines per game; and several CSV schemas for Matlab-oriented ingestion, including a “Matlab Teams” mapping file concept). citeturn42view0  
**Official / free / paywalled / scraped:** Third‑party. The format page describes data intended for databases/spreadsheets and provided as-is. The site’s terms emphasize restrictions on reproduction/dissemination without consent, so treat this as a “read terms carefully” source. citeturn42view0turn42view1  
**Update frequency:** Not stated explicitly on the format page; the repository is presented as an ongoing collection effort. citeturn41view0turn42view0  
**Best export format:** Fixed-width text and CSV variants as described. citeturn42view0  
**Team-name quirks:** If you use a team-index mapping approach, you can bypass some join-by-name problems—assuming you can reliably obtain the relevant “teams” mapping for your slice. citeturn42view0  

## Data quality and reliability notes

The tournament bracket is the rare piece of this pipeline that wants an “official truth source” rather than a statistical best guess. The printable bracket PDF is the cleanest anchor: it contains the whole field, the region/seed structure, and the official round schedule labels in one artifact. Its main drawback is format friction (PDF rather than CSV/JSON). citeturn8view0turn6view0

Team-strength inputs live in a messier epistemic world. The best practice is to treat each system as a *measurement* with known biases and to store raw snapshots with explicit timestamps. Ken Pomeroy’s page is unusually nice in that it self-documents the data cutoff (“Data includes … [date]”), which lets you reconstruct exactly what you knew when. The main operational caveat is that some deeper KenPom pages route to subscription. citeturn31view0turn32view1turn32view0

Elo is attractive because it’s conceptually compact and time-evolvable, but in college basketball it’s mostly third-party implementations. The Warren Nolan table is concrete (full Division I coverage, a numeric rating, and a delta since a named date), which makes it usable as a “daily strength feature.” You still shouldn’t assume it matches any other Elo implementation; treat it as its own system. citeturn30view0

For Torvik, the key operational move is to avoid scraping the interactive pages and instead ingest the bulk JSON/CSV-style endpoints. Even community documentation points out that bulk files exist and “update constantly,” and that mass scraping can trigger blocks. That means: (1) cache daily snapshots yourself, (2) throttle, (3) pin hashes for backtests. citeturn11view0turn19view0

Poll data is deceptively annoying. “Official AP” is real, but “AP in a scrape-ready table you can backtest across years” is usually a republisher. Warren Nolan and College Poll Archive both present poll tables in stable HTML. If you need courtroom-grade provenance, you’d cross-check key weeks against AP’s own poll hub / story pages, but for modeling you’ll usually prefer the stable HTML tables plus periodic spot-audits. citeturn49view0turn48view0turn47view0

The official NET page is, in practice, hostile to simple scraping (JS and bot verification). If your modeling needs NET, the pragmatic approach is to ingest from an accessible mirror that shows an explicit “updated” date, then treat it as a proxy you can sanity-check occasionally. citeturn24view0turn25view0

## Suggested canonical team-name standard

If you want something that survives real-world joins (and survives next season), join-by-display-name alone won’t cut it. The canonical approach I’d actually ship:

Use a **two-layer identity**:

1) **Canonical key (`team_id_canon`)**: a deterministic string you control, derived from the official bracket name for tournament teams (because your immediate target is the 2026 field), plus a disambiguation suffix when the bracket itself disambiguates. Example template (not literal code):  
- normalize Unicode → ASCII  
- uppercase  
- strip periods/apostrophes  
- collapse whitespace  
- preserve parenthetical disambiguators as a suffix (they exist for a reason)  
- then store the *original bracket display name* separately

2) **Alias mapping table (`team_aliases`)**: one row per canonical team, with columns like:
- `name_bracket` (official bracket display string from the PDF) citeturn8view0  
- `name_kenpom` (as displayed on the ratings table) citeturn31view0  
- `name_elo_site` (as displayed in the Elo table) citeturn30view0  
- `name_torvik` (as displayed in the Torvik dump) citeturn19view0  
- `name_net_mirror` (from the NET mirror you select) citeturn25view0  

This keeps your model features stable even when one source changes punctuation (periods in abbreviations), chooses a different short form, or uses parentheticals vs. commas.

A small but important rule: **store the raw source strings unchanged** alongside any normalized version. When a join fails, you want to see the original typo/variant, not just your sanitized key.

## Build-ready dataset checklist

What follows is the smallest set of artifacts I’d want in a repo before I trusted any modeling work.

**Tournament structure artifacts**
- `bracket_2026_raw.pdf` (the official printable bracket PDF as retrieved March 18, 2026). citeturn8view0  
- `tournament_2026_field.csv` with columns: `season`, `region`, `seed`, `team_name_bracket`, `is_first_four`, `first_four_opponent`, `slot` (your own region+seed+game-slot identifier). Built from the bracket artifact. citeturn8view0  
- `tournament_2026_round_dates.json` capturing the official round date ranges and host cities stated on the bracket artifact. citeturn8view0  
- `selection_sunday_metadata.json` with: `selection_sunday_date = 2026-03-15`, `reveal_time_et = 18:00`, `broadcaster = CBS` (as documented). citeturn6view0  

**Team strength snapshots (pre-tournament)**
- `kenpom_ratings_2026-03-18.html` (or parsed to CSV) *plus* a parsed `kenpom_ratings_2026-03-18.csv` with the columns you intend to use (AdjEM/NetRtg, AdjO/ORtg, AdjD/DRtg, tempo, luck, SOS columns). Keep the raw HTML because table schemas occasionally drift. citeturn31view0turn32view0  
- `elo_ratings_2026-03-18.csv` scraped from the Elo table, with the site’s own note about delta baseline date captured in metadata. citeturn30view0  
- `torvik_team_results_2026-03-18.json` archived verbatim, plus a `torvik_team_results_schema.json` that pins your interpreted column mapping. citeturn19view0turn11view0  
- `ap_poll_week19_2026.csv` (Week 19: Mar 9–15) and `ap_poll_week20_2026.csv` (Week 20: Mar 16–Apr 6), each with `rank`, `team_string`, `points`, `fpv`, and `week_date_window`. citeturn49view0turn48view0  
- If you use NET: `net_2026-03-15.csv` from your chosen mirror, with that mirror’s “updated” date stored. citeturn25view0turn24view0  

**Historical backtest artifacts (recent seasons)**
- At minimum: a set of historical tournament results pages you can scrape consistently (ESPN season bracket pages are the most directly discoverable in the retrieved set). Store both raw HTML and parsed results. citeturn39search5turn37search4  
- If you later rely on official NCAA year pages, budget engineering time for JS/anti-bot gating; in the retrieved environment those pages present a verification wall. citeturn38view3turn38view0  

**Name normalization and joins**
- `team_aliases.csv` seeded from the 2026 bracket names, then populated with aliases from each rating/poll source. Expect manual work for collisions and punctuation-driven mismatches. citeturn8view0turn31view0turn30view0turn19view0turn49view0  
- A join QA report (even a simple script output) that flags:
  - teams in bracket missing from each rating source  
  - extra teams in rating source not in Division I (should be zero; use row counts like 365 as sanity checks where available) citeturn30view0  

**Reproducibility**
- For every snapshot file: store `retrieved_at` (timestamp), `source_url`, and `sha256`. The day you decide to backtest “what would my model have predicted on Selection Sunday,” you’ll be glad you did.

## Official 2026 tournament bracket field

All matchups, regions, seeds, and First Four structure below come from the official printable bracket PDF retrieved March 18, 2026. citeturn8view0

### East region

(1) entity["sports_team","Duke","blue devils"] vs (16) entity["sports_team","Siena","saints"]  
(8) entity["sports_team","Ohio State","buckeyes"] vs (9) entity["sports_team","TCU","horned frogs"]  
(5) entity["sports_team","St. John's","red storm"] vs (12) entity["sports_team","Northern Iowa","panthers iowa"]  
(4) entity["sports_team","Kansas","jayhawks"] vs (13) entity["sports_team","Cal Baptist","lancers"]  
(6) entity["sports_team","Louisville","cardinals men's cbb"] vs (11) entity["sports_team","South Florida","bulls tampa"]  
(3) entity["sports_team","Michigan St.","spartans"] vs (14) entity["sports_team","N Dakota St.","bison"]  
(7) entity["sports_team","UCLA","bruins"] vs (10) entity["sports_team","UCF","knights"]  
(2) entity["sports_team","Connecticut","huskies men's cbb"] vs (15) entity["sports_team","Furman","paladins"]  

### West region

(1) entity["sports_team","Arizona","wildcats tucson"] vs (16) entity["sports_team","Long Island","sharks"]  
(8) entity["sports_team","Villanova","wildcats philadelphia"] vs (9) entity["sports_team","Utah St.","aggies utah"]  
(5) entity["sports_team","Wisconsin","badgers"] vs (12) entity["sports_team","High Point","panthers hpu"]  
(4) entity["sports_team","Arkansas","razorbacks"] vs (13) entity["sports_team","Hawaii","rainbow warriors"]  
(6) entity["sports_team","BYU","cougars provo"] vs (11) entity["sports_team","Texas","longhorns"] *(First Four winner over entity["sports_team","NC State","wolfpack"])*  
(3) entity["sports_team","Gonzaga","bulldogs spokane"] vs (14) entity["sports_team","Kennesaw St.","owls"]  
(7) entity["sports_team","Miami (FL)","hurricanes"] vs (10) entity["sports_team","Missouri","tigers columbia"]  
(2) entity["sports_team","Purdue","boilermakers"] vs (15) entity["sports_team","Queens (N.C.)","royals charlotte"]  

### South region

(1) entity["sports_team","Florida","gators"] vs (16) entity["sports_team","PVAMU","panthers prairie view"] / entity["sports_team","Lehigh","mountain hawks"] *(First Four matchup)*  
(8) entity["sports_team","Clemson","tigers clemson"] vs (9) entity["sports_team","Iowa","hawkeyes"]  
(5) entity["sports_team","Vanderbilt","commodores"] vs (12) entity["sports_team","McNeese","cowboys"]  
(4) entity["sports_team","Nebraska","cornhuskers"] vs (13) entity["sports_team","Troy","trojans alabama"]  
(6) entity["sports_team","North Carolina","tar heels"] vs (11) entity["sports_team","VCU","rams richmond"]  
(3) entity["sports_team","Illinois","fighting illini"] vs (14) entity["sports_team","Penn","quakers"]  
(7) entity["sports_team","Saint Mary's","gaels"] vs (10) entity["sports_team","Texas A&M","aggies college station"]  
(2) entity["sports_team","Houston","cougars houston"] vs (15) entity["sports_team","Idaho","vandals"]  

### Midwest region

(1) entity["sports_team","Michigan","wolverines"] vs (16) entity["sports_team","Howard","bison howard"] *(First Four winner over entity["sports_team","UMBC","retrievers"])*  
(8) entity["sports_team","Georgia","bulldogs athens"] vs (9) entity["sports_team","Saint Louis","billikens"]  
(5) entity["sports_team","Texas Tech","red raiders"] vs (12) entity["sports_team","Akron","zips"]  
(4) entity["sports_team","Alabama","crimson tide"] vs (13) entity["sports_team","Hofstra","pride"]  
(6) entity["sports_team","Tennessee","volunteers"] vs (11) entity["sports_team","MIA OH","redhawks"] / entity["sports_team","SMU","mustangs"] *(First Four matchup)*  
(3) entity["sports_team","Virginia","cavaliers"] vs (14) entity["sports_team","Wright St.","raiders dayton"]  
(7) entity["sports_team","Kentucky","wildcats lexington"] vs (10) entity["sports_team","Santa Clara","broncos"]  
(2) entity["sports_team","Iowa St.","cyclones"] vs (15) entity["sports_team","Tennessee St.","tigers nashville"]  

**Final Four host city shown on the official bracket:** entity["city","Indianapolis","indiana, us"]. citeturn8view0
