from openai import OpenAI
import os

# OpenAI клиентін жасау
client = OpenAI(api_key=os.getenv("Nurzhik_06"))

def ask_ai(prompt: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are Friday, an intelligent AI assistant like Tony Stark's AI."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
