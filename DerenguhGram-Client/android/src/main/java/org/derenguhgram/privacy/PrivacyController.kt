// Privacy-mode switches for DerenguhGram (Android). SPDX: GPL-3.0-only
//
// These suppress YOUR OWN activity signals only. Hook the gates into the exact
// Telegram call sites listed in docs/PRIVACY_MODES.md:
//   * Невидимка  -> ConnectionsManager / MessagesController online updates
//   * Нечиталка  -> MessagesController.markDialogAsRead / markMessageAsRead
//   * Неписалка  -> MessagesController.sendTyping / SendMessagesHelper typing
package org.derenguhgram.privacy

import android.content.Context

object PrivacyController {
    private const val PREFS = "derenguh_privacy"
    private const val KEY_INVISIBLE = "invisible"
    private const val KEY_NO_READ = "no_read"
    private const val KEY_NO_TYPING = "no_typing"

    @Volatile var invisible: Boolean = false
        private set
    @Volatile var noReadReceipts: Boolean = false
        private set
    @Volatile var noTyping: Boolean = false
        private set

    fun init(context: Context) {
        val p = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        invisible = p.getBoolean(KEY_INVISIBLE, false)
        noReadReceipts = p.getBoolean(KEY_NO_READ, false)
        noTyping = p.getBoolean(KEY_NO_TYPING, false)
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun setInvisible(context: Context, v: Boolean) {
        invisible = v; prefs(context).edit().putBoolean(KEY_INVISIBLE, v).apply()
    }

    fun setNoReadReceipts(context: Context, v: Boolean) {
        noReadReceipts = v; prefs(context).edit().putBoolean(KEY_NO_READ, v).apply()
    }

    fun setNoTyping(context: Context, v: Boolean) {
        noTyping = v; prefs(context).edit().putBoolean(KEY_NO_TYPING, v).apply()
    }

    // Gates used at the call sites.
    fun shouldSendOnlineUpdate(): Boolean = !invisible
    fun shouldSendReadReceipt(): Boolean = !noReadReceipts
    fun shouldSendTyping(): Boolean = !noTyping
}
