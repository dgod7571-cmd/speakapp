import flet as ft
import requests
import threading
import time
import re

SERVER_URL = "http://192.168.0.105:8000"

def main(page: ft.Page):
    page.title = "CRM Пульт"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 400
    page.window_height = 800

    current_chat_name = None
    last_history = ""
    last_server_draft = ""
    last_chats_data = None 

    def sync_settings(e):
        try:
            requests.post(f"{SERVER_URL}/settings", json={
                "sweeper_on": sw_sweeper.value,
                "autopilot_on": sw_autopilot.value
            })
        except: pass

    sw_sweeper = ft.Switch(label="1 - Свипер (Собрать черновики)", on_change=sync_settings)
    sw_autopilot = ft.Switch(label="2 - Автопилот (Отправлять)", on_change=sync_settings)
    chats_list = ft.ListView(expand=1, spacing=10, padding=10, auto_scroll=False)

    def force_main_refresh(e):
        nonlocal last_chats_data
        last_chats_data = None 
        chats_list.controls.clear()
        chats_list.controls.append(ft.Text("🔄 Поиск чатов...", color="grey"))
        page.update()

    # --- ОВЕРЛЕЙ ЗАМЫЛИВАНИЯ И ПРОГРЕССА ---
    # --- ОВЕРЛЕЙ ЗАМЫЛИВАНИЯ И ПРОГРЕССА ---
    cache_progress_text = ft.Text("0 / 0", size=16, color="white", text_align=ft.TextAlign.CENTER)
    
    # --- ОВЕРЛЕЙ ЗАМЫЛИВАНИЯ И ПРОГРЕССА ---
    cache_progress_text = ft.Text("0 / 0", size=16, color="white", text_align=ft.TextAlign.CENTER)
    
    blur_overlay = ft.Container(
        content=ft.Column([
            ft.ProgressRing(color="white"),
            ft.Text("Сбор чатов в кэш...", size=18, weight=ft.FontWeight.BOLD, color="white"),
            cache_progress_text
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="black54", # Заменили прозрачный цвет на встроенный текстовый!
        blur=ft.Blur(15, 15, ft.BlurTileMode.MIRROR),
        expand=True,
        visible=False
    )

    def start_caching(e):
        blur_overlay.visible = True
        page.update()
        requests.post(f"{SERVER_URL}/cache_all")
        
        def check_progress():
            time.sleep(1.0) 
            while True:
                try:
                    res = requests.get(f"{SERVER_URL}/cache_progress").json()
                    if res["active"]:
                        cache_progress_text.value = f"{res['current']} / {res['total']}\n{res['current_name']}"
                        page.update()
                    elif not res["active"]:
                        blur_overlay.visible = False
                        page.update()
                        break
                except: pass
                time.sleep(0.5)
                
        threading.Thread(target=check_progress, daemon=True).start()

    # Две кнопки в ряд
    btn_refresh_main = ft.TextButton("🔄 Обновить", on_click=force_main_refresh)
    btn_download_all = ft.TextButton("📥 Скачать все", on_click=start_caching)

    main_view = ft.Column([
        ft.Row([
            ft.Text("Активные диалоги", size=22, weight=ft.FontWeight.BOLD),
            ft.Row([btn_download_all, btn_refresh_main])
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        sw_sweeper,
        sw_autopilot,
        ft.Divider(color="grey800"),
        ft.Container(content=chats_list, expand=True)
    ], expand=True, visible=True)

    chat_title = ft.Text("💬 Чат", size=18, weight=ft.FontWeight.BOLD)
    status_label = ft.Text("Ожидание...", size=13, color="grey")
    chat_history_list = ft.ListView(expand=True, spacing=10, padding=10, auto_scroll=True)
    
    draft_label = ft.Text("Черновик от ИИ:", size=14, color="#F39C12", weight=ft.FontWeight.BOLD)
    draft_input = ft.TextField(multiline=True, min_lines=3, max_lines=4, border_color="#F39C12")
    
    def on_regen(e):
        status_label.value = "🔄 ИИ думает над новым ответом..."
        draft_input.value = ""
        page.update()
        requests.post(f"{SERVER_URL}/action", json={"action": "regen", "chat_name": current_chat_name})

    def on_send(e):
        text_to_send = draft_input.value
        if not text_to_send.strip(): return
        
        status_label.value = "⏳ Запуск отправки..."
        draft_input.value = ""
        page.update()
        requests.post(f"{SERVER_URL}/action", json={"action": "send", "chat_name": current_chat_name, "text": text_to_send})

    btn_regen = ft.ElevatedButton("🔄 Перегенерировать", color="orange", on_click=on_regen)
    btn_send = ft.ElevatedButton("✅ Отправить", bgcolor="#2FA572", color="white", on_click=on_send)
    
    def close_chat(e):
        nonlocal current_chat_name, last_history
        current_chat_name = None
        last_history = ""
        chat_view.visible = False
        main_view.visible = True
        page.update()

    btn_back = ft.TextButton("← Назад", on_click=close_chat)
    
    def force_chat_refresh(e):
        nonlocal last_history
        last_history = "" 
        status_label.value = "🔄 Принудительное обновление..."
        chat_history_list.controls.clear()
        chat_history_list.controls.append(ft.Text("Загрузка истории из CRM...", color="grey"))
        page.update()
        requests.post(f"{SERVER_URL}/open_chat", json={"name": current_chat_name})

    btn_refresh_chat = ft.TextButton("🔄", on_click=force_chat_refresh)
    
    chat_view = ft.Column([
        ft.Row([
            ft.Row([btn_back, chat_title]),
            btn_refresh_chat
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        status_label,
        ft.Divider(color="grey800"),
        ft.Container(content=chat_history_list, expand=True),
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

    def poll_server():
        nonlocal last_history, last_server_draft, last_chats_data
        while True:
            try:
                if main_view.visible:
                    res = requests.get(f"{SERVER_URL}/status", timeout=2).json()
                    sw_sweeper.value = res["state"]["sweeper_on"]
                    sw_autopilot.value = res["state"]["autopilot_on"]
                    
                    current_chats = res["chats"]
                    
                    if current_chats != last_chats_data:
                        last_chats_data = current_chats
                        chats_list.controls.clear()
                        
                        for chat in current_chats:
                            name, unread, status = chat["name"], chat["unread"], chat["status"]
                            bg_col = "#263238" 
                            badge = ""
                            
                            if status == "ignored":
                                bg_col = "#34495E"
                                badge = "   🤖 Игнор"
                            elif status == "voice":
                                bg_col = "#4A148C"
                                badge = "   🎤 Голос"
                            elif status == "stop":
                                bg_col = "#C0392B"
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

                elif chat_view.visible and current_chat_name:
                    data = requests.get(f"{SERVER_URL}/chat_data", timeout=2).json()
                    
                    if "ИИ думает" not in status_label.value and "Запуск отправки" not in status_label.value:
                        status_label.value = data["status_msg"]
                    elif data["status_msg"] != "Готов к работе": 
                        status_label.value = data["status_msg"]
                    
                    server_draft = data["draft"]
                    if server_draft and server_draft != last_server_draft and server_draft != "WAITING":
                        draft_input.value = server_draft
                        last_server_draft = server_draft
                    elif server_draft == "WAITING":
                        draft_input.value = ""
                        last_server_draft = "WAITING"

                    history_text = data["history"]
                    if history_text and history_text != last_history:
                        last_history = history_text
                        
                        new_bubbles = []
                        try:
                            messages = re.split(r'(?=\[(?:Вы|Клиент)\]:)', history_text.strip())
                            for msg in messages:
                                msg = msg.strip()
                                if not msg: continue
                                
                                if not (msg.startswith('[Вы]:') or msg.startswith('[Клиент]:')):
                                    continue
                                
                                is_out = msg.startswith('[Вы]:')
                                clean_msg = msg.replace('[Вы]:', '').replace('[Клиент]:', '').strip()
                                if not clean_msg: continue
                                
                                bubble_width = 300 if len(clean_msg) > 35 else None

                                bubble = ft.Container(
                                    content=ft.Text(clean_msg, size=15, color="white", selectable=True),
                                    bgcolor="#2B5278" if is_out else "#222D36",
                                    padding=12,
                                    border_radius=10,
                                    width=bubble_width 
                                )
                                
                                row = ft.Row([bubble], alignment=ft.MainAxisAlignment.END if is_out else ft.MainAxisAlignment.START)
                                new_bubbles.append(row)
                                
                            chat_history_list.controls = new_bubbles
                                
                        except Exception as e:
                            chat_history_list.controls = [ft.Text(f"❌ Ошибка рендера: {str(e)}", color="red")]
                            
                    page.update()
            except: pass
            
            # УСКОРЕННЫЙ ОПРОС: ловим каждую секунду таймера без зависаний
            time.sleep(0.4)

    threading.Thread(target=poll_server, daemon=True).start()
    
    # Добавили blur_overlay поверх всего
    page.add(ft.SafeArea(ft.Stack([main_view, chat_view, blur_overlay], expand=True), expand=True))
    page.update()

if __name__ == "__main__":
    ft.app(target=main)
