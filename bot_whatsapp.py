"""
Bot de WhatsApp - DB Multi-Service (Versão 2.0 - com estados e fluxo de venda)
-------------------------------------------------------------------------------
Usa Ultramsg + Flask
"""

from flask import Flask, request, jsonify
import requests
from datetime import datetime
from collections import defaultdict

app = Flask(__name__)

# ==================== CONFIGURAÇÃO ====================
INSTANCE_ID = "instance186644"          # ← Coloca o teu
TOKEN = "e9gysv7lg3n1ctsp"                      # ← Coloca o teu
API_URL = f"https://api.ultramsg.com/{INSTANCE_ID}/messages/chat"

# Números do administrador (recebem notificação de comprovativos)
# Formato internacional sem o sinal + (ex: 258846818458)
ADMIN_NUMBERS = [
    "258846818458",   # M-Pesa
    "258876063563",   # E-Mola
]

# ==================== CATÁLOGO DE PRODUTOS ====================
# Fácil de editar / acrescentar novos produtos no futuro

PRODUTOS = {
    "especiais": {
        "nome": "Ofertas Especiais (Voz + SMS + Internet)",
        "itens": {
            "1": {"nome": "7 Dias – 275 MT", "preco": 275, "descricao": "7.680 MB + 5 Min Internacionais + 25 MB Roaming"},
            "2": {"nome": "30 Dias – 468 MT", "preco": 468, "descricao": "10.138 MB + 10 Min Internacionais + 30 MB Roaming"},
            "3": {"nome": "30 Dias – 925 MT", "preco": 925, "descricao": "20.787 MB + 20 Min Internacionais + 80 MB Roaming"},
            "4": {"nome": "30 Dias – 1.400 MT", "preco": 1400, "descricao": "31.744 MB + 30 Min Internacionais + 150 MB Roaming"},
            "5": {"nome": "30 Dias – 2.800 MT", "preco": 2800, "descricao": "64.819 MB + 40 Min Internacionais + 700 MB Roaming"},
        }
    },
    "internet": {
        "nome": "Ofertas só de Internet",
        "itens": {
            "1": {"nome": "WTF 7 Dias", "preco": 50, "descricao": "50 MT"},
            "2": {"nome": "8.909 MB – 30 Dias", "preco": 280, "descricao": "280 MT"},
            "3": {"nome": "16.589 MB – 30 Dias", "preco": 475, "descricao": "475 MT"},
            "4": {"nome": "33.280 MB – 30 Dias", "preco": 950, "descricao": "950 MT"},
        }
    }
}

# ==================== MENSAGENS ====================
MSG_BOAS_VINDAS = """👋 Olá! Bem-vindo(a) à *DB Multi-Service* 🔴

Qualidade, confiança e os melhores preços num só lugar!

Escolha uma opção digitando o número:

1️⃣ Ver Ofertas Especiais (Voz + SMS + Internet)
2️⃣ Ver Ofertas só de Internet
3️⃣ Métodos de Pagamento
4️⃣ Falar com um atendente

Digite o número da opção 👆"""

MSG_PAGAMENTO = """💳 *MÉTODOS DE PAGAMENTO*

📱 M-Pesa: *846818458*
📱 E-Mola: *876063563*

Após pagar, envie o *comprovativo* aqui mesmo que confirmamos e ativamos rapidamente ✅"""

MSG_ATENDENTE = """🙋 Já vamos ligar-te a um dos nossos atendentes para te ajudar diretamente.
Só um instante, por favor 🙏"""

MSG_NOTA = """⚠️ Nota: para pacotes semanais/mensais, o número não pode ter "txuna" (crédito em dívida)."""

# ==================== ESTADO DAS CONVERSAS ====================
# Guarda o estado de cada cliente (em memória)
# Formato: { "2588xxxxxxx": {"estado": "...", "produto": ..., "numero_carregar": ...} }
estados = defaultdict(dict)

# ==================== FUNÇÕES AUXILIARES ====================

def enviar_mensagem(numero: str, texto: str):
    """Envia mensagem via Ultramsg"""
    payload = {
        "token": TOKEN,
        "to": numero,
        "body": texto,
    }
    try:
        requests.post(API_URL, data=payload, timeout=15)
    except Exception as e:
        print(f"Erro ao enviar mensagem: {e}")


def notificar_admins(mensagem: str):
    """Envia notificação para todos os números de administrador"""
    for admin in ADMIN_NUMBERS:
        enviar_mensagem(admin, mensagem)


def limpar_estado(numero: str):
    """Limpa o estado do cliente"""
    if numero in estados:
        del estados[numero]


def formatar_catalogo(categoria: str) -> str:
    """Gera a mensagem com a lista de produtos de uma categoria"""
    cat = PRODUTOS[categoria]
    texto = f"🎁 *{cat['nome']}*\n\n"
    
    for key, item in cat["itens"].items():
        texto += f"*{key}* - {item['nome']}\n   {item['descricao']}\n\n"
    
    texto += "Para encomendar, digite o *número* do pacote que deseja.\n"
    texto += "Ou digite *menu* para voltar ao início."
    return texto


# ==================== LÓGICA PRINCIPAL ====================

def processar_mensagem(numero: str, texto: str) -> str:
    """Processa a mensagem do cliente de acordo com o estado actual"""
    texto = texto.strip().lower()
    estado_atual = estados[numero].get("estado", "inicio")

    # --- Comandos globais (funcionam em qualquer estado) ---
    if texto in ["menu", "início", "inicio", "voltar", "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite"]:
        limpar_estado(numero)
        return MSG_BOAS_VINDAS

    if texto in ["4", "atendente", "humano", "ajuda", "operador"]:
        limpar_estado(numero)
        return MSG_ATENDENTE

    if texto in ["3", "pagamento", "pagar", "mpesa", "m-pesa", "emola", "e-mola"]:
        return MSG_PAGAMENTO

    # --- Fluxo baseado no estado ---
    if estado_atual == "inicio":
        if texto in ["1", "ofertas especiais", "especiais", "pacotes", "precos", "preços"]:
            estados[numero]["estado"] = "escolhendo_especial"
            return formatar_catalogo("especiais") + "\n\n" + MSG_NOTA
        
        elif texto in ["2", "internet", "dados", "megas", "net"]:
            estados[numero]["estado"] = "escolhendo_internet"
            return formatar_catalogo("internet")
        
        else:
            return MSG_BOAS_VINDAS

    # --- Escolhendo pacote Especial ---
    elif estado_atual == "escolhendo_especial":
        if texto in PRODUTOS["especiais"]["itens"]:
            produto = PRODUTOS["especiais"]["itens"][texto]
            estados[numero]["produto"] = produto
            estados[numero]["categoria"] = "especiais"
            estados[numero]["estado"] = "aguardando_numero"
            return (
                f"✅ Escolheu: *{produto['nome']}*\n"
                f"Preço: *{produto['preco']} MT*\n\n"
                f"Agora envie o *número Vodacom* onde deseja carregar o pacote.\n"
                f"(Exemplo: 84XXXXXXX ou 85XXXXXXX)"
            )
        else:
            return "❌ Opção inválida. Digite o número do pacote (1 a 5) ou *menu* para voltar."

    # --- Escolhendo pacote Internet ---
    elif estado_atual == "escolhendo_internet":
        if texto in PRODUTOS["internet"]["itens"]:
            produto = PRODUTOS["internet"]["itens"][texto]
            estados[numero]["produto"] = produto
            estados[numero]["categoria"] = "internet"
            estados[numero]["estado"] = "aguardando_numero"
            return (
                f"✅ Escolheu: *{produto['nome']}*\n"
                f"Preço: *{produto['preco']} MT*\n\n"
                f"Agora envie o *número Vodacom* onde deseja carregar o pacote.\n"
                f"(Exemplo: 84XXXXXXX ou 85XXXXXXX)"
            )
        else:
            return "❌ Opção inválida. Digite o número do pacote (1 a 4) ou *menu* para voltar."

    # --- Aguardando número a carregar ---
    elif estado_atual == "aguardando_numero":
        # Aceita números com 9 dígitos começados por 8
        numero_limpo = "".join(filter(str.isdigit, texto))
        if len(numero_limpo) == 9 and numero_limpo.startswith("8"):
            estados[numero]["numero_carregar"] = numero_limpo
            estados[numero]["estado"] = "aguardando_pagamento"
            produto = estados[numero]["produto"]
            return (
                f"📋 *Resumo do pedido:*\n\n"
                f"Pacote: *{produto['nome']}*\n"
                f"Valor: *{produto['preco']} MT*\n"
                f"Número a carregar: *{numero_limpo}*\n\n"
                f"{MSG_PAGAMENTO}\n\n"
                f"Depois de pagar, envie o comprovativo aqui."
            )
        else:
            return (
                "❌ Número inválido.\n"
                "Por favor envie um número Vodacom válido com 9 dígitos "
                "(exemplo: 84XXXXXXX)."
            )

    # --- Aguardando comprovativo ---
    elif estado_atual == "aguardando_pagamento":
        # Qualquer mensagem nesta fase é tratada como possível comprovativo
        produto = estados[numero]["produto"]
        num_carregar = estados[numero]["numero_carregar"]
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        # Mensagem para o cliente
        resposta_cliente = (
            "✅ *Comprovativo recebido!*\n\n"
            "Vamos verificar o pagamento e activar o pacote o mais rápido possível.\n"
            "Obrigado pela preferência! 🙏\n\n"
            "Digite *menu* se quiser fazer outro pedido."
        )

        # Notificação para os administradores
        msg_admin = (
            f"🔔 *NOVO COMPROVATIVO RECEBIDO*\n\n"
            f"Cliente: {numero}\n"
            f"Pacote: {produto['nome']}\n"
            f"Valor: {produto['preco']} MT\n"
            f"Número a carregar: {num_carregar}\n"
            f"Hora: {agora}\n\n"
            f"Mensagem do cliente:\n{texto}"
        )
        notificar_admins(msg_admin)

        # Limpa o estado (ou podes manter se quiseres histórico)
        limpar_estado(numero)
        return resposta_cliente

    # Fallback
    return MSG_BOAS_VINDAS


# ==================== WEBHOOK ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True, silent=True) or {}
    
    msg_data = data.get("data", {})
    tipo_evento = data.get("event_type", "")

    if tipo_evento == "message_received" and not msg_data.get("fromMe", False):
        numero = msg_data.get("from", "")
        texto_recebido = msg_data.get("body", "") or ""

        # Processa apenas mensagens de texto
        if texto_recebido:
            resposta = processar_mensagem(numero, texto_recebido)
            enviar_mensagem(numero, resposta)

    return jsonify({"status": "ok"})


@app.route("/", methods=["GET"])
def home():
    return "Bot DB Multi-Service v2.0 está a funcionar! ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
