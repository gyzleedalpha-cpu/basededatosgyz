#!/usr/bin/env python3
"""
Seguimiento 2 Semanas - Recordatorios automáticos a Telegram
Corre cada mañana a las 9 AM via launchd
Obtiene clientes de Firebase y envía recordatorios
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────

FIREBASE_URL = "https://vip-database-680d9-default-rtdb.firebaseio.com"
TELEGRAM_BOT_TOKEN = "8754213037:AAG_Slz_ae-A53LUcLMDRahdvTkBw57gj9o"
TELEGRAM_CHANNEL_ID = "-1003813391011"   # formato -100 + ID para canales
TELEGRAM_CHANNEL_URL = "https://t.me/+XXTTOG6UOzRiODBh"

LOG_PATH = Path(os.path.expanduser("~/Desktop/code/reportes/seguimiento.log"))

# ────────────────────────────────────────────────────────────────
# FUNCIONES UTILITARIAS
# ────────────────────────────────────────────────────────────────

def log_msg(msg):
    """Registra mensaje en log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    try:
        with open(LOG_PATH, 'a') as f:
            f.write(full_msg + '\n')
    except:
        pass

def fetch_firebase(path):
    """Obtiene datos de Firebase REST API"""
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return data if data else {}
        return {}
    except Exception as e:
        log_msg(f"ERROR fetching {path}: {e}")
        return {}

def parse_date(date_str):
    """Parsea fecha DD/MM/YY a datetime"""
    if not date_str or date_str == "Permanente":
        return None
    try:
        parts = date_str.split('/')
        if len(parts) != 3:
            return None
        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        year_full = 2000 + year if year < 100 else year
        return datetime(year_full, month, day)
    except:
        return None

def days_until(date_obj):
    """Calcula días hasta una fecha"""
    if not date_obj:
        return None
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    delta = (date_obj - today).days
    return delta

def send_telegram(text):
    """Envía mensaje a Telegram canal"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            log_msg(f"Telegram mensaje enviado")
            return True
        else:
            log_msg(f"Telegram error: {resp.status_code}")
            return False
    except Exception as e:
        log_msg(f"ERROR sending telegram: {e}")
        return False

# ────────────────────────────────────────────────────────────────
# LÓGICA PRINCIPAL
# ────────────────────────────────────────────────────────────────

def analyze_clientes():
    """Analiza clientes de 2 semanas y determina quiénes vencen"""
    log_msg("━━━ Iniciando análisis de seguimiento 2 semanas ━━━")

    # Obtiene datos de Firebase
    clientes = fetch_firebase("clientes_2semanas")

    if not clientes:
        log_msg("No hay datos de clientes_2semanas en Firebase aún — es normal si no hay clientes agregados todavía")
        return {
            'vencen_hoy': [], 'vencen_manana': [], 'pronto': [],
            'activos': [], 'vencidos': [], 'convertidos': []
        }

    # Convierte de diccionario (si viene como {key: {...}}) a lista
    if isinstance(clientes, dict) and len(clientes) > 0 and not isinstance(next(iter(clientes.values())), list):
        # Es un diccionario de objetos
        clientes_list = list(clientes.values())
    else:
        clientes_list = clientes if isinstance(clientes, list) else []

    log_msg(f"Total clientes 2 semanas: {len(clientes_list)}")

    # Analiza por estado
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    manana = hoy + timedelta(days=1)

    vencen_hoy = []
    vencen_manana = []
    pronto = []  # próximos 7 días
    activos = []
    vencidos = []
    convertidos = []

    for cliente in clientes_list:
        try:
            nombre = cliente.get('nombre', 'Sin nombre')
            grupo = cliente.get('grupo', 'Desconocido')
            estado = cliente.get('estado', 'ACTIVO')
            fecha_vencimiento = cliente.get('fecha_vencimiento', '')

            if estado == 'CONVERTIDO':
                convertidos.append(cliente)
                continue

            if estado == 'VENCIDO':
                vencidos.append(cliente)
                continue

            venc_date = parse_date(fecha_vencimiento)
            if not venc_date:
                continue

            dias = days_until(venc_date)

            if dias == 0:
                vencen_hoy.append({**cliente, 'dias': dias})
            elif dias == 1:
                vencen_manana.append({**cliente, 'dias': dias})
            elif 2 <= dias <= 7:
                pronto.append({**cliente, 'dias': dias})
            elif dias > 7:
                activos.append({**cliente, 'dias': dias})
            elif dias < 0:
                vencidos.append(cliente)
        except Exception as e:
            log_msg(f"Error procesando cliente: {e}")
            continue

    # Log summary
    log_msg(f"✓ Vencen hoy: {len(vencen_hoy)}")
    log_msg(f"✓ Vencen mañana: {len(vencen_manana)}")
    log_msg(f"✓ Próximos 7 días: {len(pronto)}")
    log_msg(f"✓ Activos: {len(activos)}")
    log_msg(f"✓ Vencidos: {len(vencidos)}")
    log_msg(f"✓ Convertidos: {len(convertidos)}")

    return {
        'vencen_hoy': vencen_hoy,
        'vencen_manana': vencen_manana,
        'pronto': pronto,
        'activos': activos,
        'vencidos': vencidos,
        'convertidos': convertidos
    }

def build_mensaje(data):
    """Construye mensaje para Telegram"""
    vencen_hoy = data['vencen_hoy']
    vencen_manana = data['vencen_manana']
    convertidos = data['convertidos']
    total = len(vencen_hoy) + len(vencen_manana) + data['activos'] + data['vencidos']

    msg = "<b>🔔 RECORDATORIO - CLIENTES 2 SEMANAS</b>\n"
    msg += f"<i>{datetime.now().strftime('%d/%m/%Y %H:%M')}</i>\n\n"

    if vencen_hoy:
        msg += f"<b>⏰ VENCEN HOY ({len(vencen_hoy)}):</b>\n"
        for c in vencen_hoy:
            msg += f"• <code>{c['nombre']}</code> ({c['grupo']}) — {c.get('fecha_compra', '?')}\n"
        msg += "\n"

    if vencen_manana:
        msg += f"<b>⏰ VENCEN MAÑANA ({len(vencen_manana)}):</b>\n"
        for c in vencen_manana:
            msg += f"• <code>{c['nombre']}</code> ({c['grupo']}) — {c.get('fecha_compra', '?')}\n"
        msg += "\n"

    msg += f"<b>📊 RESUMEN:</b>\n"
    msg += f"• Activos: {len(data['activos'])}\n"
    msg += f"• Por vencer (hoy/mañana): {len(vencen_hoy) + len(vencen_manana)}\n"
    msg += f"• Convertidos a permanente: {len(convertidos)}\n"
    msg += f"• Vencidos: {len(data['vencidos'])}\n"
    msg += f"• <b>Total: {total}</b>\n\n"

    msg += "👉 <b>Acción:</b> Haz follow-up a los que vencen hoy/mañana"

    return msg

def main():
    log_msg("=" * 70)
    log_msg("SEGUIMIENTO 2 SEMANAS - Ejecución iniciada")
    log_msg("=" * 70)

    # Analiza clientes
    data = analyze_clientes()

    # Si hay clientes que vencen hoy/mañana, envía mensaje
    if data['vencen_hoy'] or data['vencen_manana']:
        mensaje = build_mensaje(data)
        log_msg(f"Enviando recordatorio a Telegram...")
        send_telegram(mensaje)
    else:
        log_msg("No hay clientes venciendo hoy/mañana — no se envía recordatorio")

    log_msg("=" * 70)
    log_msg("Ejecución completada")
    log_msg("=" * 70)

if __name__ == '__main__':
    main()
