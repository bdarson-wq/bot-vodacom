"""
Bot DB Multi-Service v5.0
Catálogo completo Vodacom + IA Groq + pedidos + Agent App
"""

from flask import Flask, request, jsonify
import requests
import os
import re
from datetime import datetime
from collections import defaultdict
from openai import OpenAI

app = Flask(__name__)

# ==================== CONFIG ====================
INSTANCE_ID = os.environ.get("INSTANCE_ID", "")
TOKEN = os.environ.get("TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

API_URL = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

ADMIN_NUMBERS = {
    "258846818458",
    "258876063563",
}

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ==================== CATÁLOGO ====================
# tipo: "promo" → agent = preco * 500/468 | resto → agent = preco

PRODUTOS_PROMO = {
    "esp_275":  {"nome": "Especial 7 Dias – 275 MT", "preco": 275, "cat": "promo", "desc": "7.680 MB + voz/SMS"},
    "esp_468":  {"nome": "Especial 30 Dias – 468 MT", "preco": 468, "cat": "promo", "desc": "10.138 MB + voz/SMS"},
    "esp_925":  {"nome": "Especial 30 Dias – 925 MT", "preco": 925, "cat": "promo", "desc": "20.787 MB + voz/SMS"},
    "esp_1400": {"nome": "Especial 30 Dias – 1.400 MT", "preco": 1400, "cat": "promo", "desc": "31.744 MB + voz/SMS"},
    "esp_2800": {"nome": "Especial 30 Dias – 2.800 MT", "preco": 2800, "cat": "promo", "desc": "64.819 MB + voz/SMS"},
    "net_50":   {"nome": "WTF Internet 7 Dias – 50 MT", "preco": 50, "cat": "promo", "desc": "Internet 7 dias"},
    "net_280":  {"nome": "Internet 8.909 MB – 30 Dias – 280 MT", "preco": 280, "cat": "promo", "desc": "Internet 30 dias"},
    "net_475":  {"nome": "Internet 16.589 MB – 30 Dias – 475 MT", "preco": 475, "cat": "promo", "desc": "Internet 30 dias"},
    "net_950":  {"nome": "Internet 33.280 MB – 30 Dias – 950 MT", "preco": 950, "cat": "promo", "desc": "Internet 30 dias"},
}

# Jackpots e Só Papo (agent = preco cliente)
JACKPOT_VODA = [
    (2, 5), (4, 9), (5, 11), (10, 22), (15, 33), (20, 45), (30, 66), (40, 90),
]
JACKPOT_VODA_SEM = [(50, 110), (100, 230)]
JACKPOT_VODA_MES = [(200, 440), (500, 1100)]

JACKPOT_REDES = [
    (2, 5), (4, 9), (5, 10), (10, 21), (15, 30), (20, 40), (30, 60), (40, 85),
]
JACKPOT_REDES_SEM = [(50, 100), (100, 220)]
JACKPOT_REDES_MES = [(200, 410), (500, 1100)]

SOPAPO = [(5, 12), (10, 23), (15, 35), (20, 47)]


def valor_agent(preco: int, cat: str = "normal") -> int:
    if cat == "promo":
        return round(preco * 500 / 468)
    return preco


def catalogo_para_ia() -> str:
    return f"""
=== CRÉDITO NORMAL ===
Qualquer valor de 10 a 2000 MT. Cliente paga exactamente esse valor.

=== VODA JACKPOT (só Vodacom) ===
Diário: 2MT=5min | 4=9 | 5=11 | 10=22 | 15=33 | 20=45 | 30=66 | 40=90
Semanal: 50MT=110min | 100=230min
Mensal: 200MT=440min | 500=1100min
Sugestão mediana: diário 15MT (33min) | semanal 50 ou 100 | mensal 200MT

=== TODAS AS REDES JACKPOT ===
Diário: 2MT=5min | 4=9 | 5=10 | 10=21 | 15=30 | 20=40 | 30=60 | 40=85
Semanal: 50MT=100min | 100=220min
Mensal: 200MT=410min | 500=1100min
Sugestão mediana: diário 15MT (30min) | semanal 50/100 | mensal 200MT

=== SÓ PAPO EXTRA (válido 6 horas) ===
5MT=12min | 10=23min | 15=35min | 20=47min
Sugestão mediana: 10 ou 15 MT

=== PROMOÇÕES (preços especiais) ===
Especiais voz+SMS+net: 275 | 468 | 925 | 1400 | 2800 MT
Internet: 50 (WTF 7d) | 280 | 475 | 950 MT
Sugestão mediana: especial 468 MT | internet 280 ou 475 MT

REGRA DE SUGESTÃO: quando o cliente não especificar valor, propõe sempre a opção de preço MÉDIO da categoria.
Cliente paga SEMPRE o valor tabelado acima.
"""

# ==================== MEMÓRIA ====================
historico = defaultdict(list)
estados = defaultdict(dict)
pedidos = {}
proximo_id = 1

# ==================== FUNÇÕES ====================

def enviar_mensagem(numero: str, texto: str):
    try:
        requests.post(API_URL, data={"token": TOKEN, "to": numero, "body": texto}, timeout=15)
    except Exception as e:
        print(f"Erro envio: {e}")


def notificar_admins(msg: str):
    for a in ADMIN_NUMBERS:
        enviar_mensagem(a, msg)


def e_admin(numero: str) -> bool:
    n = numero.replace("+", "")
    return n in ADMIN_NUMBERS or numero in ADMIN_NUMBERS


def criar_pedido(wa: str, nome: str, preco: int, nr: str, cat: str = "normal") -> int:
    global proximo_id
    pid = proximo_id
    proximo_id += 1
    pedidos[pid] = {
        "id": pid,
        "wa": wa,
        "produto": nome,
        "preco_cliente": preco,
        "valor_agent": valor_agent(preco, cat),
        "nr_carregar": nr,
        "cat": cat,
        "estado": "aguardando_pagamento",
        "comprovativo": "",
        "criado": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    return pid


def ficha_agent(p: dict) -> str:
    return (
        f"📋 *FICHA AGENT APP – Pedido #{p['id']}*\n\n"
        f"Pacote: *{p['produto']}*\n"
        f"Número: *{p['nr_carregar']}*\n"
        f"Cliente paga: *{p['preco_cliente']} MT*\n"
        f"Valor Agent App: *{p['valor_agent']} MT*\n\n"
        f"Na app:\n"
        f"1. Ofertas\n"
        f"2. Tipo de oferta\n"
        f"3. Escolher\n"
        f"4. Nr: {p['nr_carregar']}\n"
        f"5. Código M-Pesa\n\n"
        f"Depois: *activado {p['id']}*"
    )


# ==================== IA ====================

def chamar_groq(numero: str, mensagem: str) -> str:
    historico[numero].append({"role": "user", "content": mensagem})
    if len(historico[numero]) > 12:
        historico[numero] = historico[numero][-12:]

    system = f"""
Tu és o assistente da *DB Multi-Service* em Moçambique. Vendes recargas e pacotes Vodacom.

TOM: descontraído, usa "tu", linguagem simples e próxima. Foco em vendas e retenção.

{catalogo_para_ia()}

COMO VENDER:
1. Entende o que o cliente quer (crédito, minutos, internet, pacote completo).
2. Se não disser valor, sugere a opção de PREÇO MÉDIO.
3. Confirma o pacote e o preço tabelado.
4. Pede o número Vodacom a carregar (9 dígitos, começa por 8).
5. Mostra resumo + pagamento:
   M-Pesa: 846818458
   E-Mola: 876063563
6. Pede o comprovativo.

Nunca inventes preços. Respostas curtas para WhatsApp.
"""

    messages = [{"role": "system", "content": system}] + historico[numero]

    try:
        r = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            temperature=0.7,
            max_tokens=450,
        )
        texto = r.choices[0].message.content.strip()
        historico[numero].append({"role": "assistant", "content": texto})
        return texto
    except Exception as e:
        print(f"Erro Groq: {e}")
        return "Desculpa, tive um problema técnico. Podes repetir? 🙏"


# ==================== ADMIN ====================

def processar_admin(texto: str) -> str | None:
    t = texto.strip().lower()

    if t == "pedidos":
        pend = [p for p in pedidos.values() if p["estado"] in ("aguardando_pagamento", "pendente_confirmacao", "confirmado")]
        if not pend:
            return "Não há pedidos pendentes."
        msg = "📋 *Pedidos:*\n\n"
        for p in pend:
            msg += (
                f"#{p['id']} [{p['estado']}]\n"
                f"{p['produto']}\n"
                f"Cliente {p['preco_cliente']} → Agent {p['valor_agent']} MT\n"
                f"Nr: {p['nr_carregar']} | WA: {p['wa']}\n\n"
            )
        return msg

    m = re.match(r"confirmar\s+(\d+)", t)
    if m:
        pid = int(m.group(1))
        if pid not in pedidos:
            return f"Pedido #{pid} não existe."
        pedidos[pid]["estado"] = "confirmado"
        enviar_mensagem(pedidos[pid]["wa"], f"✅ Pagamento do pedido #{pid} confirmado! Vamos activar em breve.")
        return ficha_agent(pedidos[pid])

    m = re.match(r"activado\s+(\d+)", t)
    if m:
        pid = int(m.group(1))
        if pid not in pedidos:
            return f"Pedido #{pid} não existe."
        pedidos[pid]["estado"] = "activado"
        enviar_mensagem(pedidos[pid]["wa"], f"🎉 Pedido #{pid} activado! Obrigado pela preferência 🙏")
        return f"✅ Pedido #{pid} activado."

    m = re.match(r"rejeitar\s+(\d+)", t)
    if m:
        pid = int(m.group(1))
        if pid not in pedidos:
            return f"Pedido #{pid} não existe."
        pedidos[pid]["estado"] = "rejeitado"
        enviar_mensagem(pedidos[pid]["wa"], f"❌ Não confirmámos o pagamento do pedido #{pid}. Fala connosco se precisares.")
        return f"Pedido #{pid} rejeitado."

    return None


# ==================== DETECÇÃO ====================

def extrair_valor(texto: str):
    for n in re.findall(r"\b(\d{1,5})(?:[.,]\d{2})?\b", texto.replace(" ", "")):
        v = int(n)
        if 2 <= v <= 5000:
            return v
    return None


def detectar_produto(texto: str):
    """Tenta identificar produto pelo texto do cliente."""
    t = texto.lower().replace(" ", "")

    # Promoções por preço
    mapa_promo = {p["preco"]: p for p in PRODUTOS_PROMO.values()}
    for preco, p in mapa_promo.items():
        if str(preco) in t:
            return p["nome"], preco, "promo"

    # Crédito explícito
    if "credito" in t or "crédito" in texto.lower() or "recarga" in t:
        v = extrair_valor(texto)
        if v and 10 <= v <= 2000:
            return f"Crédito {v} MT", v, "normal"

    # Só Papo
    if "papo" in t or "sopapo" in t:
        v = extrair_valor(texto) or 10
        return f"Só Papo Extra {v} MT", v, "normal"

    # Jackpot
    if "jackpot" in t or "jactpot" in t:
        v = extrair_valor(texto) or 15
        tipo = "Todas Redes" if "rede" in t else "Voda"
        return f"{tipo} Jackpot {v} MT", v, "normal"

    return None


# ==================== PROCESSAR ====================

def processar_mensagem(numero: str, texto: str) -> str:
    if e_admin(numero):
        r = processar_admin(texto)
        if r is not None:
            return r

    texto_l = texto.strip().lower()

    if texto_l in ("menu", "início", "inicio", "reset"):
        estados[numero] = {}
        return (
            "Olá! 👋 *DB Multi-Service*\n\n"
            "O que precisas?\n"
            "• Crédito (10–2000 MT)\n"
            "• Minutos (Jackpot / Só Papo)\n"
            "• Internet\n"
            "• Pacote voz+net\n\n"
            "Diz o que queres ou o valor que tens 😊"
        )

    # Número Vodacom (9 dígitos)
    nr = re.sub(r"\D", "", texto)
    if len(nr) == 9 and nr.startswith("8") and estados[numero].get("produto"):
        nome, preco, cat = estados[numero]["produto"]
        pid = criar_pedido(numero, nome, preco, nr, cat)
        estados[numero]["pedido_id"] = pid
        return (
            f"📋 *Pedido #{pid}*\n\n"
            f"Pacote: *{nome}*\n"
            f"Valor: *{preco} MT*\n"
            f"Número: *{nr}*\n\n"
            f"💳 M-Pesa: *846818458*\n"
            f"💳 E-Mola: *876063563*\n\n"
            f"Paga e envia o *comprovativo* aqui."
        )

    # Comprovativo
    palavras = ["comprovativo", "paguei", "já paguei", "transferi", "mpesa", "m-pesa", "emola", "e-mola"]
    if any(p in texto_l for p in palavras) or (extrair_valor(texto) and len(texto) > 15):
        pedido = None
        for p in pedidos.values():
            if p["wa"] == numero and p["estado"] == "aguardando_pagamento":
                pedido = p
                break
        valor = extrair_valor(texto)
        if pedido:
            pedido["comprovativo"] = texto
            pedido["estado"] = "pendente_confirmacao"
            msg = (
                f"🔔 *COMPROVATIVO #{pedido['id']}*\n\n"
                f"WA: {numero}\n"
                f"Pacote: {pedido['produto']}\n"
                f"Nr: {pedido['nr_carregar']}\n"
                f"Cliente: {pedido['preco_cliente']} MT\n"
                f"Agent App: *{pedido['valor_agent']} MT*\n"
                f"Valor no texto: {valor or 'n/d'}\n\n"
                f"{texto}\n\n"
                f"✅ confirmar {pedido['id']}\n"
                f"❌ rejeitar {pedido['id']}"
            )
            notificar_admins(msg)
            return f"✅ Comprovativo do pedido #{pedido['id']} recebido! Vamos verificar 🙏"
        notificar_admins(f"🔔 Comprovativo sem pedido formal\nCliente: {numero}\n{texto}")
        return "✅ Comprovativo recebido. Já verificamos."

    # Detectar produto na mensagem
    det = detectar_produto(texto)
    if det:
        estados[numero]["produto"] = det
        nome, preco, cat = det
        return (
            f"Boa escolha: *{nome}* ({preco} MT).\n\n"
            f"Envia o *número Vodacom* onde queres carregar\n"
            f"(ex: 84XXXXXXX)"
        )

    # IA para o resto
    return chamar_groq(numero, texto)


# ==================== WEBHOOK ====================

# ==================== SMS M-PESA / E-MOLA ====================

def extrair_valor_sms(texto: str):
    """Extrai valores monetários típicos de SMS M-Pesa/E-Mola."""
    t = texto.replace(" ", "").replace(",", ".")
    # Padrões: 468.00 MT | 468MT | MT468 | 468,00
    candidatos = re.findall(
        r"(?:MT|mt|Mts|mts)?\s*(\d{1,5}(?:[.,]\d{2})?)\s*(?:MT|mt|Mts|mts)?",
        texto,
        flags=re.IGNORECASE,
    )
    valores = []
    for c in candidatos:
        try:
            v = float(c.replace(",", "."))
            if 2 <= v <= 5000:
                valores.append(int(round(v)))
        except ValueError:
            continue
    return valores


def extrair_id_transacao(texto: str):
    """Tenta apanhar IDs tipo CDE1H2I3J4 ou números longos."""
    m = re.search(r"\b([A-Z0-9]{8,12})\b", texto)
    if m:
        return m.group(1)
    m = re.search(r"\b(\d{10,14})\b", texto)
    if m:
        return m.group(1)
    return None


def match_pedido_por_valor(valor: int, tolerancia: int = 2):
    """
    Procura pedido pendente cujo preco_cliente esteja perto do valor da SMS.
    Prioridade: mais recente primeiro.
    """
    candidatos = [
        p for p in pedidos.values()
        if p["estado"] in ("aguardando_pagamento", "pendente_confirmacao")
    ]
    # mais recentes primeiro
    candidatos.sort(key=lambda x: x["id"], reverse=True)

    exact = [p for p in candidatos if abs(p["preco_cliente"] - valor) <= tolerancia]
    if exact:
        return exact[0]
    return None


def processar_sms_pagamento(texto_sms: str, origem: str = "sms") -> dict:
    """
    Processa texto de SMS M-Pesa/E-Mola.
    Retorna dict com resultado para log/resposta HTTP.
    """
    if not texto_sms or len(texto_sms.strip()) < 5:
        return {"ok": False, "motivo": "texto vazio"}

    valores = extrair_valor_sms(texto_sms)
    tx_id = extrair_id_transacao(texto_sms)
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    if not valores:
        notificar_admins(
            f"📩 SMS recebida sem valor claro ({origem})\n"
            f"Hora: {agora}\n\n{texto_sms}"
        )
        return {"ok": False, "motivo": "sem valor", "texto": texto_sms}

    # tenta match com o valor mais "plausível" (maior primeiro costuma ser o montante)
    pedido = None
    valor_usado = None
    for v in sorted(set(valores), reverse=True):
        pedido = match_pedido_por_valor(v, tolerancia=2)
        if pedido:
            valor_usado = v
            break

    if not pedido:
        notificar_admins(
            f"📩 SMS sem pedido correspondente\n"
            f"Valores detectados: {valores}\n"
            f"ID: {tx_id or 'n/d'}\n"
            f"Hora: {agora}\n\n{texto_sms}\n\n"
            f"Usa *pedidos* e *confirmar X* se for válido."
        )
        return {
            "ok": False,
            "motivo": "sem match",
            "valores": valores,
            "tx_id": tx_id,
        }

    # Match encontrado → confirmar automaticamente
    pedido["estado"] = "confirmado"
    pedido["comprovativo"] = texto_sms
    pedido["sms_valor"] = valor_usado
    pedido["sms_id"] = tx_id
    pedido["confirmado_em"] = agora

    # Avisa o cliente
    enviar_mensagem(
        pedido["wa"],
        f"✅ Pagamento do pedido *#{pedido['id']}* confirmado!\n"
        f"Vamos activar o pacote em breve. Obrigado 🙏",
    )

    # Ficha Agent App para ti
    notificar_admins(
        f"✅ *PAGAMENTO CONFIRMADO POR SMS*\n"
        f"Pedido #{pedido['id']}\n"
        f"Valor SMS: {valor_usado} MT | ID: {tx_id or 'n/d'}\n"
        f"Hora: {agora}\n\n"
        f"{ficha_agent(pedido)}"
    )

    return {
        "ok": True,
        "pedido_id": pedido["id"],
        "valor": valor_usado,
        "tx_id": tx_id,
    }
    @app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    msg = data.get("data", {})
    if data.get("event_type") == "message_received" and not msg.get("fromMe", False):
        numero = msg.get("from", "")
        texto = msg.get("body", "") or ""
        if texto:
            enviar_mensagem(numero, processar_mensagem(numero, texto))
    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"])
def home():
    return "Bot DB Multi-Service v5.0 OK ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
