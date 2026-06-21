# analyzer.py
import os
import json
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dotenv import load_dotenv
from langchain_community.llms import YandexGPT
from config import SENTIMENT_MODEL, SECRET_FILE

# Загрузка секретов
load_dotenv(SECRET_FILE)

# ---------- Тональность (rubert) ----------
tokenizer = None
sentiment_model = None

def load_sentiment_model():
    global tokenizer, sentiment_model
    if tokenizer is None:
        print("Загрузка модели тональности...")
        tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL)
        sentiment_model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL)
        print("Модель тональности загружена.")

def analyze_sentiment(text):
    load_sentiment_model()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True
    )
    with torch.no_grad():
        outputs = sentiment_model(**inputs)
    probs = torch.softmax(outputs.logits, dim=1).squeeze().tolist()
    return {
        "negative": probs[0],
        "neutral": probs[1],
        "positive": probs[2]
    }

# ---------- YandexGPT ----------
def get_yandex_gpt_llm():
    api_key = os.getenv("YC_API_KEY")
    folder_id = os.getenv("YC_FOLDER_ID")
    if not api_key or not folder_id:
        raise ValueError("YC_API_KEY и YC_FOLDER_ID должны быть установлены в файле secret.env")
    return YandexGPT(
        api_key=api_key,
        folder_id=folder_id,
        model_uri=f"gpt://{folder_id}/yandexgpt-lite"
    )

def analyze_with_yandex_gpt(transcript):
    """Анализирует расшифровку разговора через YandexGPT."""
    llm = get_yandex_gpt_llm()

    prompt = f"""
    Ты — аналитик службы поддержки интернет-провайдера.
    Проанализируй следующий диалог между сотрудником и абонентом.
    Если реплики помечены [Оператор]/[Абонент] — это результат автоматического
    разделения голосов и метки могут изредка ошибаться местами, учитывай это.
    Ответь строго в формате JSON с полями:
    1. "problem" — суть проблемы абонента (одно-два предложения).
    2. "category" — категория обращения, ровно одно из значений:
       "нет интернета", "низкая скорость", "обрывы связи", "wi-fi/роутер",
       "оплата/баланс", "подключение/настройка", "телевидение", "другое".
    3. "is_resolved" — true, если проблема решена, иначе false.
    4. "action" — что именно сделал сотрудник для решения (кратко).
    5. "summary" — краткое резюме всего разговора (одно предложение).

    Диалог:
    {transcript}
    """
    try:
        raw_response = llm.invoke(prompt)
        start = raw_response.find('{')
        end = raw_response.rfind('}') + 1
        if start != -1 and end > start:
            json_str = raw_response[start:end]
            return json.loads(json_str)
        else:
            return {"error": "Не найден JSON в ответе", "raw": raw_response}
    except Exception as e:
        msg = str(e)
        if "does not match with service account folder ID" in msg:
            msg = (f"YC_FOLDER_ID в secret.env не совпадает с тем, к которому привязан "
                   f"сервисный аккаунт YC_API_KEY. Проверьте folder_id в консоли Yandex Cloud "
                   f"и поправьте secret.env. Исходная ошибка: {msg}")
        return {"error": msg, "raw": raw_response if 'raw_response' in locals() else None}

def analyze_full(transcript, llm_input_text=None):
    """Главная функция анализа: тональность считается по чистой расшифровке
    (full_text без меток спикеров — так модель тональности видит обычный текст),
    а на вход LLM можно передать другой текст (например, диалог с метками
    [Оператор]/[Абонент] от диаризации) — это помогает точнее определить,
    кто решал проблему. Если llm_input_text не задан, используется transcript."""
    sentiment = analyze_sentiment(transcript)
    llm_result = analyze_with_yandex_gpt(llm_input_text or transcript)
    return {
        "sentiment": sentiment,
        "llm_analysis": llm_result,
        "full_text": transcript
    }