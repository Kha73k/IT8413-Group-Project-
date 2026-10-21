# 25 Test Questions and Answers (simple English)

This is the short, easy-to-read version of our test set. It has the 25 questions the brief
asks for, with the right answer for each one. The numbers match Section 3 of the proposal.

- The full version, with exact sources and quotes, is in [`test_set.csv`](test_set.csv).
- **Dev** questions are for building and improving the tool. **Held-out** questions are
  kept hidden until the final test.
- Every question is one that a client could really ask an adviser at the business
  support centre.
- **Still a draft.** These were written with AI help (Claude). A group member must check
  each answer against the sources before we submit.

**Words used below**

- **Governorate**: one of Bahrain's four main areas: Capital, Muharraq, Northern, Southern.
- **Block**: a small numbered area inside a governorate.
- **One-person business** (sole proprietorship): a business owned by one person.
- **WLL** (limited liability company): a company owned by partners.
- **BD**: Bahraini dinars.

| Type | How many | Brief minimum |
|---|---|---|
| Direct lookup | 5 | 5 |
| Combined (more than one source) | 6 | 6 |
| Counter-intuitive (surprising answer) | 3 | 3 |
| Unanswerable (not in the sources) | 5 | 5 |
| Document only | 6 | 6 |
| **Total** | **25** (13 dev, 12 held-out) | **25** |

**What the questions cover**

| Client question | Test questions | Sources used |
|---|---|---|
| 1. Where do similar businesses already operate? | 3, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15 | 1, 2 |
| 2. What is each area like? | 1, 2, 4, 8, 9, 10, 12, 14, 17 | 3, 4 |
| 3. Which registration and licensing rules apply? | 10, 11, 13, 16, 19, 20–25 | 5, 6, 7, 8 |

Sources: 1 restaurants & cafés, 2 other shops, 3 land use, 4 population, 5 the law
(Decree 27/2015), 6 the regulation (Order 126/2016), 7 the MOIC Procedures Guide,
8 the Sijilat restaurant page.

---

## A. Direct lookup (5)

The answer is one value in one row of a data file.

**1. I want to open a business in the Capital governorate. How much land there was used for business (Commercial) in February 2026?** (dev)
> 1,630,338 square metres (about 1.63 km²).

**2. I want to open a family café near people's homes in Muharraq. How much land in Muharraq was used for housing (Residential) in February 2026?** (dev)
> 9,831,045 square metres (about 9.83 km²).

**3. I want to open a Japanese restaurant and visit a competitor first. What type of restaurant is Frangipani Restaurant, and which block and governorate is it in?** (dev)
> It is a Japanese restaurant, in block 257, Muharraq.

**4. My restaurant will serve non-Bahraini workers in the Southern governorate. How many non-Bahraini men lived there in June 2025?** (held-out)
> 143,198.

**5. I want to open a car showroom. Which block and governorate is the car showroom Roma Motors in?** (held-out)
> Block 502, Northern.

---

## B. Combined (6)

The tool must count or add up many rows, or use data and a document together.

**6. I want to open a coffee shop in Muharraq. How many coffee shops are already there, and which block has the most?** (dev)
> 145 coffee shops. Block 264 has the most (22).

**7. And in the Capital governorate?** (dev, follow-up to question 6)
> 224 coffee shops. Block 346 has the most (50).
>
> *Ask this right after question 6 in the same chat. It tests if the tool remembers the
> last question.*

**8. I want to open a restaurant in the Southern governorate. How many restaurants are there for every 10,000 people, and is that more or less than in Bahrain as a whole? (Use June 2025 population.)** (dev)
> Southern has 10.70 (345 restaurants, 322,290 people). That is **less** than Bahrain as a
> whole: 14.94 (2,395 restaurants, 1,603,260 people).

**9. Which governorate has the least business (Commercial) land for each restaurant, so it is the most crowded? (Use February 2026 land figures.)** (dev)
> Muharraq: about 650 m² for each restaurant (394,303 m², 607 restaurants).
> Others: Capital 1,445 m², Southern 2,218 m², Northern 2,821 m².

**10. I want to open a fast food restaurant in the governorate whose population grew the most between June 2020 and June 2025. Which governorate is that, how many fast food restaurants are already there, and what approval do I need before opening?** (held-out)
> Northern: from 375,648 to 431,075 people (+14.8%). It has 39 fast food restaurants.
> Sijilat lists one approval: a site approval from Municipality Affairs, which takes
> 3 working days at most.

**11. A 17-year-old Bahraini wants to open a restaurant as a one-person business in the governorate with the most restaurants. Which governorate is that, and can they register?** (held-out)
> The Capital (1,128 restaurants). No, they cannot register. The owner must be at least 18
> (Law No. 27 of 2015, Article 10, and the Sijilat page).

---

## C. Counter-intuitive (3)

Most people would guess wrong. The sources say the opposite.

**12. The Northern governorate has more people than Muharraq. Does it also have more restaurants?** (dev)
> No. Northern has 431,075 people and Muharraq has 297,211, so Northern has 45% more
> people. But Northern has only 315 restaurants and Muharraq has 607. Northern has the
> fewest restaurants of all four governorates.

**13. I applied to register my business. If the Ministry does not answer within 30 days, is my application approved automatically?** (dev)
> No. After 30 days with no decision, the application counts as **rejected**, not approved
> (Implementing Regulation, Article 7).

**14. I want to open a pharmacy. The Capital has the most pharmacies. Does it also have the most pharmacies for its number of people?** (held-out)
> No. Muharraq has the most for its number of people.
>
> | Governorate | Pharmacies | Per 10,000 people |
> |---|---|---|
> | Capital | 74 | 1.34 |
> | Muharraq | 54 | 1.82 |
> | Northern | 26 | 0.60 |
> | Southern | 34 | 1.05 |

---

## D. Unanswerable (5)

The right answer is to say "our sources do not have this". The tool must **not** guess.

**15. Would a new coffee shop in block 338 of the Capital make a profit?** (dev)
> Not in the sources. The sources only show businesses that already exist and the rules
> for opening one. They cannot say if a new business will make money. (The tool may say
> there are already 6 coffee shops in block 338, but it must not predict profit.)

**16. How much is the yearly fee to stay in the Commercial Register?** (dev)
> Not in the sources. The law says the yearly fee is set by a separate order from the
> Minister, and we do not have that order. The only fees in our documents are the
> municipal fee (10 BD) and a printed certificate (2 BD).
>
> *Wrong answer to watch for: giving the 10 BD municipal fee as the yearly fee.*

**17. I want to know how many customers live near my shop. How many people live in block 346 in the Capital?** (held-out)
> Not in the sources. Population is only given for whole governorates, not for blocks.
> (Block 346 has the most restaurants in the list, which may trick the tool into answering.)

**18. I want to know how risky it is. How many restaurants in Muharraq closed in 2025?** (held-out)
> Not in the sources. The restaurant list is a single snapshot. It has no opening or
> closing dates.

**19. What licences do I need to open a café that serves shisha?** (held-out)
> Not in the sources. None of our four documents mentions shisha.

---

## E. Document only (6)

The answer is in the law, the regulation, the MOIC guide or the Sijilat page.

**20. What is the punishment if I run my business without the licence it needs?** (dev)
> Up to one year in prison, and/or a fine from 1,000 to 5,000 BD. Another law can give a
> heavier punishment (Law No. 27 of 2015, Article 27).

**21. I want to open a WLL with partners. How many partners can it have, and how much money does it need to start?** (dev)
> From 2 to 50 partners. There is no minimum starting money, but each share must be worth
> at least 50 BD (MOIC Procedures Guide).

**22. After I register my business, how long do I have to get the licences I need? What happens if I do not get them in time?** (held-out)
> One year from the registration date. If they do not get the licences in that year, the
> Ministry cancels the registration by itself, tells the owner, and puts the decision on
> its website.
>
> *This needs two documents: the law points to the regulation, and the regulation gives
> the one year.*

**23. If I break the Commercial Register law for the first time, what is the highest daily fine, and what is the most it can add up to?** (held-out)
> Up to 1,000 BD per day for a first break (up to 2,000 BD per day if it happens again
> within three years). The total can never be more than 20,000 BD (Law No. 27 of 2015,
> Article 20).

**24. According to the MOIC guide, who can register a one-person business?** (held-out)
> A Bahraini or GCC citizen who lives in Bahrain, or a citizen of a country that has a
> free trade agreement with Bahrain. The person must be at least 18.
>
> *The guide's sentence can be read in more than one way, so the group should agree on one
> reading before checking.*

**25. According to Sijilat, which nationalities can own 100% of a restaurant or café?** (held-out)
> Bahrainis, GCC citizens, Americans, Singaporeans, and people from Iceland,
> Liechtenstein, Norway and Switzerland. Other foreigners can own part of it, but there
> must also be a Bahraini shareholder.
