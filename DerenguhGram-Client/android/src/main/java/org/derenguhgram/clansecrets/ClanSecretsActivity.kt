// ClanSecrets Activity (Android). SPDX: GPL-3.0-only
//
// Diagnostics + own-data window: logs, cache path, an export folder for content the
// user may keep. It deliberately does NOT capture other people's self-destructing /
// view-once media (that defeats the sender's enabled protection). Instead it offers a
// consent-respecting "request a permanent copy" action.
package org.derenguhgram.clansecrets

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class ClanSecretsActivity : Activity() {
    private lateinit var logView: TextView
    private lateinit var proxyStatus: TextView
    private val logBuffer = StringBuilder()
    private val timeFmt = SimpleDateFormat("HH:mm:ss", Locale.getDefault())

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "ClanSecrets"

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }

        root.addView(TextView(this).apply {
            text = "Версия: DerenguhGram 1.0.0"
            textSize = 14f
        })
        proxyStatus = TextView(this).apply { text = "Прокси: не подключён"; textSize = 14f }
        root.addView(proxyStatus)

        root.addView(TextView(this).apply { text = "\nЛоги клиента:"; textSize = 16f })
        logView = TextView(this).apply { textSize = 12f }
        val scroll = ScrollView(this).apply {
            addView(logView)
            layoutParams = LinearLayout.LayoutParams(-1, 0, 1f)
        }
        root.addView(scroll)

        val cacheDir = File(cacheDirParent(), "cache").absolutePath
        root.addView(TextView(this).apply { text = "\nКэш: $cacheDir"; textSize = 12f })
        root.addView(Button(this).apply {
            text = "Открыть папку кэша"
            setOnClickListener { openFolder(cacheDir) }
        })

        val exportDir = File(getExternalFilesDir(null), "ClanSecrets").apply { mkdirs() }
        root.addView(TextView(this).apply {
            text = "\nClanSecrets: сохраняется только контент, который вам разрешено хранить.\n" +
                "Самоуничтожающиеся и одноразовые медиа НЕ перехватываются — это защита,\n" +
                "включённая отправителем. Используйте запрос постоянной копии."
            textSize = 12f
        })
        root.addView(Button(this).apply {
            text = "Открыть папку ClanSecrets"
            setOnClickListener { openFolder(exportDir.absolutePath) }
        })
        root.addView(Button(this).apply {
            text = "Запросить постоянную копию у отправителя…"
            setOnClickListener { requestPermanentCopy() }
        })

        setContentView(root)
        appendLog("ClanSecrets открыт")
    }

    private fun cacheDirParent(): File = filesDir.parentFile ?: filesDir

    fun appendLog(line: String) {
        val stamped = "${timeFmt.format(Date())} $line\n"
        logBuffer.append(stamped)
        if (logBuffer.length > 64_000) logBuffer.delete(0, logBuffer.length - 64_000)
        if (::logView.isInitialized) logView.text = logBuffer.toString()
    }

    fun setProxyStatus(status: String) {
        if (::proxyStatus.isInitialized) proxyStatus.text = "Прокси: $status"
    }

    private fun openFolder(path: String) {
        // Many file managers accept a content/tree URI; fall back to a toast.
        try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(Uri.parse(path), "resource/folder")
            }
            startActivity(intent)
        } catch (e: Exception) {
            Toast.makeText(this, path, Toast.LENGTH_LONG).show()
        }
    }

    private fun requestPermanentCopy() {
        // Consent-respecting flow: open a composer to the sender with a polite draft.
        // The fork wires this to the actual chat (see docs/CLANSECRETS.md).
        Toast.makeText(this,
            "Откроется чат с отправителем и черновик: «Пришли, пожалуйста, ещё раз без таймера — хочу сохранить».",
            Toast.LENGTH_LONG).show()
    }
}
