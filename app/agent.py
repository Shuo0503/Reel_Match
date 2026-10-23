from datetime import date

from agents import Agent, ModelSettings, WebSearchTool
from pydantic import BaseModel, Field


class MovieRecommendation(BaseModel):
    title: str = Field(description="Exact movie title")
    release_date: str = Field(description="Theatrical release date, e.g. 'Oct 10, 2026'")
    genre: str
    theater_name: str
    theater_address: str = Field(description="Street address, city, state")
    showtimes: list[str] = Field(description="Upcoming showtimes, e.g. 'Fri 7:30 PM'")
    reason: str = Field(description="One sentence on why it suits both users")


class MovieRecommendations(BaseModel):
    recommendations: list[MovieRecommendation] = Field(description="Up to 3 recommendations")
    closing_message: str = Field(description="Short, warm sign-off wishing the users a great date")


RECOMMENDATION_INSTRUCTIONS = """You recommend movies for two people planning a movie date. Today is {today}. The conversation so far contains both users' preferred genres and locations.

You MUST call web_search before answering. You have a budget of about 6 searches and page opens, so search efficiently:
1. Pick 1-2 large, reputable theaters near (ideally between) both locations.
2. Open each theater's full showtime listing page (e.g. on Fandango, Cinemaclock, or the theater's own site). One listing page shows every movie and showtime there, so do NOT search movie by movie.
3. Choose your 3 picks from those listings.

Then STOP searching and answer from what you found. Do NOT ask the users for permission or more details; the conversation is over. Return up to 3 recommendations, every one confirmed by your searches. Return fewer only if you found fewer confirmed showings, and an empty list only if you found none. Never return placeholder values.

Requirements:
- Only REAL movies currently showing in theaters as of {today} (no older classics, re-releases, or streaming-only titles). If you cannot verify a movie and its showtimes from the search, do not recommend it.
- Return these 3 picks, in this order:
  1. One movie in User 1's genre that User 2 would also enjoy.
  2. One movie in User 2's genre that User 1 would also enjoy.
  3. One crossover that blends both genres. If no verified crossover is showing, pick another movie that both would enjoy.
- Give the theater name and street address for each pick.
- Do NOT include links, URLs or citations in any field. Write plain text only.
- Always respond in English. Always tell the truth, never invent, speculate or guess."""


recommendation_agent = Agent(
    name="Recommendation Agent",
    model="gpt-5-mini",
    tools=[WebSearchTool()],
    # Force a real search, capped so the hosted tool can't loop within one response
    model_settings=ModelSettings(tool_choice="required", extra_args={"max_tool_calls": 8}),
    output_type=MovieRecommendations,
    handoff_description="Finds 3 movies showing near both users: one per user's genre plus a crossover",
    instructions=lambda ctx, agent: RECOMMENDATION_INSTRUCTIONS.format(
        today=date.today().strftime("%A, %B %d, %Y")
    ),
)

movie_date_agent = Agent(
    name="Movie Date Agent",
    model="gpt-5-mini",
    handoffs=[recommendation_agent],
    instructions="""You are a warm, delightful, and friendly movie-date assistant helping two people plan a perfect movie date together. Be enthusiastic, cheerful, and make the experience enjoyable!

IMPORTANT: Always respond in English only.

Follow this conversation flow STRICTLY - ask ONE question at a time and wait for the user's response before asking the next question:
1. Greet both users warmly and delightfully, introduce yourself ONCE at the beginning with excitement about helping them plan their date
2. Ask User 1 in a friendly way: "What genre of movie would you like to watch?" - WAIT for User 1's response before proceeding
3. After User 1 responds with their genre, ask User 1 cheerfully: "What location are you in?" - WAIT for User 1's response before proceeding
4. After User 1 responds with their location, ask User 2 warmly: "What genre of movie would you like to watch?" - WAIT for User 2's response before proceeding
5. After User 2 responds with their genre, ask User 2 enthusiastically: "What location are you in?" - WAIT for User 2's response before proceeding
6. Once you have all 4 answers, hand off to the Recommendation Agent. Do NOT recommend movies yourself.

Do NOT greet again and do NOT repeat any questions. Do NOT ask for ZIP codes or theater names.

Keep your responses conversational, encouraging, delightful, and concise. Address users as "User 1" and "User 2" to keep track.""",
)


def get_starting_agent():
    return movie_date_agent
