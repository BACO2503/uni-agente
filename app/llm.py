"""
LLMClient: interfaz común para generar texto, con cascada de fallback.

Cada proveedor (Gemini, Groq, Cerebras) se activa solo si tiene su API key
configurada en .env. En modo `fallback` (el default) se intenta el primero
de LLM_FALLBACK_ORDER; si responde 429 (cuota agotada) o falla, se salta
automáticamente al siguiente, sin que quien pregunta lo note. Esto vuelve
la aplicación resistente a los límites de las capas gratuitas: haría falta
agotar los tres proveedores a la vez para que deje de responder.

También existe el modo `echo`, que no llama a ninguna API: devuelve el
contexto recuperado tal cual. Sirve para probar el pipeline de RAG
completo (ingesta, recuperación, citas) sin gastar cuota ni necesitar
ninguna key.
"""
from __future__ import annotations

import requests

from . import config


class ProviderError(Exception):
    """Un proveedor falló o no tiene key; se debe intentar el siguiente."""


class QuotaExhaustedError(Exception):
    """Todos los proveedores configurados agotaron su cuota."""


def _call_gemini(prompt: str) -> str:
    if not config.GEMINI_API_KEY:
        raise ProviderError("GEMINI_API_KEY no configurada")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_MODEL}:generateContent"
    )
    resp = requests.post(
        url,
        params={"key": config.GEMINI_API_KEY},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    if resp.status_code == 429:
        raise ProviderError("Gemini: cuota agotada (429)")
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_groq(prompt: str) -> str:
    if not config.GROQ_API_KEY:
        raise ProviderError("GROQ_API_KEY no configurada")
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
        json={
            "model": config.GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    if resp.status_code == 429:
        raise ProviderError("Groq: cuota agotada (429)")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_cerebras(prompt: str) -> str:
    if not config.CEREBRAS_API_KEY:
        raise ProviderError("CEREBRAS_API_KEY no configurada")
    resp = requests.post(
        "https://api.cerebras.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.CEREBRAS_API_KEY}"},
        json={
            "model": config.CEREBRAS_MODEL,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    if resp.status_code == 429:
        raise ProviderError("Cerebras: cuota agotada (429)")
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_echo(prompt: str) -> str:
    return prompt


_PROVIDERS = {
    "gemini": _call_gemini,
    "groq": _call_groq,
    "cerebras": _call_cerebras,
    "echo": _call_echo,
}

# Se completa dinámicamente al final del módulo con el estado real de cada
# proveedor (si tiene key configurada), para el endpoint /api/diagnostico.
PROVIDER_STATUS: dict[str, bool] = {}


def _has_key(provider: str) -> bool:
    return {
        "gemini": bool(config.GEMINI_API_KEY),
        "groq": bool(config.GROQ_API_KEY),
        "cerebras": bool(config.CEREBRAS_API_KEY),
        "echo": True,
    }.get(provider, False)


def generate(prompt: str) -> tuple[str, str]:
    """Devuelve (texto_generado, proveedor_usado)."""
    if config.LLM != "fallback":
        fn = _PROVIDERS.get(config.LLM)
        if fn is None:
            raise ValueError(f"Proveedor LLM desconocido: {config.LLM}")
        return fn(prompt), config.LLM

    errors = []
    for provider in config.LLM_FALLBACK_ORDER:
        if not _has_key(provider):
            continue
        fn = _PROVIDERS.get(provider)
        if fn is None:
            continue
        try:
            return fn(prompt), provider
        except ProviderError as e:
            errors.append(str(e))
            continue
        except requests.RequestException as e:
            errors.append(f"{provider}: {e}")
            continue

    raise QuotaExhaustedError(
        "Todos los proveedores configurados fallaron o agotaron su cuota: "
        + "; ".join(errors) if errors else
        "Ningún proveedor tiene API key configurada. Revisa tu archivo .env."
    )


def diagnostico() -> dict:
    return {
        provider: {"configurado": _has_key(provider)}
        for provider in list(config.LLM_FALLBACK_ORDER) + ["echo"]
    }
