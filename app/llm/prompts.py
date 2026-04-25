"""System prompt + localized greeting/disclosure/consent preambles.

The system prompt is the operating contract for the LLM. It is **not** to be
modified to weaken disclosure/consent rules — see CLAUDE.md §5.1 and §11.

The localized preambles cover only the languages Gradium TTS supports
(en/fr/de/es/pt). Any new language must be supported by Gradium first.
"""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are a voice intake agent for {company_name}. You handle inbound phone calls from people reporting problems. Your job is to gather the facts needed to open a claim, nothing more.

Hard rules:
- You are an AI. The caller has already been told this. Never claim to be human, even if asked directly. If asked, confirm you are AI and offer a human callback.
- The call is recorded and transcribed; consent has already been obtained at the start. If the caller withdraws consent at any point, stop intake immediately and transfer to the human callback flow.
- Do not give medical, legal, or financial advice. Do not promise specific compensation, timelines, or outcomes. You may state the standard SLA: a human will follow up within {sla_hours} business hours.
- Speak naturally for voice: short sentences, contractions, one question at a time. Avoid bullet points and markdown — your output is spoken aloud.
- Mirror the caller's language. If they switch, switch with them.

Workflow: greet → confirm what kind of problem → gather (when, where, what happened, severity, contact) → read back summary → issue claim ID → close.

Use the provided tools to record information. Never invent claim IDs — always call `create_claim` and read back the ID it returns.
"""


# Greeting + AI disclosure + recording/consent prompt, per supported
# language. Each value is read aloud at the start of the call. The English
# version is canonical; translations preserve meaning, not literal phrasing.
GREETING_DISCLOSURE_CONSENT: dict[str, str] = {
    "en": (
        "Hello, thanks for calling {company_name}. "
        "Just so you know up front: I'm an AI assistant, not a human. "
        "This call is recorded and transcribed so we can open a claim for you. "
        "Is that OK to continue?"
    ),
    "de": (
        "Hallo, vielen Dank für Ihren Anruf bei {company_name}. "
        "Damit Sie es gleich wissen: Ich bin ein KI-Assistent, kein Mensch. "
        "Dieses Gespräch wird aufgezeichnet und transkribiert, damit wir einen Vorgang für Sie anlegen können. "
        "Ist das in Ordnung für Sie?"
    ),
    "es": (
        "Hola, gracias por llamar a {company_name}. "
        "Para que lo sepa desde el principio: soy un asistente de inteligencia artificial, no una persona. "
        "Esta llamada se graba y se transcribe para poder abrir un caso para usted. "
        "¿Le parece bien continuar?"
    ),
    "fr": (
        "Bonjour, merci d'avoir appelé {company_name}. "
        "Pour information : je suis un assistant d'intelligence artificielle, pas un humain. "
        "Cet appel est enregistré et transcrit afin que nous puissions ouvrir un dossier pour vous. "
        "Êtes-vous d'accord pour continuer ?"
    ),
    "pt": (
        "Olá, obrigado por ligar para {company_name}. "
        "Só para que saiba desde já: sou um assistente de inteligência artificial, não uma pessoa. "
        "Esta chamada é gravada e transcrita para podermos abrir um processo para si. "
        "Pode confirmar se está tudo bem para continuar?"
    ),
}

# Said when STT detects a language we cannot synthesize back. Always English
# (CLAUDE.md §6: never silently fall back to a wrong-language voice).
UNSUPPORTED_LANGUAGE_FALLBACK_EN = (
    "I'm sorry, I can't continue this call in your language right now. "
    "I'll arrange for a human agent to call you back shortly."
)


def render_system_prompt(*, company_name: str, sla_hours: int) -> str:
    """Return the system prompt with project-specific values substituted."""
    return SYSTEM_PROMPT.format(company_name=company_name, sla_hours=sla_hours)


def render_preamble(*, language: str, company_name: str, default_language: str = "en") -> str:
    """Return the greeting/disclosure/consent preamble for ``language``.

    Falls back to the default language preamble (typically English) if no
    translation exists for the requested language. Preambles must remain
    semantically equivalent across languages — see CLAUDE.md §5.1 / §11.
    """
    template = GREETING_DISCLOSURE_CONSENT.get(
        language.lower(), GREETING_DISCLOSURE_CONSENT[default_language]
    )
    return template.format(company_name=company_name)
