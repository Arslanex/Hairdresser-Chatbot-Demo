"""Intent classifier using Claude or Groq (Groq for tests)."""
from __future__ import annotations

import json
import logging
import time

import anthropic

from config import settings

logger = logging.getLogger(__name__)

_USE_GROQ = getattr(settings, "use_groq_llm", False)
if _USE_GROQ:
    try:
        from groq import AsyncGroq
    except ImportError as e:
        raise ImportError(
            "Groq is required when USE_GROQ_LLM=1. Install with: pip install groq"
        ) from e
else:
    AsyncGroq = None  # type: ignore[misc, assignment]

_INTENT_SYSTEM_PROMPT = """Sen İzellik Makeup House makyaj ve güzellik salonu için WhatsApp chatbot niyet sınıflandırıcısısın.

## NİYETLER

**Genel:**
- greeting     : Selamlama (merhaba, selam, iyi günler, günaydın, hey vb.)
- farewell     : Veda (görüşürüz, hoşça kalın, teşekkürler/sağolun + veda, bye vb.)
- affirmative  : Onaylama (evet, tamam, olur, doğru, kabul, tabi, peki vb.)
- negative     : Reddetme (hayır, istemiyorum, iptal, olmaz, vazgeçtim, hayir vb.)
- chitchat     : Konu dışı ama zararsız sohbet (nasılsın, hava durumu vb.)
- out_of_scope : Güzellik/makyaj/randevuyla HİÇ ilgisi olmayan (politika, spor, matematik vb.)

**Bilgi:**
- info_services: Hizmet listesi, ne yapılıyor, uzmanlar, sanatçılar kim
- info_price   : Fiyat, ne kadar tutar, ücret, paket, fiyat listesi
- info_hours   : Çalışma saatleri, kaçta açık/kapanır, bugün açık mısınız
- info_address : Adres, nerede, nasıl gidilir, konum, harita, telefon numarası

**Randevu:**
- booking_request   : Randevu almak/sorgulamak, müsaitlik, ne zaman gelebilirim
- cancel_booking    : Randevuyu iptal, randevumu silmek/değiştirmek istiyorum
- restart_booking   : Randevu sürecini başa al, en baştan başlamak istiyorum, yeniden başla, sıfırla vb.

**Randevu akışında veri sağlama:**
- provide_service     : Hizmet seçiyor (düğün makyajı, kına, nişan, tırnak, profesyonel vb.)
- provide_location    : Konum belirtiyor (stüdyo/salona geleyim, otel, şehir dışı otel)
- provide_staff       : Uzman/sanatçı seçiyor (İzel, Merve, Dicle, İrem, Gizem, Neslihan, Sena vb.)
- provide_date        : Tarih veriyor (yarın, cuma, 15 nisan, haftaya pazartesi, 15/04/2026 vb.)
- provide_time        : Saat veriyor (saat 10, öğleden sonra 3, 14:30, sabah 11 vb.)
- provide_guest_count : Kişi sayısı veriyor (1, 3, iki kişi, beş kişiyiz, sadece ben vb.)
- provide_name        : Ad soyad paylaşıyor (Ayşe Yılmaz, benim adım Fatma vb.)
- provide_phone       : Telefon numarası veriyor (0532..., +90... vb.)

## ENTITY ÇIKARMA
- service      : Hizmet adı (tam adıyla: "Düğün Saç & Makyaj", "Kına Türban Tasarım" vb.)
- date         : Tarih ifadesi olduğu gibi ("yarın", "bu cuma", "15/04/2026")
- time         : Saat ifadesi olduğu gibi ("14:30", "sabah 10", "öğleden sonra 3")
- name         : Ad soyad
- phone        : Telefon numarası
- guest_count  : Kişi sayısı, sadece rakam olarak ("1", "3", "5")
- location     : Konum kodu ("studio", "hotel", "out_of_city")

## SINIFLANDIRMA KURALLARI
1. Randevu akışında (geçmişte randevu adımları varsa) veri içeren mesajlar için provide_* tercih et.
2. Aynı mesajda birden fazla veri varsa en belirgin olana göre sınıflandır, diğerlerini entity olarak çıkar.
3. "Evet/tamam" tek başına → affirmative. "Evet, düğün makyajı" → provide_service.
4. Makyaj, güzellik, cilt, saç, tırnak, gelin, kına, nişan konuları HİÇBİR ZAMAN out_of_scope değildir.
5. out_of_scope'u yalnızca tamamen alakasız konular için kullan; belirsizse info_services veya booking_request seç.
6. Rakam içeren kısa mesajlar (1, 3, "iki") kişi sayısı adımındaysa provide_guest_count olabilir.
7. "Baştan başla", "yeniden başla", "başa dön", "her şeyi sil", "baştan almak istiyorum" → HER ZAMAN restart_booking. Step hint ne olursa olsun bu kurala uy.

## ÇIKTI FORMATI — SADECE JSON, başka hiçbir şey ekleme:
{
  "intent": "<intent_adı>",
  "confidence": <0.0–1.0>,
  "entities": {
    "service": "",
    "date": "",
    "time": "",
    "name": "",
    "phone": "",
    "guest_count": "",
    "location": ""
  }
}"""


# Step-specific hints passed as context when user is in an active booking flow
_STEP_HINTS: dict[str, str] = {
    "select_service":    "Kullanıcı ŞU AN HİZMET SEÇİYOR. Hizmet adı içeren yanıtlar provide_service olmalı.",
    "select_location":   "Kullanıcı ŞU AN KONUM SEÇİYOR. Stüdyo/otel/şehir dışı içeren yanıtlar provide_location olmalı.",
    "select_branch":     "Kullanıcı ŞU AN ŞUBE SEÇİYOR (Gaziantep veya İstanbul). Şehir adı içeren yanıtlar bu adım için geçerlidir.",
    "get_visit_address": "Kullanıcı ŞU AN OTEL/ZİYARET ADRESİ giriyor. Uzun metin yanıtlar adres olabilir.",
    "select_staff":      "Kullanıcı ŞU AN UZMAN/SANATÇI SEÇİYOR. İsim içeren yanıtlar provide_staff olmalı.",
    "select_date":       "Kullanıcı ŞU AN TARİH GİRİYOR. Tarih ifadesi içeren yanıtlar provide_date olmalı.",
    "select_time":       "Kullanıcı ŞU AN SAAT GİRİYOR. Saat ifadesi içeren yanıtlar provide_time olmalı.",
    "get_guest_count":   "Kullanıcı ŞU AN KİŞİ SAYISI GİRİYOR. Sayısal yanıtlar (1, 3, beş kişi vb.) provide_guest_count olmalı.",
    "get_name":          "Kullanıcı ŞU AN AD SOYAD GİRİYOR. İsim içeren yanıtlar provide_name olmalı.",
    "get_phone":         "Kullanıcı ŞU AN TELEFON NUMARASI GİRİYOR. Numara içeren yanıtlar provide_phone olmalı.",
    "confirm":           "Kullanıcı ŞU AN ONAY ADIMINDA. Evet/hayır veya onaylama/reddetme yanıtları bekleniyor.",
}


class IntentClassifier:
    """Classifies user message intents using Claude or Groq (Groq when USE_GROQ_LLM=1)."""

    def __init__(self) -> None:
        if _USE_GROQ:
            self._client = AsyncGroq(api_key=settings.groq_api_key)
            self._use_groq = True
        else:
            self._client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                timeout=20.0,
            )
            self._use_groq = False

    async def classify_intent(
        self,
        message: str,
        conversation_history: list[dict],
        current_step: str = "",
    ) -> dict:
        """Classify the intent of a user message.

        Args:
            message: The current user message to classify.
            conversation_history: List of previous messages in the conversation,
                each as a dict with 'role' and 'content' keys.
            current_step: Active booking flow step (e.g. 'get_name'), used to
                inject a step-specific hint so the model classifies in context.

        Returns:
            Dictionary containing:
                - intent (str): Classified intent name.
                - confidence (float): Confidence score between 0.0 and 1.0.
                - entities (dict): Extracted entities.
        """
        messages: list[dict] = []

        # Include recent conversation history for context (last 6 messages)
        for entry in conversation_history[-6:]:
            if entry.get("role") in ("user", "assistant"):
                messages.append({"role": entry["role"], "content": entry["content"]})

        # Add the current message
        messages.append({"role": "user", "content": message})

        # Inject step hint into system prompt so it never creates consecutive
        # assistant turns (which the Anthropic API rejects with 400).
        step_hint = _STEP_HINTS.get(current_step, "")
        system = (
            f"{_INTENT_SYSTEM_PROMPT}\n\n## MEVCUT ADIM\n{step_hint}"
            if step_hint
            else _INTENT_SYSTEM_PROMPT
        )

        hist_turns = len(messages) - 1  # exclude current message
        model_id = settings.groq_model if self._use_groq else settings.claude_classifier_model
        logger.debug(
            "[CLASSIFY] model=%s hist_turns=%d msg=%r",
            model_id, hist_turns, message[:80],
        )

        t0 = time.monotonic()
        try:
            if self._use_groq:
                # Groq: OpenAI-compatible chat completions
                groq_messages = [{"role": "system", "content": system}]
                groq_messages.extend(messages)
                response = await self._client.chat.completions.create(
                    model=settings.groq_model,
                    max_completion_tokens=512,
                    messages=groq_messages,
                )
                text_content = (response.choices[0].message.content or "").strip()
            else:
                response = await self._client.messages.create(
                    model=settings.claude_classifier_model,
                    max_tokens=512,
                    system=system,
                    messages=messages,
                )
                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content = block.text
                        break
                text_content = text_content.strip()

            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.debug("[CLASSIFY] raw=%r elapsed=%dms", text_content[:120], elapsed_ms)

            # Parse JSON response
            if text_content.startswith("```"):
                lines = text_content.split("\n")
                text_content = "\n".join(lines[1:-1])

            result: dict = json.loads(text_content)

            intent = result.get("intent", "out_of_scope")
            confidence = float(result.get("confidence", 0.0))
            entities = result.get("entities", {})
            # Filter out empty entity values for a cleaner log
            non_empty_entities = {k: v for k, v in entities.items() if v}

            logger.info(
                "[CLASSIFY] intent=%-20s conf=%.2f entities=%s elapsed=%dms",
                intent, confidence,
                non_empty_entities if non_empty_entities else "{}",
                elapsed_ms,
            )

            return {"intent": intent, "confidence": confidence, "entities": entities}

        except (json.JSONDecodeError, KeyError, AttributeError) as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.warning("[CLASSIFY] parse error after %dms: %s", elapsed_ms, exc)
            return {"intent": "unknown", "confidence": 0.0, "entities": {}}
        except anthropic.APIError as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            logger.error("[CLASSIFY] Anthropic API error after %dms: %s", elapsed_ms, exc)
            return {"intent": "unknown", "confidence": 0.0, "entities": {}}
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if self._use_groq:
                logger.error("[CLASSIFY] Groq API error after %dms: %s", elapsed_ms, exc)
            else:
                raise
            return {"intent": "unknown", "confidence": 0.0, "entities": {}}
