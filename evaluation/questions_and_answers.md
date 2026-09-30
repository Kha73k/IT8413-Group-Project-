# 25 Test Questions and Answers (simple English)

This is the short, easy-to-read version of our test set. It has the 25 questions the brief
asks for, with the right answer for each one.

- The full version, with exact sources and quotes, is in [`test_set.csv`](test_set.csv).
  The number in brackets after each question, like **(Q01)**, is its ID in that file.
- **Dev** questions are for building and improving the tool. **Held-out** questions are
  kept hidden until the final test.
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
| Simple look-up | 5 | 5 |
| Combined (more than one source) | 6 | 6 |
| Surprising answer | 3 | 3 |
| Not in the sources | 5 | 5 |
| Documents only | 6 | 6 |
| **Total** | **25** (13 dev, 12 held-out) | **25** |

---

## A. Simple look-up (5)

The answer is one value in one row of a data file.

**1. How many Bahraini women lived in Muharraq in June 2025?** (Q01, dev)
> 72,477.

**2. How much land in the Northern governorate was used for housing in February 2026?** (Q02, dev)
> 37,314,618 square metres (about 37.3 km²).

**3. What kind of restaurant is Frangipani Restaurant, and where is it?** (Q03, dev)
> It is a Japanese restaurant. It is in block 257, in Muharraq.

**4. How many non-Bahraini men lived in the Capital governorate in December 2024?** (Q04, held-out)
> 292,635.

**5. How much land in the Capital governorate was used for business (commercial) in July 2024?** (Q05, held-out)
> 1,510,413 square metres (about 1.5 km²).

---

## B. Combined (6)

The tool must count or add up many rows, or use data and a document together.

**6. How many fast food restaurants are in Muharraq, and what part of all Muharraq restaurants is that?** (Q07, dev)
> 105 out of 607 restaurants, which is 17.3%.

**7. And what about the Northern governorate?** (Q08, dev, follow-up to question 6)
> Northern has 39 fast food restaurants out of 315 (12.4%). So Northern has fewer than
> Muharraq (105), and a smaller share.
>
> *Ask this right after question 6 in the same chat. It tests if the tool remembers the
> last question.*

**8. How many Arabic restaurants are in the Southern governorate? And what approval does a new restaurant need, and how long does it take?** (Q09, dev)
> There are 45 Arabic restaurants. Sijilat lists one approval: a site approval from
> Municipality Affairs. It takes 3 working days at most.

**9. For each governorate, how many restaurants are there for every 10,000 people? (Use June 2025 population.)** (Q10, dev)

> | Governorate | Restaurants | People | Per 10,000 people |
> |---|---|---|---|
> | Capital | 1,128 | 552,684 | 20.41 |
> | Muharraq | 607 | 297,211 | 20.42 |
> | Northern | 315 | 431,075 | 7.31 |
> | Southern | 345 | 322,290 | 10.70 |
>
> *Capital and Muharraq are almost the same (about 20.4). Saying "about equal" is correct.*

**10. Which governorate grew the most in people from June 2020 to June 2025, and how many restaurants does it have?** (Q11, held-out)
> Northern. It went from 375,648 to 431,075 people (14.8% more). It has 315 restaurants.
> (The others: Muharraq +12.8%, Southern +8.1%, Capital +3.3%.)

**11. A 17-year-old Bahraini wants to open a restaurant as a one-person business in the governorate with the fewest restaurants. Which governorate is that, and can they register?** (Q12, held-out)
> Northern has the fewest restaurants (315). No, they cannot register. The owner of a
> one-person business must be at least 18 (Law No. 27 of 2015, Article 10). Sijilat also
> says restaurant owners must be 18 or older.

---

## C. Surprising answer (3)

Most people would guess wrong. The sources say the opposite.

**12. The Northern governorate has more people than Muharraq. Does it also have more restaurants?** (Q14, dev)
> No. Northern has 431,075 people and Muharraq has 297,211, so Northern has 45% more
> people. But Northern has only 315 restaurants and Muharraq has 607. Northern has the
> fewest restaurants of all four governorates.

**13. If the Ministry does not answer a registration request within 30 days, is it approved automatically?** (Q15, dev)
> No. After 30 days with no decision, the request counts as **rejected**, not approved
> (Implementing Regulation, Article 7).

**14. The Capital has the most pharmacies. Does it also have the most pharmacies for its number of people?** (Q16, held-out)
> No. Muharraq has the most for its number of people.
>
> | Governorate | Pharmacies | Per 10,000 people |
> |---|---|---|
> | Capital | 74 | 1.34 |
> | Muharraq | 54 | 1.82 |
> | Northern | 26 | 0.60 |
> | Southern | 34 | 1.05 |

---

## D. Not in the sources (5)

The right answer is to say "our sources do not have this". The tool must **not** guess.

**15. Would a new coffee shop in block 338 of the Capital make a profit?** (Q19, dev)
> Not in the sources. The sources only show businesses that already exist and the rules
> for opening one. They cannot say if a new business will make money. (The tool may say
> there are already 6 coffee shops in block 338, but it must not predict profit.)

**16. How much is the yearly fee to stay in the Commercial Register?** (Q20, dev)
> Not in the sources. The law says the yearly fee is set by a separate order from the
> Minister, and we do not have that order. The only fees in our documents are the
> municipal fee (10 BD) and a printed certificate (2 BD).
>
> *Wrong answer to watch for: giving the 10 BD municipal fee as the yearly fee.*

**17. How much land in the Southern governorate was in the "Other" group in September 2025?** (Q21, held-out)
> Not in the sources. That month is empty in the file. The months before and after have
> numbers, but filling the gap would be a guess.

**18. How many restaurants in Muharraq closed in 2025?** (Q22, held-out)
> Not in the sources. The restaurant list is a single snapshot. It has no opening or
> closing dates.

**19. What licences do I need to open a café that serves shisha?** (Q23, held-out)
> Not in the sources. None of our four documents mentions shisha.

---

## E. Documents only (6)

The answer is in the law, the regulation, the MOIC guide or the Sijilat page.

**20. What is the punishment for running a business without the licence it needs?** (Q24, dev)
> Up to one year in prison, and/or a fine from 1,000 to 5,000 BD. Another law can give a
> heavier punishment (Law No. 27 of 2015, Article 27).

**21. How many partners can a WLL have, and how much money does it need to start?** (Q26, dev)
> From 2 to 50 partners. There is no minimum starting money, but each share must be worth
> at least 50 BD (MOIC Procedures Guide).

**22. After registering, how long does the owner have to get the needed licences? What happens if they are late?** (Q27, held-out)
> One year from the registration date. If they do not get the licences in that year, the
> Ministry cancels the registration by itself, tells the owner, and puts the decision on
> its website.
>
> *This needs two documents: the law points to the regulation, and the regulation gives
> the one year.*

**23. What is the highest daily fine for a first break of the Commercial Register law, and what is the most it can add up to?** (Q28, held-out)
> Up to 1,000 BD per day for a first break (up to 2,000 BD per day if it happens again
> within three years). The total can never be more than 20,000 BD (Law No. 27 of 2015,
> Article 20).

**24. According to the MOIC guide, who can register a one-person business?** (Q29, held-out)
> A Bahraini or GCC citizen who lives in Bahrain, or a citizen of a country that has a
> free trade agreement with Bahrain. The person must be at least 18.
>
> *The guide's sentence can be read in more than one way, so the group should agree on one
> reading before checking.*

**25. According to Sijilat, which nationalities can own 100% of a restaurant or food business?** (Q30, held-out)
> Bahrainis, GCC citizens, Americans, Singaporeans, and people from Iceland,
> Liechtenstein, Norway and Switzerland. Other foreigners can own part of it, but there
> must also be a Bahraini shareholder.

---

## Spare questions

`test_set.csv` has 5 more questions that are not in this list. We can use them if the tutor
wants more, or to replace a question here:

| ID | Type | Question |
|---|---|---|
| Q06 | Look-up | What kind of business is Roma Motors, and where is it? *(Car showroom, block 502, Northern)* |
| Q13 | Combined | In June 2025, what percentage of people in the Capital were not Bahraini? *(70.9%)* |
| Q17 | Surprising | In June 2025, were there about the same number of men and women in Bahrain? *(No: 61.8% men)* |
| Q18 | Not in sources | How many people live in block 346 in the Capital? |
| Q25 | Documents | If registration details change, how many days does the owner have to report it? *(30 days)* |
