"""Shared AI service; credentials are read only on request."""
import os

SYSTEM_PROMPT = "You are Friday, a helpful and precise personal AI assistant. Respond in the user's language, including Kazakh. Be honest about uncertainty. Never claim to browse, access files or execute actions without tools."


def configured():
    return bool(os.getenv('FRIDAY_API_KEY') or os.getenv('Nurzhik_06') or os.getenv('OPENAI_API_KEY'))


def chat(messages):
    from openai import OpenAI
    key = os.getenv('FRIDAY_API_KEY') or os.getenv('Nurzhik_06') or os.getenv('OPENAI_API_KEY')
    if not key:
        raise RuntimeError('API_KEY_MISSING')
    with OpenAI(api_key=key, timeout=45.0, max_retries=1) as client:
        result = client.chat.completions.create(
            model=os.getenv('FRIDAY_MODEL', 'gpt-4o-mini'),
            messages=[{'role': 'system', 'content': SYSTEM_PROMPT}, *messages],
            max_completion_tokens=2048,
        )
    answer = result.choices[0].message.content
    if not answer:
        raise RuntimeError('EMPTY_RESPONSE')
    return answer


def ask_ai(prompt: str) -> str:
    return chat([{'role': 'user', 'content': prompt}])
