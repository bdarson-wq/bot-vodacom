"""
Bot DB Multi-Service - Versão 3.0 (IA Groq + Vendas)
"""

from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime
from collections import defaultdict
from openai import OpenAI

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
INSTANCE_ID = os.environ.get("INSTANCE_ID", "")
TOKEN = os.environ.get("TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

API_URL = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

# Números dos administradores (recebem notificação de comprovativos)
ADMIN_NUMBERS = [
    "258846818458",   # M-Pesa
    "258876063563",   # E-Mola
]

# Cliente Groq (compatível com OpenAI)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

# ==================== CATÁLOGO DE PRODUTOS ====================
PRODUTOS_TEXTO = """
=== OFERTAS ESPECIAIS (Voz + SMS + Internet) ===
1. 7 Dias – 275 MT → 7.680 MB + 5 Min Internacionais + 25 MB Roaming
2. 30 Dias – 468 MT → 10.138 MB + 10 Min Internacionais + 30 MB Roaming
3. 30 Dias – 925 MT → 20.787 MB + 20 Min Internacionais + 80 MB Roaming
4. 30 Dias – 1.400 MT → 31.744 MB + 30 Min Internacionais + 150 MB Roaming
5. 30 Dias – 2.800 MT → 64.819 MB + 40 Min Internacionais + 700 MB Roaming

=== OFERTAS SÓ DE INTERNET ===
1. WTF 7 Dias – 50 MT
2. 8.909 MB – 30 Dias – 280 MT
3. 16.589 MB – 30 Dias – 475 MT
4. 33.280 MB – 30 Dias – 950 MT

Nota importante: Para pacotes semanais/mensais o número não pode ter "txuna" (crédito em dívida).

Métodos de pagamento:
- M-Pesa: 846818458
- E-Mola: 876063563
"""

# ==================== MEMÓRIA DAS CONVERSAS ====================
historico = defaultdict(list)          # histórico de mensagens
estados = defaultdict(dict)            # estado do pedido (produto, número, etc.)

# ==================== FUNÇÕES ====================

def enviar_mensagem(numero: str, texto: str):
    payload = {
        "token": TOKEN,
        "to": numero,
        "body": texto,
    }
    try:
        requests.post(API_URL, data=payload, timeout=15)
    except Exception as e:
        print(f"Erro ao enviar: {e}")


def notificar_admins(mensagem: str):
    for admin in ADMIN_NUMBERS:
        enviar_mensagem(admin, mensagem)


def limpar_conversa(numero: str):
    if numero in historico:
        del historico[numero]
    if numero in estados:
        del estados[numero]


def chamar_groq(numero: str, mensagem_cliente: str) -> str:
    """Chama a IA da Groq com o contexto da conversa"""
    
    # Adiciona a mensagem do cliente ao histórico
    historico[numero].append({"role": "user", "content": mensagem_cliente})
    
    # Mantém só as últimas 10 mensagens para não estourar o contexto
    if len(historico[numero]) > 10:
        historico[numero] = historico[numero][-10:]

    system_prompt = f"""
Tu és o assistente oficial da *DB Multi-Service*, uma loja de confiança em Moçambique que vende pacotes Vodacom a preços promocionais.

O teu objectivo principal é:
1. Ajudar o cliente de forma simpática e descontraída
2. Entender o que ele precisa (orçamento, quantos dias, só internet ou voz+internet)
3. Recomendar o melhor pacote
4. Conduzir a conversa até à venda
5. Pedir o número Vodacom onde quer carregar
6. Pedir o comprovativo de pagamento

TOM DE VOZ:
- Descontraído, amigável e próximo (usa "tu")
- Linguagem simples, como se estivesses a falar com um amigo
- Um pouco de humor leve quando fizer sentido
- Nunca sejas robótico ou formal demais
- Sempre positivo e confiante

REGRAS IMPORTANTES:
- Nunca inventes preços ou pacotes. Usa apenas os dados abaixo.
- Se o cliente pedir algo que não tens, diz a verdade e oferece a melhor alternativa.
- Quando o cliente escolher um pacote, pede o número Vodacom a carregar.
- Depois de ter o número, mostra o resumo + métodos de pagamento e pede o comprovativo.
- Se o cliente enviar comprovativo ou disser que já pagou, confirma que recebeste e que vais activar.

CATÁLOGO ACTUAL:
{PRODUTOS_TEXTO}

Responde sempre em português de Moçambique, de forma natural e curta (WhatsApp).
"""

    messages = [{"role": "system", "content": system_prompt}] + historico[numero]

    try:
        resposta = client.chat.completions.create(
            model=model="lhama-3.3-70b-versatil",
            messages=messages,
            temperature=0.7,
            max_tokens=450
        )
        texto_resposta = resposta.choices[0].message.content.strip()
        
        # Guarda a resposta da IA no histórico
        historico[numero].append({"role": "assistant", "content": texto_resposta})
        
        return texto_resposta
    except Exception as e:
        print(f"Erro Groq: {e}")
        return "Desculpa, estou com uma pequena instabilidade agora. Podes repetir a mensagem? 🙏"


def processar_mensagem(numero: str, texto: str) -> str:
    texto_limpo = texto.strip().lower()

    # Comandos especiais
    if texto_limpo in ["menu", "início", "inicio", "recomeçar", "reset"]:
        limpar_conversa(numero)
        return "Olá! 👋 Bem-vindo à *DB Multi-Service*.\n\nEm que posso ajudar-te hoje? Queres ver as ofertas de internet, pacotes com voz, ou já sabes o que precisas?"

    # Detecção simples de comprovativo
    palavras_comprovativo = ["comprovativo", "paguei", "já paguei", "transferi", "mpesa", "e-mola", "emola", "enviei o dinheiro"]
    if any(p in texto_limpo for p in palavras_comprovativo) or len(texto) > 30:
        # Provável comprovativo → notifica admin
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        msg_admin = (
            f"🔔 *NOVO COMPROVATIVO / POSSÍVEL PAGAMENTO*\n\n"
            f"Cliente: {numero}\n"
            f"Hora: {agora}\n\n"
            f"Mensagem:\n{texto}"
        )
        notificar_admins(msg_admin)

    # Chama a IA
    return chamar_groq(numero, texto)


# ==================== WEBHOOK ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    
    msg_data = data.get("data", {})
    tipo_evento = data.get("event_type", "")

    if tipo_evento == "message_received" and not msg_data.get("fromMe", False):
        numero = msg_data.get("from", "")
        texto_recebido = msg_data.get("body", "") or ""

        if texto_recebido:
            resposta = processar_mensagem(numero, texto_recebido)
            enviar_mensagem(numero, resposta)

    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"])
def home():
    return "Bot DB Multi-Service v3.0 (Groq AI) está a funcionar! ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
