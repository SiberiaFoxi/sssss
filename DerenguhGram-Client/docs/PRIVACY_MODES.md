# Режимы приватности — точки внедрения

Три режима подавляют **ваши собственные** сигналы активности. Они не затрагивают
чужой защищённый контент. Всюду вставляется один гейт перед отправкой пакета.

| Режим | Что подавляется | Гейт |
|---|---|---|
| Невидимка | online-статус / `account.updateStatus(offline=false)` | `shouldSendOnlineUpdate()` |
| Нечиталка | read receipts (`messages.readHistory`, `channels.readHistory`, read-mark) | `shouldSendReadReceipt()` |
| Неписалка | `messages.setTyping` | `shouldSendTyping()` |

> Важно: «Невидимка» на уровне клиента лишь не шлёт явные online-апдейты. Сервер всё
> равно может считать вас онлайн, пока активно TCP-соединение. Это ограничение любого
> клиентского ghost-режима, а не недочёт мода.

---

## Desktop (tdesktop)

Гейты: `derenguh::PrivacySettings::instance()`.

Найдите места отправки:
```bash
grep -rn "updateStatus\|UpdateStatus" Telegram/SourceFiles/main
grep -rn "readHistory\|ReadHistory\|markRead\|readOutbox" Telegram/SourceFiles
grep -rn "setTyping\|SetTyping\|SendTyping\|sendTyping" Telegram/SourceFiles
```

Вставьте гейты (иллюстративно):
```cpp
// online: main_session.cpp, Session::updateOnline / sendUpdateStatus
if (!derenguh::PrivacySettings::instance().shouldSendOnlineUpdate()) return;

// read receipts: api/api_messages.cpp / History::markRead path
if (!derenguh::PrivacySettings::instance().shouldSendReadReceipt()) return;

// typing: api/api_sending.cpp, Api typing helper
if (!derenguh::PrivacySettings::instance().shouldSendTyping()) return;
```

UI-переключатели — в настройках приватности; каждый вызывает соответствующий
`setInvisible / setNoReadReceipts / setNoTyping`.

---

## Android (DrKLO / Hook-droid)

Гейты: `org.derenguhgram.privacy.PrivacyController`.

Найдите места отправки:
```bash
grep -rn "TL_account_updateStatus\|updateStatus" TMessagesProj/src/main/java
grep -rn "markDialogAsRead\|markMessageAsRead\|TL_messages_readHistory\|TL_channels_readHistory" TMessagesProj/src/main/java
grep -rn "TL_messages_setTyping\|sendTyping" TMessagesProj/src/main/java
```

Вставьте гейты (иллюстративно):
```java
// MessagesController: перед отправкой TL_account_updateStatus(offline=false)
if (!PrivacyController.INSTANCE.shouldSendOnlineUpdate()) return;

// MessagesController.markDialogAsRead / markMessageAsRead: перед read-запросом
if (!PrivacyController.INSTANCE.shouldSendReadReceipt()) return;

// перед отправкой TL_messages_setTyping
if (!PrivacyController.INSTANCE.shouldSendTyping()) return;
```

В Kotlin-файлах обращайтесь как `PrivacyController.shouldSendTyping()` (object).
UI-переключатели сохраняются в `SharedPreferences` через сеттеры контроллера.

---

## Проверка

1. Включите режим, откройте чат с тестового аккаунта-наблюдателя.
2. «Неписалка»: печатайте — наблюдатель не видит «печатает…».
3. «Нечиталка»: прочитайте сообщение — у отправителя не появляется вторая галочка.
4. «Невидимка»: наблюдатель не видит ваш online (с оговоркой выше).
