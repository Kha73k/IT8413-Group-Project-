"""Builds evaluation/test_set.csv: the draft test set for the proposal (PDF section 7.1).

Data answers are computed here from sources/data/*.csv, so every figure is reproducible.
Document answers carry verbatim quotes, and this script fails if a quote is not found in
the named PDF, so a mis-cited article cannot slip through.

DRAFT: questions and answers were drafted with AI assistance (Claude). The PDF prohibits
unverified ground truth, so a group member must check every row against the sources and
fill in verified_by / verified_on before the test set is submitted.

    python evaluation/build_test_set.py
"""
import csv
import logging
import re
from collections import Counter
from pathlib import Path

import pypdf

ROOT = Path(__file__).resolve().parent.parent
DATA, DOCS = ROOT / "sources" / "data", ROOT / "sources" / "documents"
OUT = ROOT / "evaluation" / "test_set.csv"

# Minimums from PDF 7.1; the held-out rules are from the same section.
MINIMUMS = {"document": 6, "combined": 6, "unanswerable": 5, "counter-intuitive": 3, "lookup": 5}
HELD_OUT_MINIMUMS = {"unanswerable": 3, "document": 3}

DOC_FILES = {
    "T1": "cr_law_27_2015.pdf",
    "T2": "cr_regulation_126_2016.pdf",
    "T3": "moic_procedures_guide_2022.pdf",
    "T4": "sijilat_activity_5610-1_food_beverage.pdf",
}


# ---- data --------------------------------------------------------------------------

def rows(name):
    with open(DATA / f"{name}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


REST, SHOPS = rows("restaurants_cafes"), rows("other_shops")
LAND, POP = rows("land_use"), rows("population_by_governorate")


def gov(r):
    # Restaurants/shops use CAPITAL, land use/population use Capital.
    return r["governorate"].strip().title()


def area_m2(r):
    # Stored as text with the unit, e.g. "16398662.168012 m2"; one row is just "m2".
    number = r["area"].replace("m2", "").strip()
    return float(number) if number else None


def one(table, **where):
    hits = [r for r in table if all(r[k] == v for k, v in where.items())]
    assert len(hits) == 1, f"expected exactly one row for {where}, got {len(hits)}"
    return hits[0]


def population(period, governorate=None, **where):
    return sum(int(float(r["population"])) for r in POP
               if r["year"] == period
               and (governorate is None or gov(r) == governorate)
               and all(r[k] == v for k, v in where.items()))


def count(table, **where):
    return sum(1 for r in table if all(
        (gov(r) if k == "governorate" else r[k]) == v for k, v in where.items()))


def land(period, governorate, category):
    year, month = period
    return one(LAND, year=year, month=month, governorate=governorate,
               land_use_category=category)


GOVS = ["Capital", "Muharraq", "Northern", "Southern"]
LATEST_POP = "2025-06"
pop25 = {g: population(LATEST_POP, g) for g in GOVS}
rest_by_gov = {g: count(REST, governorate=g) for g in GOVS}


def per_10k(n, g):
    return n / pop25[g] * 10_000


def pct(a, b):
    return f"{a / b * 100:.1f}%"


# ---- documents ---------------------------------------------------------------------

def squash(text):
    # PDF extraction splits words ("requir ed"), so compare with all whitespace removed.
    return re.sub(r"\s+", "", text).lower()


logging.getLogger("pypdf").setLevel(logging.ERROR)
DOC_TEXT = {k: squash("".join(p.extract_text() or "" for p in pypdf.PdfReader(DOCS / f).pages))
            for k, f in DOC_FILES.items()}


# ---- questions ---------------------------------------------------------------------
# quotes: list of (doc id, verbatim text) that must appear in that document.

Q = []


def q(id, split, type, question, answer, source, quotes=(), follow_up_of="", notes=""):
    Q.append(dict(id=id, split=split, type=type, question=question, follow_up_of=follow_up_of,
                  ground_truth=answer, source_location=source, quotes=list(quotes), notes=notes))


# Every question is one a client could ask an adviser at the business support centre.
# Q-numbers match the numbering in the proposal (Section 3).
LATEST_LAND = ("2026", "02 February")


def m2(r):
    return f"{area_m2(r):,.0f} m² (about {area_m2(r) / 1e6:.2f} km²)"


def top_block(governorate, subtype):
    blocks = Counter(r["block"] for r in REST if gov(r) == governorate and r["subtype"] == subtype)
    block, n = blocks.most_common(1)[0]
    return int(float(block)), n


# Direct lookups: the answer is one cell in one row.
r = land(LATEST_LAND, "Capital", "Commercial")
q("Q01", "dev", "lookup",
  "I want to open a business in the Capital governorate. How much land there was used for business "
  "(Commercial) in February 2026?",
  m2(r),
  "land_use.csv, the row with year=2026, month=02 February, governorate=Capital, land_use_category=Commercial",
  notes="The file stores the area as text with the unit ('... m2'). Accept m² or km² if the conversion is right.")

r = land(LATEST_LAND, "Muharraq", "Residential")
q("Q02", "dev", "lookup",
  "I want to open a family café near people's homes in Muharraq. How much land in Muharraq was used for "
  "housing (Residential) in February 2026?",
  m2(r),
  "land_use.csv, the row with year=2026, month=02 February, governorate=Muharraq, land_use_category=Residential")

r = one(REST, name="FRANGIPANI RESTAURANT")
q("Q03", "dev", "lookup",
  "I want to open a Japanese restaurant and visit a competitor first. What type of restaurant is Frangipani "
  "Restaurant, and which block and governorate is it in?",
  f"{r['subtype'].title()}, block {int(float(r['block']))}, {gov(r)} governorate",
  "restaurants_cafes.csv, the row with name=FRANGIPANI RESTAURANT")

r = one(POP, year=LATEST_POP, governorate="Southern", nationality="Non-Bahraini", sex="Male")
q("Q04", "held-out", "lookup",
  "My restaurant will serve non-Bahraini workers in the Southern governorate. How many non-Bahraini men "
  "lived there in June 2025?",
  f"{int(float(r['population'])):,}",
  "population_by_governorate.csv, the row with year=2025-06, governorate=Southern, nationality=Non-Bahraini, sex=Male")

r = one(SHOPS, name="ROMA MOTORS")
q("Q05", "held-out", "lookup",
  "I want to open a car showroom. Which block and governorate is the car showroom Roma Motors in?",
  f"Block {int(float(r['block']))}, {gov(r)} governorate",
  "other_shops.csv, the row with name=ROMA MOTORS")

# Combined: the answer needs several rows, or data and a document together.
cs_m, (blk_m, n_m) = count(REST, governorate="Muharraq", subtype="COFFEE SHOPS"), top_block("Muharraq", "COFFEE SHOPS")
q("Q06", "dev", "combined",
  "I want to open a coffee shop in Muharraq. How many coffee shops are already there, and which block has the most?",
  f"{cs_m} coffee shops. Block {blk_m} has the most ({n_m}).",
  "restaurants_cafes.csv: count the rows with governorate=MUHARRAQ and subtype=COFFEE SHOPS, then count them by block")

cs_c, (blk_c, n_c) = count(REST, governorate="Capital", subtype="COFFEE SHOPS"), top_block("Capital", "COFFEE SHOPS")
q("Q07", "dev", "combined",
  "And in the Capital governorate?",
  f"{cs_c} coffee shops. Block {blk_c} has the most ({n_c}). "
  f"(Muharraq has {cs_m}, with the most in block {blk_m}.)",
  "restaurants_cafes.csv: the same counts for CAPITAL",
  follow_up_of="Q06",
  notes="Follow-up question (feature F8). It only makes sense after Q06, so ask Q06 first in the same chat.")

sth, total_rest, total_pop = per_10k(rest_by_gov["Southern"], "Southern"), len(REST), sum(pop25.values())
bh = total_rest / total_pop * 10_000
q("Q08", "dev", "combined",
  "I want to open a restaurant in the Southern governorate. How many restaurants are there for every 10,000 "
  "people, and is that more or less than in Bahrain as a whole? Use the June 2025 population.",
  f"Southern has {sth:.2f} restaurants for every 10,000 people ({rest_by_gov['Southern']} restaurants, "
  f"{pop25['Southern']:,} people). That is less than Bahrain as a whole: {bh:.2f} "
  f"({total_rest:,} restaurants, {total_pop:,} people).",
  "restaurants_cafes.csv: count all rows, and the rows with governorate=SOUTHERN; population_by_governorate.csv: "
  "for year=2025-06, add up all rows, and the rows for Southern")

com = {g: area_m2(land(LATEST_LAND, g, "Commercial")) for g in GOVS}
per_rest = {g: com[g] / rest_by_gov[g] for g in GOVS}
least = min(per_rest, key=per_rest.get)
q("Q09", "dev", "combined",
  "Which governorate has the least business (Commercial) land for each restaurant, so it is the most crowded? "
  "Use the land figures for February 2026.",
  f"{least}: about {per_rest[least]:,.0f} m² of business land for each restaurant ({com[least]:,.0f} m², "
  f"{rest_by_gov[least]} restaurants). Others: "
  + ", ".join(f"{g} {per_rest[g]:,.0f} m²" for g in sorted(GOVS, key=per_rest.get) if g != least) + ".",
  "land_use.csv: rows with year=2026, month=02 February, land_use_category=Commercial; "
  "restaurants_cafes.csv: count the rows in each governorate")

p20 = {g: population("2020-06", g) for g in GOVS}
growth = {g: pop25[g] / p20[g] - 1 for g in GOVS}
fastest = max(growth, key=growth.get)
ff = count(REST, governorate=fastest, subtype="FAST FOOD RESTAURANTS")
q("Q10", "held-out", "combined",
  "I want to open a fast food restaurant in the governorate whose population grew the most between June 2020 "
  "and June 2025. Which governorate is that, how many fast food restaurants are already there, and what "
  "approval do I need before opening?",
  f"{fastest}: from {p20[fastest]:,} to {pop25[fastest]:,} people (+{growth[fastest] * 100:.1f}%). It has {ff} "
  "fast food restaurants. Sijilat lists one approval: a site approval from Municipality Affairs, which takes "
  "3 working days at most.",
  "population_by_governorate.csv: the totals for year=2020-06 and year=2025-06 in each governorate; "
  "restaurants_cafes.csv: count the rows with that governorate and subtype=FAST FOOD RESTAURANTS; "
  "Sijilat page 5610-1, page 2, 'Required Step of Licenses and Approvals'",
  quotes=[("T4", "Site Approval for Food and Beverage service activities"),
          ("T4", "3 working days max")])

busiest = max(rest_by_gov, key=rest_by_gov.get)
q("Q11", "held-out", "combined",
  "A 17-year-old Bahraini wants to open a restaurant as a one-person business (sole proprietorship) in the "
  "governorate with the most restaurants. Which governorate is that, and is the person allowed to register?",
  f"{busiest} ({rest_by_gov[busiest]:,} restaurants). No, they are not allowed. The owner of a one-person business "
  "must be at least 18 (Law No. 27 of 2015, Article 10), and Sijilat also says restaurant owners must be 18 or older.",
  "restaurants_cafes.csv: count the rows in each governorate; Law 27/2015 Article 10, page 4; "
  "Sijilat page 5610-1, page 1, 'Business Requirements'",
  quotes=[("T1", "provided that such nationals have reached the age of 18"),
          ("T4", "Age 18 and above")])

# Counter-intuitive: the true answer is the opposite of what most people would guess.
q("Q12", "dev", "counter-intuitive",
  "The Northern governorate has more people than Muharraq. Does it also have more restaurants?",
  f"No. Northern has {pop25['Northern']:,} people and Muharraq has {pop25['Muharraq']:,} "
  f"({pop25['Northern'] / pop25['Muharraq'] - 1:.0%} more in Northern). But Northern has only "
  f"{rest_by_gov['Northern']} restaurants, while Muharraq has {rest_by_gov['Muharraq']}. "
  "Northern has the fewest restaurants of all four governorates.",
  "population_by_governorate.csv for year=2025-06; restaurants_cafes.csv: count the rows in each governorate")

q("Q13", "dev", "counter-intuitive",
  "I applied to register my business. If the Ministry does not answer within 30 days, is my application "
  "approved automatically?",
  "No. The rules say that if 30 days pass with no decision, the application counts as rejected, not approved.",
  "Implementing Regulation (Order 126 of 2016), Article 7, pages 4-5",
  quotes=[("T2", "The lapse of thirty days without deciding upon the application shall be considered an "
                 "implied rejection thereof")],
  notes="Most people expect 'no answer means yes'. The rules say the opposite.")

ph = {g: count(SHOPS, governorate=g, subtype="PHARMACIES") for g in GOVS}
ph10 = {g: per_10k(ph[g], g) for g in GOVS}
q("Q14", "held-out", "counter-intuitive",
  "I want to open a pharmacy. The Capital governorate has the most pharmacies. Does it also have the most "
  "pharmacies for its number of people?",
  f"No. {max(ph10, key=ph10.get)} has the most for its number of people. Pharmacies for every 10,000 people: "
  + "; ".join(f"{g} {ph10[g]:.2f} ({ph[g]} pharmacies)" for g in GOVS)
  + ". Population is from June 2025.",
  "other_shops.csv: count the rows with subtype=PHARMACIES in each governorate; population_by_governorate.csv for year=2025-06")

# Unanswerable: the tool must say the sources do not have the answer.
q("Q15", "dev", "unanswerable",
  "Would a new coffee shop in block 338 of the Capital governorate make a profit?",
  "NOT IN THE SOURCES. The sources show businesses that already exist and the rules for opening new ones. "
  "They cannot tell if a new business will succeed. (The tool may say that "
  f"{count(REST, block='338.0', subtype='COFFEE SHOPS')} coffee shops are already listed in block 338, "
  "but it must not predict profit.)",
  "restaurants_cafes.csv, rows with block=338.0 (only businesses that already exist)",
  notes="The project brief itself gives 'will my business succeed?' as a question the sources cannot answer.")

q("Q16", "dev", "unanswerable",
  "How much is the yearly fee for being registered in the Commercial Register?",
  "NOT IN THE SOURCES. The law says the yearly fees are set by a separate order from the Minister, and that "
  "order is not in our documents. The only fees our documents give are the municipal fee (10 dinars) and a "
  "printed copy of the certificate (2 dinars).",
  "Law 27/2015 Article 28(a), page 10; Procedures Guide page 8 (page 9 of the PDF)",
  quotes=[("T1", "Annual fees shall be imposed on the registration in the Commercial Register. Such fees shall be "
                 "determined by an order from the Minister"),
          ("T3", "Collection of the municipal fees (ten dinars)"),
          ("T3", "a hard copy of the certificate can be obtained for two dinars")],
  notes="Tests whether the model makes up a fee from memory. "
        "Giving the 10 dinar municipal fee as the yearly registration fee is wrong.")

q("Q17", "held-out", "unanswerable",
  "I want to know how many customers live near my shop. How many people live in block 346 in the Capital governorate?",
  "NOT IN THE SOURCES. Population is only given for whole governorates, not for blocks. "
  f"(Block 346 has the most restaurants in the list ({count(REST, block='346.0')}), which might trick the tool "
  "into answering.)",
  "population_by_governorate.csv has no block column; restaurants_cafes.csv has blocks but no population")

q("Q18", "held-out", "unanswerable",
  "I want to know how risky it is. How many restaurants in Muharraq closed in 2025?",
  "NOT IN THE SOURCES. The restaurant list is one snapshot. It has no opening or closing dates.",
  "restaurants_cafes.csv has no date or status column")

q("Q19", "held-out", "unanswerable",
  "What licences do I need to open a café that serves shisha?",
  "NOT IN THE SOURCES. None of our documents talks about shisha. The Sijilat page is about food and drink "
  "businesses in general and does not mention shisha.",
  "All four documents (shisha is not mentioned)")

# Document-only: the answer is in the documents.
q("Q20", "dev", "document",
  "What is the punishment if I run my business without the licence it needs?",
  "Up to one year in prison and a fine of 1,000 to 5,000 Bahraini dinars, or one of the two. "
  "Another law can give a heavier punishment.",
  "Law 27/2015 Article 27, point 3, page 9",
  quotes=[("T1", "imprisonment for a term not exceeding one year and to a fine not less than One Thousand Bahraini "
                 "Dinars and not exceeding Five Thousand Bahraini Dinars, or to either penalty"),
          ("T1", "Practicing a Commercial Activity without obtaining a license from the Competent Bodies")])

q("Q21", "dev", "document",
  "I want to open a limited liability company (WLL) with partners. How many partners can it have, and how much "
  "money does it need to start?",
  "From 2 to 50 partners. There is no minimum capital (starting money), but each share must be worth at least 50 dinars.",
  "Procedures Guide, section 'Limited Liability Companies', page 10 (page 11 of the PDF)",
  quotes=[("T3", "The number of partners may not be less than two and may not exceed 50"),
          ("T3", "There is no minimum capital"),
          ("T3", "The nominal value for each share may not be less than 50 BD")])

q("Q22", "held-out", "document",
  "After I register my business, how long do I have to get the licences I need? And what happens if I do not "
  "get them in time?",
  "One year from the registration date. If the licences are not received within that year, the Ministry cancels "
  "the registration by itself, tells the owner, and publishes the decision on its website.",
  "Law 27/2015 Articles 8-9, pages 3-4; Implementing Regulation Article 10 (page 5) and Article 16 (pages 7-8)",
  quotes=[("T1", "within the time period specified in the Implementing Regulation"),
          ("T2", "within one year from the Registration date, the approvals and licenses required"),
          ("T2", "it shall omit the Registration of its own accord")],
  notes="Needs two documents: the law says 'the period in the Regulation', and the Regulation gives the one year. "
        "'Omit the registration' is the documents' word for cancelling it.")

q("Q23", "held-out", "document",
  "If I break the Commercial Register law for the first time, what is the highest daily fine, and what is the "
  "most the fine can add up to?",
  "Up to 1,000 dinars per day for a first break (up to 2,000 per day if it happens again within three years). "
  "The total can never be more than 20,000 dinars.",
  "Law 27/2015 Article 20(a), point 2, page 7",
  quotes=[("T1", "shall not exceed One Thousand Bahraini Dinars per day when the breach is committed for the first time"),
          ("T1", "Two Thousand Bahraini Dinars per day"),
          ("T1", "the sum of the fine may not exceed Twenty Thousand Bahraini Dinars")])

q("Q24", "held-out", "document",
  "According to the MOIC Procedures Guide, who can register a one-person business (sole proprietorship)?",
  "A Bahraini or GCC citizen who lives in Bahrain, or a citizen of a country that has a free trade agreement "
  "with Bahrain. The person must be at least 18.",
  "Procedures Guide, section 'Sole Proprietorship', page 12 (page 13 of the PDF)",
  quotes=[("T3", "one must be a Bahraini or GCC citizen, be resident in the Kingdom of Bahrain or a citizen of one "
                 "of the states associated with free trade agreements with the Kingdom of Bahrain, and the "
                 "applicant may not be less than 18 years of age")],
  notes="The law (Article 10) says Bahrainis only, 'without prejudice to ... agreements'. An answer that only "
        "uses Article 10 is partly correct. The guide's sentence can be read more than one way, "
        "so the checker should agree on one reading.")

q("Q25", "held-out", "document",
  "According to Sijilat, which nationalities can own 100% of a restaurant or café?",
  "Bahrainis, GCC citizens, Americans, Singaporeans, and people from Iceland, Liechtenstein, Norway and Switzerland "
  "can own 100%. Other foreigners can own part, but the business must also have a Bahraini shareholder.",
  "Sijilat page 5610-1, page 1, 'Allowed for Nationalities'",
  quotes=[("T4", "Bahraini Ownership 100%"), ("T4", "GCC Nationals Ownership 100%"),
          ("T4", "American Nationals ownership 100%"),
          ("T4", "Icelander, Liechtensteiner, Norwegian, Swiss Nationals ownership 100%"),
          ("T4", "Singaporean Nationals ownership 100%"),
          ("T4", "Foreign ownership allowed, but must include a Bahraini shareholder")])


# ---- checks ------------------------------------------------------------------------

def check():
    problems = []
    for x in Q:
        for doc, text in x["quotes"]:
            if squash(text) not in DOC_TEXT[doc]:
                problems.append(f"{x['id']}: quote not found in {doc}: {text[:60]}...")
        if x["follow_up_of"] and x["follow_up_of"] not in {y["id"] for y in Q}:
            problems.append(f"{x['id']}: follows unknown question {x['follow_up_of']}")
    types = Counter(x["type"] for x in Q)
    held = Counter(x["type"] for x in Q if x["split"] == "held-out")
    problems += [f"only {types[t]} '{t}' questions, need {n}" for t, n in MINIMUMS.items() if types[t] < n]
    problems += [f"held-out has {held[t]} '{t}', need {n}" for t, n in HELD_OUT_MINIMUMS.items() if held[t] < n]
    if len(Q) < 25:
        problems.append(f"only {len(Q)} questions, need 25")
    assert len({x["id"] for x in Q}) == len(Q), "duplicate ids"
    return types, held, problems


if __name__ == "__main__":
    types, held, problems = check()
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:  # BOM so Excel reads UTF-8
        w = csv.writer(f)
        w.writerow(["id", "split", "type", "question", "follow_up_of", "ground_truth", "source_location",
                    "verbatim_quotes", "notes", "verified_by", "verified_on", "verifier_comment"])
        for x in Q:
            w.writerow([x["id"], x["split"], x["type"], x["question"], x["follow_up_of"], x["ground_truth"],
                        x["source_location"], " | ".join(f"[{d}] {t}" for d, t in x["quotes"]), x["notes"],
                        "", "", ""])
    print(f"wrote {OUT.relative_to(ROOT)}: {len(Q)} questions "
          f"({sum(x['split'] == 'dev' for x in Q)} dev / {sum(x['split'] == 'held-out' for x in Q)} held-out)")
    for t, n in MINIMUMS.items():
        print(f"  {t:18} {types[t]:>2} (min {n})   held-out {held[t]}")
    print("quotes checked:", sum(len(x["quotes"]) for x in Q))
    if problems:
        raise SystemExit("FAILED:\n  " + "\n  ".join(problems))
    print("all checks passed")
