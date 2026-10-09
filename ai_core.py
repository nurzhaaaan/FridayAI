"""Shared AI service: OpenAI or a local Ollama model."""
import json
import os
from urllib.request import Request, build_opener, ProxyHandler

SYSTEM_PROMPT = (
    "You are Friday, a helpful personal voice assistant. Respond in the user's "
    "language, including Kazakh. Prefer concise, natural answers suitable for "
    "speaking aloud unless detail is requested. Be honest about uncertainty. "
    "Never claim to browse, access files or execute actions without tools."
)
OLLAMA_URL = 'http://127.0.0.1:11434'


def provider():
    return os.getenv('FRIDAY_PROVIDER', 'openai').lower()


def model_name():
    return os.getenv('FRIDAY_MODEL') or ('qwen3:4b' if provider() == 'ollama' else 'gpt-4o-mini')


def local_request(path, payload=None, timeout=3):
    # Local requests never use the environment's external network proxy.
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(OLLAMA_URL + path, data=data, headers={'Content-Type': 'application/json'})
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise RuntimeError('OLLAMA_RESPONSE_TOO_LARGE')
    return json.loads(body)


def status():
    result = {'provider': provider(), 'model': model_name(), 'configured': False}
    if provider() == 'ollama':
        try:
            names = {item.get('name') for item in local_request('/api/tags').get('models', [])}
            target = model_name()
            result['configured'] = target in names or (':' not in target and target + ':latest' in names)
            result['detail'] = 'Жергілікті модель дайын.' if result['configured'] else f'Модельді жүктеңіз: ollama pull {target}'
        except Exception:
            result['detail'] = 'Ollama қосылмаған. MacBook-та Ollama-ны іске қосыңыз.'
    elif provider() == 'openai':
        result['configured'] = bool(os.getenv('FRIDAY_API_KEY') or os.getenv('Nurzhik_06') or os.getenv('OPENAI_API_KEY'))
        result['detail'] = 'API кілті орнатылған.' if result['configured'] else 'Серверде FRIDAY_API_KEY немесе Nurzhik_06 кілтін орнатыңыз.'
    else:
        result['detail'] = 'FRIDAY_PROVIDER: openai немесе ollama болуы керек.'
    return result


def configured():
    return status()['configured']


def chat(messages):
    context = [{'role': 'system', 'content': SYSTEM_PROMPT}, *messages]
    if provider() == 'ollama':
        response = local_request('/api/chat', {
            'model': model_name(), 'messages': context, 'stream': False,
            'think': False, 'options': {'num_predict': 1024},
        }, timeout=90)
        answer = response.get('message', {}).get('content')
    elif provider() == 'openai':
        from openai import OpenAI
        key = os.getenv('FRIDAY_API_KEY') or os.getenv('Nurzhik_06') or os.getenv('OPENAI_API_KEY')
        if not key:
            raise RuntimeError('API_KEY_MISSING')
        with OpenAI(api_key=key, timeout=45.0, max_retries=1) as client:
            result = client.chat.completions.create(
                model=model_name(), messages=context, max_completion_tokens=2048,
            )
        answer = result.choices[0].message.content
    else:
        raise RuntimeError('INVALID_PROVIDER')
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError('EMPTY_RESPONSE')
    return answer


def ask_ai(prompt: str) -> str:
    return chat([{'role': 'user', 'content': prompt}])
