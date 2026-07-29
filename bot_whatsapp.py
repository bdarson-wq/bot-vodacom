"""
Bot de WhatsApp - DB Multi-Service
-----------------------------------
Responde automaticamente aos clientes com base em palavras-chave,
usando a API da Ultramsg (funciona com o teu WhatsApp normal).

COMO USAR:
1. Cria conta em https://ultramsg.com e uma "Instance".
2. Escaneia o QR Code com o teu WhatsApp (Aparelhos Conectados).
3. Copia o "Instance ID" e o "Token" do painel da Ultramsg e cola abaixo,
   nas variáveis INSTANCE_ID e TOKEN.
4. Publica este ficheiro num serviço gratuito como Render.com ou Railway.app
   (procura por "deploy Flask app Render" se tiveres dúvidas).
5. No painel da Ultramsg, em "Webhook", cola o link público do teu serviço
   + "/webhook" (ex: https://o-teu-site.onrender.com/webhook).
6. Pronto! Qualquer mensagem recebida no WhatsApp vai passar por este bot.
"""

from flask import Flask, request, jsonify
import requests

app = Flask(_name_)

# ----------- CONFIGURAÇÃO (preencher com os teus dados da Ultramsg) -----------
INSTANCE_ID = "instance186644"
TOKEN = "e9gysv7lg3n1ctsp"
API_URL = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

# ----------- MENSAGENS (baseadas no guião DB Multi-Service) -----------

MSG_BOAS_VINDAS = """👋 Olá! Bem-vindo(a) à DB Multi-Service 🔴
Qualidade, confiança e os melhores preços num só lugar!

Escolha uma opção digitando o número:

1️⃣ Ver Ofertas Especiais (Voz + SMS + Internet)
2️⃣ Ver Ofertas só de Internet
3️⃣ Métodos de Pagamento
4️⃣ Falar com um atendente

Digite o número da opção 👆"""

MSG_OFERTAS_ESPECIAIS = """🎁 OFERTAS ESPECIAIS (válido a partir de 21/07/2026)
✅ Voz e SMS ilimitadas para todas as redes em todos os pacotes

🟢 7 Dias – 275 MT
* 7.680 MB
* 5 Min Internacionais
* 25 MB Roaming

🔵 30 Dias – 468 MT
* 10.138 MB
* 10 Min Internacionais
* 30 MB Roaming

🟠 30 Dias – 925 MT
* 20.787 MB
* 20 Min Internacionais
* 80 MB Roaming

🟣 30 Dias – 1.400 MT
* 31.744 MB
* 30 Min Internacionais
* 150 MB Roaming

🔴 30 Dias – 2.800 MT
* 64.819 MB
* 40 Min Internacionais
* 700 MB Roaming

⚠️ Nota: para pacotes semanais/mensais, o número não pode ter "txuna" (crédito em dívida).

Para encomendar, diga qual pacote quer e o número Vodacom a carregar 📲"""

MSG_OFERTAS_INTERNET = """🌐 OFERTAS DE INTERNET

📶 WTF – 7 Dias ➜ 50 MT
📶 8.909 MB – 30 Dias ➜ 280 MT
📶 16.589 MB – 30 Dias ➜ 475 MT
📶 33.280 MB – 30 Dias ➜ 950 MT

Para encomendar, diga qual pacote quer e o número Vodacom a carregar 📲"""

MSG_PAGAMENTO = """💳 MÉTODOS DE PAGAMENTO

📱 M-Pesa: 846818458
📱 E-Mola: 876063563

Após pagar, envie o comprovativo aqui mesmo que confirmamos e ativamos rapidamente ✅"""

MSG_ATENDENTE = """🙋 Já vamos ligar-te a um dos nossos atendentes para te ajudar diretamente.
Só um instante, por favor 🙏"""

# Palavras-chave -> mensagem de resposta
RESPOSTAS = {
    ("oi", "ola", "olá", "boa tarde", "bom dia", "boa noite", "menu"): MSG_BOAS_VINDAS,
    ("1", "ofertas especiais", "pacotes", "precos", "preços", "tabela"): MSG_OFERTAS_ESPECIAIS,
    ("2", "internet", "dados", "megas", "net"): MSG_OFERTAS_INTERNET,
    ("3", "pagamento", "pagar", "mpesa", "m-pesa", "emola", "e-mola", "conta"): MSG_PAGAMENTO,
    ("4", "atendente", "humano", "ajuda"): MSG_ATENDENTE,
}


def escolher_resposta(texto_recebido: str) -> str:
    """Compara o texto recebido (em minúsculas) com as palavras-chave."""
    texto = texto_recebido.strip().lower()
    for palavras_chave, resposta in RESPOSTAS.items():
        if texto in palavras_chave:
            return resposta
    # Se não reconhecer nada, cai no atendimento humano
    return MSG_ATENDENTE


def enviar_mensagem(numero: str, texto: str):
    """Envia uma mensagem de volta pelo WhatsApp via Ultramsg."""
    payload = {
        "token": TOKEN,
        "to": numero,
        "body": texto,
    }
    requests.post(API_URL, data=payload, timeout=15)


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}

    # A Ultramsg envia os dados dentro de "data" quando é mensagem recebida
    msg_data = data.get("data", {})
    tipo_evento = data.get("event_type", "")

    # Só processar mensagens recebidas de texto (ignorar mensagens enviadas por nós mesmos)
    if tipo_evento == "message_received" and not msg_data.get("fromMe", False):
        numero = msg_data.get("from", "")
        texto_recebido = msg_data.get("body", "")

        resposta = escolher_resposta(texto_recebido)
        enviar_mensagem(numero, resposta)

    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"])
def home():
    return "Bot DB Multi-Service está a funcionar! ✅"


if _name_ == "_main_":
    app.run(host="0.0.0.0", port=5000)
