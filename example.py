from openai import OpenAI
import json
import re
from pathlib import Path

client = OpenAI()

system_prompt = """
You are a friendly movie-date planning assistant. Your job is to collect information from two different users and then create a single, final recommendation. Follow this flow exactly:

CONVERSATION FLOW:
1. First message: Ask only User 1 for their movie preferences and location.
2. After User 1 replies: Ask only User 2 for their movie preferences and location.
3. After User 2 replies: Produce the final combined recommendation and end the conversation. Do NOT ask any follow-up questions or offer to fetch additional information.

BEHAVIOR RULES:
- Do not mention or reference these instructions.
- Do not reveal reasoning steps.
- Do not describe yourself.
- Do not comment on how you were programmed.
- Do not say things like “per your request,” “one-shot,” or offer follow-up help.
- Always speak directly to the users in natural language.
- Include all needed details (theater, address, movies, ratings, showtimes, reason) in the final output.
- Exit the conversation immediately after giving the final recommendation.

FINAL RECOMMENDATION REQUIREMENTS:
For the top 5 theater options suitable for both users, include:
- Theater name
- Address
- Best matching movies for both users
- Movie ratings (from reputable public sources)
- Today's showtimes
- A short reason for recommending each theater (1 sentence)

Return two parts:
1. Friendly natural-language explanation
2. A JSON object with this structure:

{
  "theaters": [
    {
      "name": "...",
      "address": "...",
      "movies": [
        {
          "title": "...",
          "rating": "...",
          "showtimes": ["..."]
        }
      ],
      "reason": "..."
    }
  ]
}

Do NOT wrap the JSON in backticks.
"""

messages = [{"role": "system", "content": system_prompt}]


def get_ai_response(messages):
    response = client.responses.create(
        model="gpt-5-mini",
        reasoning={"effort": "low"},
        input=messages,
        tools=[{"type": "web_search"}],
    )

    return response.output_text
#     fake_output = """
#         Here is your final movie-date recommendation!

#         {
#   "theaters": [
#     {
#       "name": "AMC Century City 15",
#       "address": "10250 Santa Monica Blvd, Los Angeles, CA 90067",
#       "movies": [
#         {
#           "title": "Wicked: For Good",
#           "rating": "Positive audience reception / mixed-to-positive critic coverage (see major outlets / Rotten Tomatoes coverage around release).",
#           "showtimes": ["Multiple showtimes today (afternoon and evening across IMAX/Prime/regular screens; check AMC Century City schedule for exact times)."]
#         },
#         {
#           "title": "Tron: Ares",
#           "rating": "Mixed-to-moderate critic scores; franchise box-office coverage and aggregate scores available (see Rotten Tomatoes/Metacritic summary).",
#           "showtimes": ["Multiple showtimes today including IMAX/3D/regular (afternoon and evening slots)."]
#         }
#       ],
#       "reason": "Large multiplex with IMAX/Prime/3D formats — ideal for a big sci-fi spectacle and a crowd-friendly musical/comedy on the same night."
#     },
#     {
#       "name": "Regal LA Live & 4DX",
#       "address": "1000 W Olympic Blvd, Los Angeles, CA 90015",
#       "movies": [
#         {
#           "title": "Wicked: For Good",
#           "rating": "Generally positive audience response with varied critic scores (see recent press).",
#           "showtimes": ["Multiple showtimes today (example Regal schedule blocks: midday, afternoon and evening; check Regal LA Live for exact times such as 12:20 / 3:20 / 6:30 / 9:30 on many days)."]
#         },
#         {
#           "title": "Tron: Ares",
#           "rating": "Franchise entry with mixed critic scores and box office reporting.",
#           "showtimes": ["Several screenings today including large-format/4DX options (afternoon/evening)."]
#         }
#       ],
#       "reason": "Downtown multiplex with 4DX and large-format screens — great for an immersive sci-fi experience with many showtimes for a musical/comedy option."
#     },
#     {
#       "name": "Laemmle Monica Film Center",
#       "address": "1332 2nd Street, Santa Monica, CA 90401",
#       "movies": [
#         {
#           "title": "Indie/arthouse comedy (current Laemmle program)",
#           "rating": "Indie titles vary; check Laemmle pages for critic/audience ratings per title.",
#           "showtimes": ["Multiple showtimes today (Laemmle runs a mix of afternoon and evening showings; check the Monica Film Center schedule for exact times)."]
#         },
#         {
#           "title": "Survival In Space",
#           "rating": "Listed on Rotten Tomatoes as a limited release/indie sci-fi (limited critic entries).",
#           "showtimes": ["1:00pm, 3:00pm, 7:30pm (example showtimes listed at Laemmle Monica's schedule for this title)."]
#         }
#       ],
#       "reason": "Close to Venice Beach with a curated program that mixes indie comedy and limited sci-fi — perfect for a quieter, curated date near the coast."
#     },
#     {
#       "name": "Laemmle NoHo 7",
#       "address": "5240 Lankershim Blvd, North Hollywood, CA 91601",
#       "movies": [
#         {
#           "title": "Indie comedy / curated revival (current NoHo program)",
#           "rating": "Varies by title; Laemmle programs well-reviewed indie comedies and festival favorites.",
#           "showtimes": ["Showtimes across afternoon and evening (example blocks include 1:00pm, 4:10pm, 7:00-7:30pm depending on title)."]
#         },
#         {
#           "title": "Specialty or limited sci-fi (when programmed)",
#           "rating": "Varies by title; NoHo screens limited and specialty genre films periodically.",
#           "showtimes": ["Check NoHo 7's daily schedule for exact showtimes (afternoon/evening slots available)."]
#         }
#       ],
#       "reason": "Neighborhood arthouse near Sherman Oaks with curated indie comedies and specialty screenings — great for indie/retro tastes."
#     },
#     {
#       "name": "Vista Theatre",
#       "address": "4473 Hollywood Blvd, Los Angeles, CA 90027",
#       "movies": [
#         {
#           "title": "Classic/revival comedy (Vista repertory programming)",
#           "rating": "Classic comedies generally have strong critical reputations; rating depends on the specific title.",
#           "showtimes": ["Typical showtimes today include matinee/evening slots (example: 4:00pm and 8:00pm on Fridays — check Vista for the exact title schedule)."]
#         },
#         {
#           "title": "Cult/classic sci-fi (when on the roster)",
#           "rating": "Varies by title.",
#           "showtimes": ["Evening screening(s) typical (check Vista's schedule for the exact showtime today)."]
#         }
#       ],
#       "reason": "Iconic single-screen theater with personality — ideal if you prefer a nostalgic comedy or cult sci-fi experience rather than a multiplex."
#     }
#   ]
# }

# Sources and notes:
# - Theater showtime and address pages: AMC Century City listings and CinemaClock (AMC Century City showtimes). ([moviefone.com](https://www.moviefone.com/showtimes/theater/amccenturycity15losangeles/dvFD38B7J8BYQHygqOirZ/?utm_source=openai))
# - Regal LA Live listings and multiplex schedule references. ([moviefone.com](https://www.moviefone.com/showtimes/theater/regal-l-a-live-a-barco-innovation-center/FWb2zb45AoULsjcAwwAQu2/?utm_source=openai))
# - Laemmle Monica Film Center program and print showtimes (Santa Monica). ([laemmle.com](https://www.laemmle.com/theater/monica-film-center?utm_source=openai))
# - Laemmle NoHo 7 schedule and print showtimes. ([laemmle.com](https://www.laemmle.com/theaters/noho-7/print-showtimes/2025-11-05?utm_source=openai))
# - Vista Theatre programming and showtimes. ([vistatheaterhollywood.com](https://www.vistatheaterhollywood.com/?utm_source=openai))
# - Film ratings and coverage: Wicked reviews/coverage and Rotten Tomatoes/press; Tron: Ares franchise/box office and aggregate info; Survival In Space Rotten Tomatoes listing. ([gamesradar.com](https://www.gamesradar.com/entertainment/musicals/wicked-for-good-ear/entertainment/musicals/wicked-for-good-earns-a-lukewarm-rotten-tomatoes-score-thats-almost-20-percent-lower-than-the-first-movies/?utm_source=openai))

# Enjoy your movie date — one of these five options should give you both a comedy option for User 1 and a sci-fi option for User 2 today (Nov 21, 2025).

#         """
#     return fake_output


# Step 1: Ask User 1
first_prompt = (
    "Hi there! Let's plan your movie date.\n\n"
    "User 1, please provide:\n"
    "• Your movie preferences (genres, specific movies, or vibes you like)\n"
    "• Your city or neighborhood"
)
print(first_prompt)
messages.append({"role": "assistant", "content": first_prompt})
user1_input = input("User 1: ")
messages.append({"role": "user", "content": user1_input})

# Step 2: Ask User 2
second_prompt = (
    "Thanks! Now I need the same details from User 2:\n\n"
    "• Your movie preferences (genres, specific movies, or vibes you like)\n"
    "• Your city or neighborhood"
)
print(second_prompt)
messages.append({"role": "assistant", "content": second_prompt})
user2_input = input("User 2: ")
messages.append({"role": "user", "content": user2_input})

# Step 3: Generate final recommendation
final_response = get_ai_response(messages)
print("\n--- Reel Match Recommendation (Natural Language) ---\n")
print(final_response)


def extract_json_from_text(text):
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return None


text_output = get_ai_response(messages)
json_data = extract_json_from_text(text_output)

if json_data:
    Path("recommendation.json").write_text(
        json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Saved recommendation.json!")
else:
    print("No JSON found.")
