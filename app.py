"""
Bot DB Multi-Service v5.1
IA Groq + catálogo Vodacom + pedidos + SMS M-Pesa/E-Mola
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
SMS_SECRET = os.environ.get("SMS_SECRET", "")

API_URL = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

ADMIN_NUMBERS = {
    "258846818458",
    "258876063563",
}

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ==================== CATÁLOGO ====================
PRODUTOS_PROMO = {
    "esp_275":  {"nome": "Especial 7 Dias – 275 MT", "preco": 275, "cat": "promo"},
    "esp_468":  {"nome": "Especial 30 Dias – 468 MT", "preco": 468, "cat": "promo"},
    "esp_925":  {"nome": "Especial 30 Dias – 925 MT", "preco": 925, "cat": "promo"},
    "esp_1400": {"nome": "Especial 30 Dias – 1.400 MT", "preco": 1400, "cat": "promo"},
    "esp_2800": {"nome": "Especial 30 Dias – 2.800 MT", "preco": 2800, "cat": "promo"},
    "net_50":   {"nome": "WTF Internet 7 Dias – 50 MT", "preco": 50, "cat": "promo"},
    "net_280":  {"nome": "Internet 8.909 MB – 30 Dias – 280 MT", "preco": 280, "cat": "promo"},
    "net_475":  {"nome": "Internet 16.589 MB – 30 Dias – 475 MT", "preco": 475, "cat": "promo"},
    "net_950":  {"nome": "Internet 33.280 MB – 30 Dias – 950 MT", "preco": 950, "cat": "promo"},
}


def valor_agent(preco, cat="normal"):
    if cat == "promo":
        return int(round(preco * 500 / 468.0))
    return int(preco)


def catalogo_para_ia():
    return """
=== CRÉDITO NORMAL ===
Qualquer valor de 10 a 2000 MT.

=== VODA JACKPOT (só Vodacom) ===
Diário: 2MT=5min | 4=9 | 5=11 | 10=22 | 15=33 | 20=45 | 30=66 | 40=90
Semanal: 50MT=110min | 100=230min
Mensal: 200MT=440min | 500=1100min
Sugestão mediana: diário 15MT | semanal 50/100 | mensal 200MT

=== TODAS AS REDES JACKPOT ===
Diário: 2=5 | 4=9 | 5=10 | 10=21 | 15=30 | 20=40 | 30=60 | 40=85 min
Semanal: 50=100 | 100=220 min
Mensal: 200=410 | 500=1100 min
Sugestão mediana: diário 15MT | semanal 50/100 | mensal 200MT

=== SÓ PAPO EXTRA (6 horas) ===
5MT=12min | 10=23 | 15=35 | 20=47
Sugestão mediana: 10 ou 15 MT

=== PROMOÇÕES ===
Especiais: 275 | 468 | 925 | 1400 | 2800 MT
Internet: 50 | 280 | 475 | 950 MT
Sugestão mediana: especial 468 | internet 280 ou 475

REGRA: se o cliente não disser valor, sugere preço MÉDIO.
Cliente paga sempre o valor tabelado.
"""

# ==================== MEMÓRIA ====================
historico = defaultdict(list)
estados = defaultdict(dict)
pedidos = {}
proximo_id = 1

# ==================== FUNÇÕES BASE ====================

def enviar_mensagem(numero, texto):
    try:
        requests.post(
            API_URL,
            data={"token": TOKEN, "to": numero, "body": texto},
            timeout=15,
        )
    except Exception as e:
        print("Erro envio:", e)


def notificar_admins(msg):
    for a in ADMIN_NUMBERS:
        enviar_mensagem(a, msg)


def e_admin(numero):
    n = (numero or "").replace("+", "")
    return n in ADMIN_NUMBERS or numero in ADMIN_NUMBERS


def criar_pedido(wa, nome, preco, nr, cat="normal"):
    global proximo_id
    pid = proximo_id
    proximo_id += 1
    pedidos[pid] = {
        "id": pid,
        "wa": wa,
        "produto": nome,
        "preco_cliente": int(preco),
        "valor_agent": valor_agent(preco, cat),
        "nr_carregar": nr,
        "cat": cat,
        "estado": "aguardando_pagamento",
        "comprovativo": "",
        "criado": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    return pid


def ficha_agent(p):
    return (
        "📋 *FICHA AGENT APP – Pedido #{}*\n\n"
        "Pacote: *{}*\n"
        "Número: *{}*\n"
        "Cliente paga: *{} MT*\n"
        "Valor Agent App: *{} MT*\n\n"
        "Na app:\n"
        "1. Ofertas\n"
        "2. Tipo de oferta\n"
        "3. Escolher\n"
        "4. Nr: {}\n"
        "5. Código M-Pesa\n\n"
        "Depois: *activado {}*"
    ).format(
        p["id"],
        p["produto"],
        p["nr_carregar"],
        p["preco_cliente"],
        p["valor_agent"],
        p["nr_carregar"],
        p["id"],
    )


# ==================== IA ====================

def chamar_groq(numero, mensagem):
    historico[numero].append({"role": "user", "content": mensagem})
    if len(historico[numero]) > 12:
        historico[numero] = historico[numero][-12:]

    system = (
        "Tu és o assistente da *DB Multi-Service* em Moçambique. "
        "Vendes recargas e pacotes Vodacom.\n\n"
        "TOM: descontraído, usa \"tu\", linguagem simples. Foco em vendas.\n\n"
        + catalogo_para_ia()
        + "\n\nCOMO VENDER:\n"
        "1. Entende o que o cliente quer.\n"
        "2. Se não disser valor, sugere preço MÉDIO.\n"
        "3. Confirma pacote e preço.\n"
        "4. Pede número Vodacom (9 dígitos, começa por 8).\n"
        "5. Pagamento: M-Pesa 846818458 | E-Mola 876063563\n"
        "6. Pede comprovativo.\n"
        "Nunca inventes preços. Respostas curtas."
    )

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
        print("Erro Groq:", e)
        return "Desculpa, tive um problema técnico. Podes repetir? 🙏"


# ==================== ADMIN ====================

def processar_admin(texto):
    t = texto.strip().lower()

    if t == "pedidos":
        pend = [
            p
            for p in pedidos.values()
            if p["estado"]
            in ("aguardando_pagamento", "pendente_confirmacao", "confirmado")
        ]
        if not pend:
            return "Não há pedidos pendentes."
        msg = "📋 *Pedidos:*\n\n"
        for p in pend:
            msg += (
                "#{0} [{1}]\n{2}\n"
                "Cliente {3} → Agent {4} MT\n"
                "Nr: {5} | WA: {6}\n\n"
            ).format(
                p["id"],
                p["estado"],
                p["produto"],
                p["preco_cliente"],
                p["valor_agent"],
                p["nr_carregar"],
                p["wa"],
            )
        return msg

    m = re.match(r"confirmar\s+(\d+)", t)
    if m:
        pid = int(m.group(1))
        if pid not in pedidos:
            return "Pedido #{} não existe.".format(pid)
        pedidos[pid]["estado"] = "confirmado"
        enviar_mensagem(
            pedidos[pid]["wa"],
            "✅ Pagamento do pedido #{} confirmado! Vamos activar em breve.".format(pid),
        )
        return ficha_agent(pedidos[pid])

    m = re.match(r"activado\s+(\d+)", t)
    if m:
        pid = int(m.group(1))
        if pid not in pedidos:


            return "Pedido #{} não existe.".format(pid)
        pedidos[pid]["estado"] = "activado"
        enviar_mensagem(
            pedidos[pid]["wa"],
            "🎉 Pedido #{} activ
            if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
