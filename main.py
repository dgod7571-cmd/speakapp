import flet as ft
import requests
import threading
import time
import re

# Замени на локальный IP компьютера в сети (узнать через ipconfig)
SERVER_URL = "http://127.0.0.1:8000"

def main(page: ft.Page):
    page.title = "CRM Пульт"
    page.theme_mode = ft.ThemeMode.DARK
    page.window.width = 400
    page.window.height = 800

    current_chat_name = None
    last_history = ""
    last_server_draft = ""

    def sync_settings(e):
        try:
            requests.post(f"{SERVER_URL}/settings", json={
                "sweeper_on": sw_sweeper.value,
                "autopilot_on": sw_autopilot.value
            })
        except: pass

    # --- ГЛАВНЫЙ ЭКРАН ---
    sw_sweeper = ft.Switch(label="1 - Свипер (Собрать черновики)", on_change=sync_settings)
    sw_autopilot = ft.Switch(label="2 - Автопилот (Отправлять)", on_change=sync_settings)
    chats_list = ft.ListView(expand=1, spacing=10, padding=10, auto_scroll=False)

    main_view = ft.Column([
        ft.Text("Активные диалоги (ПК)", size=22, weight=ft.FontWeight.BOLD),
        sw_sweeper,
        sw_autopilot,
        ft.Divider(color="grey800"),
        chats_list
    ], expand=True, visible=True)

    # --- ЭКРАН ЧАТА ---
    chat_title = ft.Text("💬 Чат", size=18, weight=ft.FontWeight.BOLD)
    status_label = ft.Text("Ожидание...", size=13, color="grey")
    chat_history_list = ft.ListView(expand=True, spacing=10, padding=10, auto_scroll=True)
    
    draft_label = ft.Text("Черновик от ИИ:", size=14, color="#F39C12", weight=ft.FontWeight.BOLD)
    draft_input = ft.TextField(multiline=True, min_lines=4, max_lines=6, border_color="#F39C12")
    
    def on_regen(e):
        requests.post(f"{SERVER_URL}/action", json={"action": "regen", "chat_name": current_chat_name})
        draft_input.value = ""
        page.update()

    def on_send(e):
        requests.post(f"{SERVER_URL}/action", json={"action": "send", "chat_name": current_chat_name, "text": draft_input.value})
        draft_input.value = ""
        page.update()

    btn_regen = ft.ElevatedButton("🔄 Перегенерировать", style=ft.ButtonStyle(color="orange"), on_click=on_regen)
    btn_send = ft.ElevatedButton("✅ Отправить", style=ft.ButtonStyle(bgcolor="#2FA572", color="white"), on_click=on_send)
    
    def close_chat(e):
        nonlocal current_chat_name, last_history
        current_chat_name = None
        last_history = ""
        chat_view.visible = False
        main_view.visible = True
        page.update()

    btn_back = ft.TextButton("← Назад", on_click=close_chat)
    
    chat_view = ft.Column([
        ft.Row([btn_back, chat_title], alignment=ft.MainAxisAlignment.START),
        status_label,
        ft.Divider(color="grey800"),
        chat_history_list,
        ft.Divider(color="grey800"),
        draft_label,
        draft_input,
        ft.Row([btn_regen, btn_send], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    ], expand=True, visible=False)

    def open_chat(e):
        nonlocal current_chat_name, last_history, last_server_draft
        current_chat_name = e.control.data
        chat_title.value = f"💬 {current_chat_name}"
        
        chat_history_list.controls.clear()
        chat_history_list.controls.append(ft.Text("Загрузка истории из CRM...", color="grey"))
        last_history = ""
        last_server_draft = ""
        draft_input.value = ""
        
        requests.post(f"{SERVER_URL}/open_chat", json={"name": current_chat_name})
        
        main_view.visible = False
        chat_view.visible = True
        page.update()

    # --- ЖИВОЙ ПОЛЛИНГ СЕРВЕРА ---
    def poll_server():
        nonlocal last_history, last_server_draft
        while True:
            try:
                # 1. ОБНОВЛЕНИЕ ГЛАВНОГО МЕНЮ
                if main_view.visible:
                    res = requests.get(f"{SERVER_URL}/status", timeout=2).json()
                    sw_sweeper.value = res["state"]["sweeper_on"]
                    sw_autopilot.value = res["state"]["autopilot_on"]
                    
                    chats_list.controls.clear()
                    for chat in res["chats"]:
                        name, unread, status = chat["name"], chat["unread"], chat["status"]
                        bg_col = "#263238"
                        badge = ""
                        
                        if status == "ignored":
                            bg_col = "#34495E"
                            badge = "   🤖 Игнор"
                        elif status == "voice":
                            bg_col = "#4A148C" # ФИОЛЕТОВЫЙ для голосовых
                            badge = "   🎤 Голос"
                        elif status == "stop":
                            bg_col = "#C0392B" # КРАСНЫЙ для отказов
                            badge = "   🛑 Внимание"
                        elif status == "ready":
                            bg_col = "#1B5E20"
                            badge = "   ✅ Готов"
                        elif status == "waiting":
                            badge = "   ⏳ Ждем"
                            
                        if unread > 0: badge += f"   🔴 ({unread})"
                            
                        btn = ft.Container(
                            content=ft.Text(f"💬 {name}{badge}", size=15),
                            bgcolor=bg_col, padding=15, border_radius=10, data=name, on_click=open_chat
                        )
                        chats_list.controls.append(btn)
                    page.update()

                # 2. ЖИВОЕ ОБНОВЛЕНИЕ ЧАТА
                elif chat_view.visible and current_chat_name:
                    data = requests.get(f"{SERVER_URL}/chat_data", timeout=2).json()
                    status_label.value = data["status_msg"]
                    
                    # Если текст черновика от сервера изменился, обновляем поле
                    # (Но не затираем то, что ты редактируешь, если сервер спит)
                    server_draft = data["draft"]
                    if server_draft and server_draft != last_server_draft and server_draft != "WAITING":
                        draft_input.value = server_draft
                        last_server_draft = server_draft
                    elif server_draft == "WAITING":
                        draft_input.value = ""
                        last_server_draft = "WAITING"

                    # Отрисовка пузырей истории (только если она обновилась)
                    history_text = data["history"]
                    if history_text and history_text != last_history:
                        last_history = history_text
                        chat_history_list.controls.clear()
                        
                        messages = re.split(r'(?=\[(?:Вы|Клиент)\]:)', history_text.strip())
                        for msg in messages:
                            msg = msg.strip()
                            if not msg: continue
                            is_out = msg.startswith('[Вы]:')
                            clean_msg = msg.replace('[Вы]:', '', 1).replace('[Клиент]:', '', 1).strip()
                            
                            bubble = ft.Container(
                                content=ft.Text(clean_msg, size=14, color="white"),
                                bgcolor="#2B5278" if is_out else "#1E3B57",
                                padding=10,
                                border_radius=10,
                                alignment=ft.alignment.center_right if is_out else ft.alignment.center_left,
                                margin=ft.margin.only(left=50 if is_out else 0, right=0 if is_out else 50)
                            )
                            chat_history_list.controls.append(bubble)
                    page.update()
            except:
                pass
            time.sleep(1.0) # Частота живого обновления - 1 секунда

    threading.Thread(target=poll_server, daemon=True).start()

    page.add(ft.SafeArea(ft.Stack([main_view, chat_view], expand=True)))
    page.update()

ft.app(target=main)