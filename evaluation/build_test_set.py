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


# Direct lookups: the answer is one cell in one row.
r = one(POP, year="2025-06", governorate="Muharraq", nationality="Bahraini", sex="Female")
q("Q01", "dev", "lookup",
  "How many Bahraini women lived in Muharraq in June 2025?",
  f"{int(float(r['population'])):,}",
  "population_by_governorate.csv, the row with year=2025-06, governorate=Muharraq, nationality=Bahraini, sex=Female")

r = land(("2026", "02 February"), "Northern", "Residential")
q("Q02", "dev", "lookup",
  "How much land in the Northern governorate was used for housing (Residential) in February 2026?",
  f"{area_m2(r):,.0f} m² (about {area_m2(r) / 1e6:.2f} km²)",
  "land_use.csv, the row with year=2026, month=02 February, governorate=Northern, land_use_category=Residential",
  notes="The file stores the area as text with the unit ('... m2'). Accept m² or km² if the conversion is right.")

r = one(REST, name="FRANGIPANI RESTAURANT")
q("Q03", "dev", "lookup",
  "What kind of restaurant is Frangipani Restaurant, and where is it (governorate and block)?",
  f"{r['subtype'].title()}, block {int(float(r['block']))}, {gov(r)} governorate",
  "restaurants_cafes.csv, the row with name=FRANGIPANI RESTAURANT")

r = one(POP, year="2024-12", governorate="Capital", nationality="Non-Bahraini", sex="Male")
q("Q04", "held-out", "lookup",
  "How many non-Bahraini men lived in the Capital governorate in December 2024?",
  f"{int(float(r['population'])):,}",
  "population_by_governorate.csv, the row with year=2024-12, governorate=Capital, nationality=Non-Bahraini, sex=Male")

r = land(("2024", "07 July"), "Capital", "Commercial")
q("Q05", "held-out", "lookup",
  "How much land in the Capital governorate was used for business (Commercial) in July 2024?",
  f"{area_m2(r):,.0f} m² (about {area_m2(r) / 1e6:.2f} km²)",
  "land_use.csv, the row with year=2024, month=07 July, governorate=Capital, land_use_category=Commercial")

r = one(SHOPS, name="ROMA MOTORS")
q("Q06", "held-out", "lookup",
  "What kind of business is Roma Motors, and where is it (governorate and block)?",
  f"{r['subtype'].title()} ({r['type'].title()}), block {int(float(r['block']))}, {gov(r)} governorate",
  "other_shops.csv, the row with name=ROMA MOTORS")

# Combined: the answer needs several rows, or data and a document together.
ff_m, all_m = count(REST, governorate="Muharraq", subtype="FAST FOOD RESTAURANTS"), rest_by_gov["Muharraq"]
q("Q07", "dev", "combined",
  "How many fast food restaurants are in Muharraq, and what percentage of all Muharraq restaurants are they?",
  f"{ff_m} out of {all_m} restaurants ({pct(ff_m, all_m)})",
  "restaurants_cafes.csv: count the rows with governorate=MUHARRAQ and subtype=FAST FOOD RESTAURANTS, "
  "and all rows with governorate=MUHARRAQ")

ff_n, all_n = count(REST, governorate="Northern", subtype="FAST FOOD RESTAURANTS"), rest_by_gov["Northern"]
q("Q08", "dev", "combined",
  "And what about the Northern governorate?",
  f"Northern has {ff_n} fast food restaurants out of {all_n} ({pct(ff_n, all_n)}). "
  f"Muharraq has {ff_m} out of {all_m} ({pct(ff_m, all_m)}). So Northern has fewer, and a smaller percentage.",
  "restaurants_cafes.csv: the same counts for NORTHERN and MUHARRAQ",
  follow_up_of="Q07",
  notes="Follow-up question (feature F8). It only makes sense after Q07, so ask Q07 first in the same chat.")

ar_s = count(REST, governorate="Southern", subtype="ARABIC RESTAURANTS")
q("Q09", "dev", "combined",
  "How many Arabic restaurants are in the Southern governorate? And according to Sijilat, what approval does "
  "a new restaurant need, and how long does it take?",
  f"{ar_s} Arabic restaurants. Sijilat lists one approval: a site approval from Municipality Affairs "
  "('Site Approval for Food and Beverage service activities'), which takes 3 working days at most.",
  "restaurants_cafes.csv: count the rows with governorate=SOUTHERN and subtype=ARABIC RESTAURANTS; "
  "Sijilat page 5610-1, page 2, 'Required Step of Licenses and Approvals'",
  quotes=[("T4", "Site Approval for Food and Beverage service activities"),
          ("T4", "3 working days max")])

q("Q10", "dev", "combined",
  "For each governorate, how many restaurants are there for every 10,000 people? Use the June 2025 population.",
  "; ".join(f"{g} {per_10k(rest_by_gov[g], g):.2f} ({rest_by_gov[g]:,} restaurants, {pop25[g]:,} people)"
            for g in GOVS),
  "restaurants_cafes.csv: count the rows in each governorate; population_by_governorate.csv: for year=2025-06, "
  "add up both nationalities and both sexes in each governorate",
  notes="Capital and Muharraq are only different in the second decimal place. "
        "An answer that says they are about equal (around 20.4) is correct.")

p20 = {g: population("2020-06", g) for g in GOVS}
growth = {g: pop25[g] / p20[g] - 1 for g in GOVS}
fastest = max(growth, key=growth.get)
q("Q11", "held-out", "combined",
  "Which governorate's population grew the most between June 2020 and June 2025, and how many restaurants does it have?",
  f"{fastest}: from {p20[fastest]:,} to {pop25[fastest]:,} people (+{growth[fastest] * 100:.1f}%). "
  f"It has {rest_by_gov[fastest]} restaurants. (The others grew: "
  + ", ".join(f"{g} +{growth[g] * 100:.1f}%" for g in GOVS if g != fastest) + ")",
  "population_by_governorate.csv: the totals for year=2020-06 and year=2025-06 in each governorate; "
  "restaurants_cafes.csv: count the rows in that governorate")

fewest = min(rest_by_gov, key=rest_by_gov.get)
q("Q12", "held-out", "combined",
  "A 17-year-old Bahraini wants to open a restaurant as a one-person business (sole proprietorship) in the "
  "governorate with the fewest restaurants. Which governorate is that, and is the person allowed to register?",
  f"{fewest} ({rest_by_gov[fewest]} restaurants). No, they are not allowed. The owner of a one-person business "
  "must be at least 18 (Law No. 27 of 2015, Article 10), and Sijilat also says restaurant owners must be 18 or older.",
  "restaurants_cafes.csv: count the rows in each governorate; Law 27/2015 Article 10, page 4; "
  "Sijilat page 5610-1, page 1, 'Business Requirements'",
  quotes=[("T1", "provided that such nationals have reached the age of 18"),
          ("T4", "Age 18 and above")])

nb, cap = population(LATEST_POP, "Capital", nationality="Non-Bahraini"), pop25["Capital"]
q("Q13", "held-out", "combined",
  "In June 2025, what percentage of people in the Capital governorate were not Bahraini?",
  f"{pct(nb, cap)} ({nb:,} out of {cap:,})",
  "population_by_governorate.csv: for year=2025-06 and governorate=Capital, add up both sexes for each nationality")

# Counter-intuitive: the true answer is the opposite of what most people would guess.
q("Q14", "dev", "counter-intuitive",
  "The Northern governorate has more people than Muharraq. Does it also have more restaurants?",
  f"No. Northern has {pop25['Northern']:,} people and Muharraq has {pop25['Muharraq']:,} "
  f"({pop25['Northern'] / pop25['Muharraq'] - 1:.0%} more in Northern). But Northern has only "
  f"{rest_by_gov['Northern']} restaurants, while Muharraq has {rest_by_gov['Muharraq']}. "
  "Northern has the fewest restaurants of all four governorates.",
  "population_by_governorate.csv for year=2025-06; restaurants_cafes.csv: count the rows in each governorate")

q("Q15", "dev", "counter-intuitive",
  "If the Ministry does not answer a business registration application within 30 days, "
  "is the application approved automatically?",
  "No. The rules say that if 30 days pass with no decision, the application counts as rejected, not approved.",
  "Implementing Regulation (Order 126 of 2016), Article 7, pages 4-5",
  quotes=[("T2", "The lapse of thirty days without deciding upon the application shall be considered an "
                 "implied rejection thereof")],
  notes="Most people expect 'no answer means yes'. The rules say the opposite.")

ph = {g: count(SHOPS, governorate=g, subtype="PHARMACIES") for g in GOVS}
ph10 = {g: per_10k(ph[g], g) for g in GOVS}
q("Q16", "held-out", "counter-intuitive",
  "The Capital governorate has the most pharmacies. Does it also have the most pharmacies for its number of people?",
  f"No. {max(ph10, key=ph10.get)} has the most for its number of people. Pharmacies for every 10,000 people: "
  + "; ".join(f"{g} {ph10[g]:.2f} ({ph[g]} pharmacies)" for g in GOVS)
  + ". Population is from June 2025.",
  "other_shops.csv: count the rows with subtype=PHARMACIES in each governorate; population_by_governorate.csv for year=2025-06")

male, total = population(LATEST_POP, sex="Male"), population(LATEST_POP)
q("Q17", "held-out", "counter-intuitive",
  "In June 2025, were there about the same number of men and women in Bahrain?",
  f"No. {pct(male, total)} were men ({male:,} out of {total:,}) and {pct(total - male, total)} were women.",
  "population_by_governorate.csv: for year=2025-06, add up all rows for each sex")

# Unanswerable: the tool must say the sources do not have the answer.
q("Q18", "dev", "unanswerable",
  "How many people live in block 346 in the Capital governorate?",
  "NOT IN THE SOURCES. Population is only given for whole governorates, not for blocks. "
  "(Block 346 does appear in the restaurant list, which might trick the tool into answering.)",
  "population_by_governorate.csv has no block column; restaurants_cafes.csv has blocks but no population")

q("Q19", "dev", "unanswerable",
  "Would a new coffee shop in block 338 of the Capital governorate make a profit?",
  "NOT IN THE SOURCES. The sources show businesses that already exist and the rules for opening new ones. "
  "They cannot tell if a new business will succeed. (The tool may say that "
  f"{count(REST, block='338.0', subtype='COFFEE SHOPS')} coffee shops are already listed in block 338, "
  "but it must not predict profit.)",
  "restaurants_cafes.csv, rows with block=338.0 (only businesses that already exist)",
  notes="The project brief itself gives 'will my business succeed?' as a question the sources cannot answer.")

q("Q20", "dev", "unanswerable",
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

southern_other = one(LAND, year="2025", month="09 September", governorate="Southern", land_use_category="Other")
assert area_m2(southern_other) is None, "the missing value this question relies on is no longer missing"
q("Q21", "held-out", "unanswerable",
  "How much land in the Southern governorate was in the 'Other' category in September 2025?",
  "NOT IN THE SOURCES. The area is empty for that month in the file. The months before and after have numbers, "
  "but filling the gap would be a guess.",
  "land_use.csv, the row with year=2025, month=09 September, governorate=Southern, land_use_category=Other "
  "(the area says 'm2' with no number)")

q("Q22", "held-out", "unanswerable",
  "How many restaurants in Muharraq closed in 2025?",
  "NOT IN THE SOURCES. The restaurant list is one snapshot. It has no opening or closing dates.",
  "restaurants_cafes.csv has no date or status column")

q("Q23", "held-out", "unanswerable",
  "What licences do I need to open a café that serves shisha?",
  "NOT IN THE SOURCES. None of our documents talks about shisha. The Sijilat page is about food and drink "
  "businesses in general and does not mention shisha.",
  "All four documents (shisha is not mentioned)")

# Document-only: the answer is in the documents.
q("Q24", "dev", "document",
  "What is the punishment for running a business without the licence it needs?",
  "Up to one year in prison and a fine of 1,000 to 5,000 Bahraini dinars, or one of the two. "
  "Another law can give a heavier punishment.",
  "Law 27/2015 Article 27, point 3, page 9",
  quotes=[("T1", "imprisonment for a term not exceeding one year and to a fine not less than One Thousand Bahraini "
                 "Dinars and not exceeding Five Thousand Bahraini Dinars, or to either penalty"),
          ("T1", "Practicing a Commercial Activity without obtaining a license from the Competent Bodies")])

q("Q25", "dev", "document",
  "If a business's registration details change, how many days does the owner have to report it?",
  "30 days from the day the change happened.",
  "Law 27/2015 Article 11, page 4 (also the Implementing Regulation, Article 3, page 3)",
  quotes=[("T1", "within thirty days from the date when the incident requiring such indication took place"),
          ("T2", "within thirty days from the date when the incidence requiring Indication took place")])

q("Q26", "dev", "document",
  "How many partners can a limited liability company (WLL) have, and how much money does it need to start?",
  "From 2 to 50 partners. There is no minimum capital (starting money), but each share must be worth at least 50 dinars.",
  "Procedures Guide, section 'Limited Liability Companies', page 10 (page 11 of the PDF)",
  quotes=[("T3", "The number of partners may not be less than two and may not exceed 50"),
          ("T3", "There is no minimum capital"),
          ("T3", "The nominal value for each share may not be less than 50 BD")])

q("Q27", "held-out", "document",
  "After registering a business, how long does the owner have to get the licences they need? "
  "And what happens if they do not get them in time?",
  "One year from the registration date. If the licences are not received within that year, the Ministry cancels "
  "the registration by itself, tells the owner, and publishes the decision on its website.",
  "Law 27/2015 Articles 8-9, pages 3-4; Implementing Regulation Article 10 (page 5) and Article 16 (pages 7-8)",
  quotes=[("T1", "within the time period specified in the Implementing Regulation"),
          ("T2", "within one year from the Registration date, the approvals and licenses required"),
          ("T2", "it shall omit the Registration of its own accord")],
  notes="Needs two documents: the law says 'the period in the Regulation', and the Regulation gives the one year. "
        "'Omit the registration' is the documents' word for cancelling it.")

q("Q28", "held-out", "document",
  "What is the highest daily fine for a first break of the Commercial Register law, and what is the most "
  "the fine can add up to?",
  "Up to 1,000 dinars per day for a first break (up to 2,000 per day if it happens again within three years). "
  "The total can never be more than 20,000 dinars.",
  "Law 27/2015 Article 20(a), point 2, page 7",
  quotes=[("T1", "shall not exceed One Thousand Bahraini Dinars per day when the breach is committed for the first time"),
          ("T1", "Two Thousand Bahraini Dinars per day"),
          ("T1", "the sum of the fine may not exceed Twenty Thousand Bahraini Dinars")])

q("Q29", "held-out", "document",
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

q("Q30", "held-out", "document",
  "According to Sijilat, which nationalities can own 100% of a restaurant or food business?",
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
